from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class Hypothesis(BaseModel):
    condition: str = Field(description="The medical condition or disease")
    probability: float = Field(description="Estimated probability (0-1) based on current evidence")
    rationale: str = Field(description="Reasoning for this hypothesis")

class DrHypothesisOutput(BaseModel):
    reasoning: str = Field(description="Dr. Hypothesis's reasoning and thoughts to share with the panel")
    differential_diagnosis: List[Hypothesis] = Field(description="The updated top hypotheses")

class TestRequest(BaseModel):
    request_type: Literal["question", "test"] = Field(description="Whether this is a question to the patient or a diagnostic test")
    content: str = Field(description="The specific question or test name")
    rationale: str = Field(description="Why this test or question is being requested")

class PanelDecision(BaseModel):
    decision_type: Literal["consult_gatekeeper", "diagnose", "continue"] = Field(description="The consensus action. Use 'consult_gatekeeper' if you are asking ANY questions or ordering ANY tests.")
    questions: Optional[List[str]] = Field(default=None, description="Questions for the patient")
    tests: Optional[List[str]] = Field(default=None, description="Diagnostic tests to order")
    diagnosis: Optional[str] = Field(default=None, description="The final diagnosis if decision_type is 'diagnose'")
    rationale: str = Field(description="Reasoning behind this decision")

class DiagnosticState(BaseModel):
    # Initial case information
    case_vignette: str = Field(default="", description="The initial clinical vignette provided to the agents")
    full_case_text: str = Field(default="", description="The secret complete medical record with all test results, used by Gatekeeper only")
    ground_truth: str = Field(default="", description="The actual correct diagnosis for evaluation")
    
    # History of information revealed by Gatekeeper
    information_history: List[str] = Field(default_factory=list, description="History of Q&A and test results")
    
    # Current differential diagnosis (maintained by Dr. Hypothesis)
    differential_diagnosis: List[Hypothesis] = Field(default_factory=list, description="Top hypotheses")
    
    # The running chain of debate (log of what each persona said in the current round)
    debate_history: List[str] = Field(default_factory=list, description="Transcripts of the current round's debate")
    
    # The current proposed test(s)/question(s) (by Dr. Test-Chooser)
    proposed_tests: List[TestRequest] = Field(default_factory=list, description="Tests proposed by Dr. Test-Chooser")
    
    # The final decision of the round (by Dr. Checklist / Consensus)
    round_decision: Optional[PanelDecision] = Field(default=None, description="The final action to take this round")
    
    # Is the case closed?
    case_closed: bool = Field(default=False, description="True if a final diagnosis has been made")
    final_diagnosis: Optional[str] = Field(default=None, description="The committed final diagnosis")
    
    # Cost tracking
    total_cost: int = Field(default=0, description="Total accumulated nominal cost")
    cost_itemization: List[str] = Field(default_factory=list, description="Log of incurred costs")
    
    # Round tracking
    round_count: int = Field(default=0, description="Number of rounds completed")
    max_rounds: int = Field(default=2, description="Maximum number of rounds allowed before forced diagnosis")
