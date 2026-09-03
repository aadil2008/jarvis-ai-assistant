from __future__ import annotations

import unittest

from app.config import Settings
from app.models import AgentName, RouteMode
from app.router import route_request


class RouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = Settings(
            fast_model="fast-model",
            smart_model="smart-model",
            coding_model="coding-model",
            web_model="web-model",
        )

    def route(self, message: str, agent: AgentName | None = None, mode: RouteMode = RouteMode.AUTO):
        return route_request(message, agent, mode, self.settings)

    def test_greeting_uses_fast(self) -> None:
        self.assertEqual(self.route("Hello").route, "fast")

    def test_rewrite_uses_fast(self) -> None:
        self.assertEqual(self.route("Rewrite this paragraph").route, "fast")

    def test_summary_uses_fast(self) -> None:
        self.assertEqual(self.route("Summarize this text").model, "fast-model")

    def test_complicated_debugging_uses_coding(self) -> None:
        decision = self.route(
            "Debug this complicated asynchronous Python architecture and evaluate the design tradeoffs"
        )
        self.assertEqual(decision.route, "coding")
        self.assertEqual(decision.model, "coding-model")

    def test_simple_coding_question_uses_coding(self) -> None:
        decision = self.route("Write a Python function that reverses a string")
        self.assertEqual(decision.route, "coding")
        self.assertEqual(decision.model, "coding-model")

    def test_code_block_uses_coding(self) -> None:
        self.assertEqual(self.route("Fix this:\n```python\nprint('hello')\n```").route, "coding")

    def test_current_web_research_uses_web(self) -> None:
        decision = self.route("Search the web for today's latest AI announcements")
        self.assertEqual(decision.route, "web")
        self.assertEqual(decision.model, "web-model")

    def test_plain_find_does_not_force_web(self) -> None:
        self.assertEqual(self.route("Find the conclusion in this report").route, "fast")

    def test_direct_look_up_uses_web(self) -> None:
        self.assertEqual(self.route("Look up MIT's latest announcement").route, "web")

    def test_current_information_uses_web(self) -> None:
        self.assertEqual(self.route("Give me current information about OpenAI leadership").route, "web")

    def test_current_local_project_does_not_force_web(self) -> None:
        self.assertEqual(self.route("Summarize my current project").route, "fast")

    def test_agent_name_alone_does_not_force_escalation(self) -> None:
        self.assertEqual(self.route("Hello", AgentName.FRIDAY).route, "fast")

    def test_friday_technical_research_uses_smart(self) -> None:
        self.assertEqual(
            self.route("Analyze this research paper", AgentName.FRIDAY).route,
            "smart",
        )

    def test_edith_calculation_uses_smart(self) -> None:
        self.assertEqual(self.route("Calculate the load distribution", AgentName.EDITH).route, "smart")

    def test_explicit_reasoning_task_uses_smart(self) -> None:
        self.assertEqual(self.route("Reasoning: determine the best design").route, "smart")

    def test_manual_modes_always_select_configured_model(self) -> None:
        for mode, expected_route, expected_model in (
            (RouteMode.FAST, "fast", "fast-model"),
            (RouteMode.SMART, "smart", "smart-model"),
            (RouteMode.CODING, "coding", "coding-model"),
            (RouteMode.WEB, "web", "web-model"),
        ):
            with self.subTest(mode=mode):
                decision = self.route("Hello", mode=mode)
                self.assertEqual(decision.route, expected_route)
                self.assertEqual(decision.model, expected_model)


if __name__ == "__main__":
    unittest.main()
