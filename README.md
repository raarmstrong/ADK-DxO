# ADK_DxO: Sequential Diagnosis Orchestrator

ADK_DxO is an open-source, multi-agent medical diagnostic orchestrator built on the Google Agent Development Kit (ADK).

This project is based on the **MAI-DxO (Microsoft AI Diagnostic Orchestrator)** and **SDBench** framework introduced by the Microsoft AI team in their 2025 paper, ['Sequential Diagnosis with Language Models'](https://arxiv.org/abs/2506.22405). It aims to recreate the iterative, sequential clinical reasoning process using a panel of AI doctors who debate, ask patient questions, and order diagnostic tests under budget constraints before committing to a final diagnosis.

## Proof of Concept (POC) Limitations
This repository currently represents a **Proof of Concept** designed to allow researchers and developers to visually debug and develop multi-agent medical workflows. As such, there are several intentional constraints:

- **Single Case Execution**: The system is heavily optimized to run one case at a time through the interactive ADK Web UI. This allows users to inspect the "Chain of Debate" between the AI doctors in real-time, tweak prompts, and observe the exact decision-making process.
- **Nominal Pricing**: Unlike the original paper which maps tests to dynamic real-world CPT billing codes, this POC uses a static, nominal pricing placeholder (e.g., $10 per question, $250 per diagnostic test) to demonstrate the cost-tracking architecture without requiring a complex medical billing backend.
- **Limited Turn Architecture**: To prevent runaway API costs and infinite loops during local testing, the orchestrator is hard-coded with a maximum round limit. If the panel does not reach a consensus by the final round, Dr. Checklist is forcefully prompted to output a final diagnosis.
- **Choice of Model**: Whilst the architecture is model-agnostic, the POC is configured to use Google Gemini 3.5 Flash Lite throughout for efficiency of speed and cost. 

## Citation & Acknowledgments
The architectural concepts, personas (Dr. Hypothesis, Dr. Test-Chooser, Dr. Challenger, Dr. Stewardship, Dr. Checklist), and evaluation frameworks implemented in this repository are based on:

> **Sequential Diagnosis with Language Models**
> Harsha Nori, Mayank Daswani, Christopher Kelly, et al.
> *Microsoft AI, July 2025.* 
> [arXiv:2506.22405v2](https://arxiv.org/abs/2506.22405)

## Disclaimer
**This project is for educational and research purposes only.**
- This system is an experimental AI simulation and is **NOT** intended for clinical use, patient triage, or actual medical diagnosis.
- The sample cases provided in the `cases/` directory are AI-generated, heavily summarized, anonymized, and modified abstractions intended solely for evaluating AI reasoning. They do not represent real, identifiable patients.
- Do not use this software with real patient health information (PHI) or upload proprietary, copyrighted medical records.

## Setup & Installation

1. **Clone the repository and set up a virtual environment:**
   ```bash
   git clone https://github.com/raarmstrong/ADK_DxO.git
   cd ADK_DxO
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set your model and configure your API Key (if required):**
   
   Create a `.env` file in the root directory and add your Google Gemini API key:
   ```text
   GEMINI_API_KEY=your_api_key_here
   ```

   This POC uses the same model for all API calls, this is set in `adk_dxo.py`:
   ```text
   MODEL = "gemini-3.5-flash-lite"
   ```

## Running the Simulation

ADK_DxO uses the ADK web UI to provide an interactive chat interface.

1. **Start the ADK Web Server:**
   ```bash
   adk web
   ```
2. **Open the UI:**
   Navigate to `http://127.0.0.1:8000` in your browser.
3. **Start a Case:**
   When prompted by the system, type the ID of a sample case from the /cases folder (e.g., `case_1`, `case_2`) into the chat box to begin the simulation. The panel of doctors will take over, debating the clinical findings, requesting tests from the Gatekeeper, and tracking the financial cost until a final diagnosis is reached. This will then be evaluated by the Judge agent and a summary result returned.

## Creating Custom Cases
You can easily create your own medical cases by adding a `.json` file to the `cases/` directory. 

The orchestrator requires a specific JSON schema to function correctly. The `vignette` is the only information provided to the medical panel at the start. The rest of the fields (and the nested `test_results` object) are kept hidden and are used exclusively by the **Gatekeeper** to answer the panel's questions realistically. The `ground_truth` is used by the **Judge** at the end of the simulation to score the panel's final diagnosis.

Here is the required structure:
```json
{
  "id": "my_custom_case",
  "vignette": "A brief 1-2 sentence summary of the patient's chief complaint. This is shown to the panel immediately.",
  "history_of_present_illness": "Detailed symptom progression...",
  "past_medical_history": "Relevant past surgeries, illnesses...",
  "medications": "Current prescriptions...",
  "social_and_family_history": "Smoking status, family diseases...",
  "test_results": {
    "labs": "CBC, BMP, LFT results...",
    "imaging": "CT, MRI, X-ray findings...",
    "biopsy": "Pathology reports (optional)..."
  },
  "ground_truth": "The exact definitive diagnosis (e.g. Acute Pulmonary Embolism)"
}
```

## Repository Structure
- `agent.py`: The core ADK graph and node router.
- `adk_dxo.py`: The LLM generation engine managing API calls and formatting.
- `prompts.py`: System prompts defining the behaviors of the medical panel.
- `state.py`: Pydantic schemas enforcing strict JSON outputs and state management.
- `cases/`: Directory containing structured `.json` case files for the Gatekeeper to reference.
