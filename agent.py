import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.adk.workflow import Workflow, FunctionNode
from google.adk.events.event import Event
from state import DiagnosticState
import adk_dxo

from google.adk.events.request_input import RequestInput



import json

def init_node(ctx, node_input=None):
    state = DiagnosticState.model_validate(ctx.state.to_dict())
    if not state.case_vignette:
        if node_input:
            input_text = ""
            if hasattr(node_input, 'parts') and node_input.parts:
                for part in node_input.parts:
                    if hasattr(part, 'text') and part.text:
                        input_text += part.text
            else:
                input_text = str(node_input)
                
            input_text = input_text.strip(' "\'')
            
            # If the user typed "case_1", try to load it from the cases/ folder
            case_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases", f"{input_text}.json")
            if os.path.exists(case_path):
                with open(case_path, 'r') as f:
                    case_data = json.load(f)
                    state.case_vignette = case_data.get("vignette", "")
                    state.ground_truth = case_data.get("ground_truth", "")
                    
                    # Format the structured JSON into a comprehensive medical record for the Gatekeeper
                    record = []
                    for key, value in case_data.items():
                        if key not in ["id", "vignette", "ground_truth"]:
                            if isinstance(value, dict):
                                record.append(f"### {key.replace('_', ' ').upper()}")
                                for k, v in value.items():
                                    record.append(f"- **{k.upper()}**: {v}")
                            else:
                                record.append(f"### {key.replace('_', ' ').upper()}\n{value}")
                    
                    state.full_case_text = "\n\n".join(record)
            else:
                # Otherwise, treat the input as a raw custom vignette
                state.case_vignette = input_text
                # Use the vignette as a fallback for the full case text if not provided
                state.full_case_text = input_text
                
            ctx.state.update(state.model_dump())
            return Event(route="start_debate")
        else:
            return RequestInput(message="Please provide the initial case vignette OR type a case ID (e.g. 'case_1', 'case_2').")
    return Event(route="start_debate")

def dr_hypothesis(ctx):
    state = DiagnosticState.model_validate(ctx.state.to_dict())
    adk_dxo.run_dr_hypothesis(state)
    ctx.state.update(state.model_dump())

def dr_test_chooser(ctx):
    state = DiagnosticState.model_validate(ctx.state.to_dict())
    adk_dxo.run_dr_test_chooser(state)
    ctx.state.update(state.model_dump())

def dr_challenger(ctx):
    state = DiagnosticState.model_validate(ctx.state.to_dict())
    adk_dxo.run_dr_challenger(state)
    ctx.state.update(state.model_dump())

def dr_stewardship(ctx):
    state = DiagnosticState.model_validate(ctx.state.to_dict())
    adk_dxo.run_dr_stewardship(state)
    ctx.state.update(state.model_dump())

def dr_checklist(ctx):
    state = DiagnosticState.model_validate(ctx.state.to_dict())
    state.round_count += 1
    adk_dxo.run_dr_checklist(state)
    ctx.state.update(state.model_dump())
    decision = state.round_decision.decision_type
    
    # decision_type will be one of: 'diagnose', 'consult_gatekeeper', 'continue'
    if decision == "consult_gatekeeper":
        return Event(route="consult_gatekeeper")
    return Event(route=decision)

def gatekeeper(ctx):
    state = DiagnosticState.model_validate(ctx.state.to_dict())
    decision = state.round_decision
    
    # Base cost for a "Visit" / Gatekeeper turn
    TURN_COST = 100
    state.total_cost += TURN_COST
    state.cost_itemization.append(f"Consultation Visit: ${TURN_COST}")
    
    # Process patient questions
    if decision.questions:
        for q in decision.questions:
            ans = adk_dxo.gatekeeper_respond(state, q)
            state.information_history.append("Q: " + str(q) + "\n" + "A: " + str(ans))
            # Questions are cheap
            state.total_cost += 10
            state.cost_itemization.append(f"Question (Nominal): $10 - {q}")
        
    # Process diagnostic tests
    if decision.tests:
        for t in decision.tests:
            res = adk_dxo.gatekeeper_respond(state, t)
            state.information_history.append("Test: " + str(t) + "\n" + "Result: " + str(res))
            # Tests are expensive
            state.total_cost += 250
            state.cost_itemization.append(f"Test (Nominal): $250 - {t}")
        
    # Clear the debate history for the new round
    state.debate_history = []
    ctx.state.update(state.model_dump())

def judge(ctx):
    state = DiagnosticState.model_validate(ctx.state.to_dict())
    diagnosis = state.round_decision.diagnosis
    
    # If we have a structured ground truth from a case JSON, use it! Otherwise fallback to vignette.
    truth_text = state.ground_truth if state.ground_truth else state.case_vignette
    score = adk_dxo.judge_diagnosis(diagnosis, truth_text)
    
    # Generate a narrative summary of the panel's reasoning
    narrative_summary = adk_dxo.summarize_case(state)
    
    state.case_closed = True
    state.final_diagnosis = diagnosis
    
    # Create a comprehensive markdown summary for the UI
    summary_md = f"## 🩺 Case Closed\n\n"
    summary_md += f"**Final Diagnosis:** {diagnosis}\n\n"
    if state.ground_truth:
        summary_md += f"**True Ground Truth:** {state.ground_truth}\n\n"
    summary_md += f"**Judge Evaluation Score:** {score}/5\n\n"
    summary_md += f"### 📝 Diagnostic Journey & Reasoning\n"
    summary_md += f"{narrative_summary}\n\n"
    summary_md += f"### 💰 Financial Breakdown\n"
    summary_md += f"**Total Workup Cost:** ${state.total_cost}\n\n"
    for item in state.cost_itemization:
        summary_md += f"- {item}\n"
    
    state.debate_history.append(f"--- CASE CLOSED ---\nScore: {score}\nCost: ${state.total_cost}")
    ctx.state.update(state.model_dump())
    
    return summary_md

# Wrap the functions into ADK FunctionNodes
node_init = FunctionNode(func=init_node, name="Init")
node_hypothesis = FunctionNode(func=dr_hypothesis, name="Dr_Hypothesis")
node_test_chooser = FunctionNode(func=dr_test_chooser, name="Dr_Test_Chooser")
node_challenger = FunctionNode(func=dr_challenger, name="Dr_Challenger")
node_stewardship = FunctionNode(func=dr_stewardship, name="Dr_Stewardship")
node_checklist = FunctionNode(func=dr_checklist, name="Dr_Checklist")
node_gatekeeper = FunctionNode(func=gatekeeper, name="Gatekeeper")
node_judge = FunctionNode(func=judge, name="Judge")

# Define the formal ADK-DxO Graph
root_agent = Workflow(
    name="adk_dxo_workflow",
    state_schema=DiagnosticState,
    edges=[
        # Init handles getting the initial user vignette
        ("START", node_init, {
            "start_debate": node_hypothesis
        }),
        # The main Chain of Debate sequence
        (node_hypothesis, node_test_chooser, node_challenger, node_stewardship, node_checklist, {
            "consult_gatekeeper": node_gatekeeper,
            "continue": node_hypothesis,   # Loop back without external queries
            "diagnose": node_judge         # Break out to the final evaluation
        }),
        # After the Gatekeeper returns results, the panel starts a new round
        (node_gatekeeper, node_hypothesis)
    ]
)
