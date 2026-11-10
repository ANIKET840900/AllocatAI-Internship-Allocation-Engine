from __future__ import annotations

from collections.abc import Callable


class AgentOrchestrator:
    """Runs only explicitly registered tools allowed for the selected agent."""

    PERMISSIONS = {
        "orchestrator": frozenset({"eligibility", "matching", "allocation", "fairness", "rag", "explanation"}),
        "resume": frozenset({"resume_analysis"}),
        "internship": frozenset({"internship_lookup"}),
        "eligibility": frozenset({"eligibility"}),
        "matching": frozenset({"matching"}),
        "allocation": frozenset({"allocation"}),
        "fairness": frozenset({"fairness"}),
        "explanation": frozenset({"explanation"}),
        "rag": frozenset({"rag"}),
    }

    def __init__(self, tools: dict[str, Callable[[str], object]]):
        self.tools = tools

    def execute(self, agent: str, tool: str, task: str):
        if tool not in self.PERMISSIONS.get(agent, frozenset()):
            raise PermissionError(f"Agent '{agent}' is not permitted to invoke tool '{tool}'")
        if tool not in self.tools:
            raise LookupError(f"Tool '{tool}' is not registered")
        return self.tools[tool](task)