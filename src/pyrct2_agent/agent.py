"""Agent — the main public API for pyrct2-agent."""

from __future__ import annotations

import time
import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING

from langchain.agents import create_agent
from pyrct2._generated.enums import GameSpeed
from pyrct2.client import RCT2
from pyrct2.scenarios import Scenario

from pyrct2_agent.modes import Mode, TickPerAction
from pyrct2_agent.prompts import build_system_prompt
from pyrct2_agent.result import Outcome, RunResult
from pyrct2_agent.tools import default_tools

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

# Tool factory: receives a game instance, returns a list of tools.
ToolFactory = Callable[[RCT2], list]


def _warn_no_end_condition(
    end_on_scenario_complete: bool, max_ticks: int | None, max_actions: int | None
) -> None:
    if not end_on_scenario_complete and not max_ticks and not max_actions:
        warnings.warn(
            "No end condition set — agent will run until interrupted.",
            stacklevel=3,
        )


class Agent:
    """LLM agent that plays RollerCoaster Tycoon 2.

    Minimal usage::

        from pyrct2_agent import Agent
        from pyrct2.scenarios import Scenario
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model="gpt-5.4",
            model_kwargs={"parallel_tool_calls": False},
        )
        result = Agent(Scenario.CRAZY_CASTLE, llm=llm).run()

    .. warning::

        Set ``parallel_tool_calls=False`` on the LLM. Without it, the model
        may issue multiple actions simultaneously (e.g. placing two rides at
        once). If the first fails, the second still executes against stale
        assumptions, leading to incoherent park states.

    Custom tools::

        # Add to builtins
        def my_tools(game):
            @tool
            def hire_all() -> str:
                for t in StaffType:
                    game.park.staff.hire(t)
                return "Done"
            return [hire_all]

        Agent(scenario, llm=llm, extra_tools=my_tools)

        # Replace all builtins
        Agent(scenario, llm=llm, tools=my_tools)
    """

    def __init__(
        self,
        scenario: Scenario,
        *,
        llm: BaseChatModel,
        mode: Mode = TickPerAction(),
        system_prompt: str | None = None,
        tools: ToolFactory | None = None,
        extra_tools: ToolFactory | None = None,
        game_speed: int = 4,
        headless: bool = True,
        end_on_scenario_complete: bool = True,
        max_ticks: int | None = None,
        max_actions: int | None = None,
    ) -> None:
        if tools is not None and extra_tools is not None:
            raise ValueError("Pass 'tools' or 'extra_tools', not both.")

        self._game: RCT2 | None = None
        self.scenario = scenario
        self.llm = llm
        self.mode = mode
        self.system_prompt = system_prompt
        self._tools = tools
        self._extra_tools = extra_tools
        self.game_speed = game_speed
        self.headless = headless
        self.end_on_scenario_complete = end_on_scenario_complete
        self.max_ticks = max_ticks
        self.max_actions = max_actions

        _warn_no_end_condition(end_on_scenario_complete, max_ticks, max_actions)

    @classmethod
    def from_game(
        cls,
        game: RCT2,
        *,
        llm: BaseChatModel,
        mode: Mode = TickPerAction(),
        system_prompt: str | None = None,
        tools: ToolFactory | None = None,
        extra_tools: ToolFactory | None = None,
        end_on_scenario_complete: bool = True,
        max_ticks: int | None = None,
        max_actions: int | None = None,
    ) -> Agent:
        """Attach to an already-running game instance."""
        agent = cls.__new__(cls)
        agent._game = game
        agent.scenario = None  # type: ignore[assignment]
        agent.llm = llm
        agent.mode = mode
        agent.system_prompt = system_prompt
        agent._tools = tools
        agent._extra_tools = extra_tools
        agent.end_on_scenario_complete = end_on_scenario_complete
        agent.max_ticks = max_ticks
        agent.max_actions = max_actions

        _warn_no_end_condition(end_on_scenario_complete, max_ticks, max_actions)
        return agent

    def _resolve_tools(self, game: RCT2) -> list:
        """Build the final tool list from config."""
        if self._tools is not None:
            return self._tools(game)

        all_tools = default_tools(game)
        if self._extra_tools is not None:
            all_tools.extend(self._extra_tools(game))
        return all_tools

    def run(self) -> RunResult:
        """Run the agent loop until an end condition fires."""
        if self._game is not None:
            return self._game_loop(self._game)

        game = RCT2.launch(self.scenario, headless=self.headless)
        try:
            game.park.cheats.build_in_pause_mode()
            game.park.open()
            game.actions.game_set_speed(speed=GameSpeed(self.game_speed))
            return self._game_loop(game)
        finally:
            game.close()

    def _game_loop(self, game: RCT2) -> RunResult:
        prompt = build_system_prompt(self.mode, self.system_prompt)
        tools = self._resolve_tools(game)
        agent_executor = create_agent(self.llm, tools, system_prompt=prompt)
        messages: list = []

        start_time = time.monotonic()
        outcome: Outcome | None = None
        total_actions = 0
        total_ticks = 0

        for i, snapshot in enumerate(self.mode(game, agent_executor, messages), 1):
            total_actions += snapshot.actions
            total_ticks = game.get_status().get("scenarioTicks", total_ticks)

            print(f"\n--- Snapshot {i} | Guests {game.park.guests.count()} ---")

            if self.max_actions and total_actions >= self.max_actions:
                outcome = Outcome.MAX_ACTIONS
                break
            if self.end_on_scenario_complete:
                if game.state.scenario_status() != "inProgress":
                    outcome = Outcome.SCENARIO_COMPLETE
                    break
            if self.max_ticks and total_ticks >= self.max_ticks:
                outcome = Outcome.MAX_TICKS
                break

        return RunResult(
            outcome=outcome,
            total_actions=total_actions,
            total_ticks=total_ticks,
            wall_time_seconds=time.monotonic() - start_time,
        )
