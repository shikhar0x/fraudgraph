"""
Action Request — matches docs/architecture.md Section 4.3.
This is what the Agent Reasoning Layer (Person 2) hands to your
policy/action layer. Don't let this drift from what they actually emit —
confirm the shape with them before Day 3 integration.
"""
from pydantic import BaseModel
from case_memory.schema import ACTIONS, ROUTES

class ActionRequest(BaseModel):
    action: ACTIONS
    requires_approval: bool
    route: ROUTES
    justification: str  # must cite a policy rule, e.g. "R2"
