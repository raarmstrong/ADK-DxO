import os
import json
from google import genai
from google.genai import types
from state import DiagnosticState, PanelDecision, Hypothesis, TestRequest, DrHypothesisOutput
from prompts import (
    GATEKEEPER_PROMPT,
    DR_HYPOTHESIS_PROMPT,
    DR_CHALLENGER_PROMPT,
    DR_TEST_CHOOSER_PROMPT,
    DR_STEWARDSHIP_PROMPT,
    DR_CHECKLIST_PROMPT,
    JUDGE_PROMPT
)

# Initialize client
client = genai.Client()
MODEL = "gemini-3.5-flash-lite"

import time
from google.genai.errors import APIError

def generate_with_retry(*args, **kwargs):
    # Proactively slow down to avoid hitting the 15 RPM free tier limit
    time.sleep(4)
    
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg or "429" in error_msg:
                if attempt < max_retries - 1:
                    # If we hit 429 quota exhausted, we should wait at least a minute
                    delay = 60 if "429" in error_msg else 10 * (2 ** attempt)
                    print(f"\n[!] API limit hit (429/503), retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
            raise e

def format_state_for_prompt(state: DiagnosticState) -> str:
    prompt = f"CASE VIGNETTE:\n{state.case_vignette}\n\n"
    prompt += "INFORMATION HISTORY:\n"
    for item in state.information_history:
        prompt += f"- {item}\n"
    prompt += "\nCURRENT DIFFERENTIAL DIAGNOSIS:\n"
    for h in state.differential_diagnosis:
        prompt += f"- {h.condition} (Prob: {h.probability}): {h.rationale}\n"
    prompt += "\nDEBATE HISTORY:\n"
    for turn in state.debate_history:
        prompt += f"{turn}\n\n"
    return prompt

def run_dr_hypothesis(state: DiagnosticState) -> DiagnosticState:
    prompt = format_state_for_prompt(state)
    prompt += "TASK: Update the differential diagnosis based on the latest information. Output JSON."
    
    response = generate_with_retry(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=DR_HYPOTHESIS_PROMPT,
            response_mime_type="application/json",
            response_schema=DrHypothesisOutput,
            temperature=0.2
        )
    )
    
    output_data = json.loads(response.text)
    output = DrHypothesisOutput(**output_data)
    
    state.differential_diagnosis = output.differential_diagnosis
    state.debate_history.append(f"Dr. Hypothesis:\n{output.reasoning}")
    return state

def run_dr_challenger(state: DiagnosticState) -> DiagnosticState:
    prompt = format_state_for_prompt(state)
    prompt += "TASK: Challenge the current hypotheses. What are we missing?"
    
    response = generate_with_retry(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=DR_CHALLENGER_PROMPT,
            temperature=0.4
        )
    )
    state.debate_history.append(f"Dr. Challenger:\n{response.text}")
    return state

def run_dr_test_chooser(state: DiagnosticState) -> DiagnosticState:
    prompt = format_state_for_prompt(state)
    prompt += "TASK: Propose up to 3 diagnostic tests or questions to maximally discriminate between hypotheses."
    
    response = generate_with_retry(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=DR_TEST_CHOOSER_PROMPT,
            temperature=0.2
        )
    )
    state.debate_history.append(f"Dr. Test-Chooser:\n{response.text}")
    return state

def run_dr_stewardship(state: DiagnosticState) -> DiagnosticState:
    prompt = format_state_for_prompt(state)
    prompt += "TASK: Review the proposed tests. Veto expensive/low-yield tests, suggest cheaper alternatives."
    
    response = generate_with_retry(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=DR_STEWARDSHIP_PROMPT,
            temperature=0.2
        )
    )
    state.debate_history.append(f"Dr. Stewardship:\n{response.text}")
    return state

def run_dr_checklist(state: DiagnosticState) -> DiagnosticState:
    prompt = format_state_for_prompt(state)
    if state.round_count >= state.max_rounds:
        prompt += f"TASK: This is ROUND {state.round_count}. You have reached the maximum allowed rounds ({state.max_rounds}). You MUST output a final 'diagnose' decision. Do NOT order more tests."
    else:
        prompt += f"TASK: This is ROUND {state.round_count} of {state.max_rounds}. Review the debate. Output the final consensus action as a JSON object matching the PanelDecision schema."
    
    response = generate_with_retry(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=DR_CHECKLIST_PROMPT,
            response_mime_type="application/json",
            response_schema=PanelDecision,
            temperature=0.1
        )
    )
    state.debate_history.append(f"Dr. Checklist (Final Decision):\n{response.text}")
    
    # Parse the structured response
    decision_data = json.loads(response.text)
    decision = PanelDecision(**decision_data)
    state.round_decision = decision
    return state

def gatekeeper_respond(state: DiagnosticState, request: str) -> str:
    prompt = f"CASE TEXT (GROUND TRUTH):\n{state.full_case_text}\n\n"
    prompt += f"HISTORY:\n{state.information_history}\n\n"
    prompt += f"REQUEST: {request}\n"
    
    response = generate_with_retry(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=GATEKEEPER_PROMPT,
            temperature=0.1
        )
    )
    return response.text

def judge_diagnosis(candidate_diagnosis: str, ground_truth: str) -> int:
    prompt = f"Ground Truth Diagnosis: {ground_truth}\n"
    prompt += f"Candidate Diagnosis: {candidate_diagnosis}\n"
    
    response = generate_with_retry(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=JUDGE_PROMPT,
            temperature=0.0
        )
    )
    # Basic parsing to extract integer score from the end
    try:
        score = int(response.text.strip().split()[-1])
        return score
    except:
        # Fallback if parsing fails
        print(f"Judge output: {response.text}")
        return 0

def summarize_case(state: DiagnosticState) -> str:
    prompt = "Write a concise, 1-2 paragraph medical summary of the diagnostic journey based on the following logs. Focus on how the panel's reasoning evolved as test results came back, and explain why they arrived at their final diagnosis.\n\n"
    prompt += format_state_for_prompt(state)
    
    response = generate_with_retry(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2
        )
    )
    return response.text

def run_chain_of_debate(state: DiagnosticState) -> DiagnosticState:
    print("\n--- Starting Chain of Debate ---")
    state = run_dr_hypothesis(state)
    print("Dr. Hypothesis completed.")
    state = run_dr_challenger(state)
    print("Dr. Challenger completed.")
    state = run_dr_test_chooser(state)
    print("Dr. Test-Chooser completed.")
    state = run_dr_stewardship(state)
    print("Dr. Stewardship completed.")
    state = run_dr_checklist(state)
    print("Dr. Checklist completed.")
    return state
