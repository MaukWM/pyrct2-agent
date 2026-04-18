"""Agent — the main public API for pyrct2-agent."""

from __future__ import annotations

import time
import warnings
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

from langchain.agents import create_agent
from pyrct2._generated.enums import GameSpeed
from pyrct2.client import RCT2
from pyrct2.scenarios import Scenario

from pyrct2_agent.modes import Mode, PauseAndAct, RealTime, TickPerAction
from pyrct2_agent.prompts import build_system_prompt
from pyrct2_agent.result import Outcome, RunResult

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


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

        llm = ChatOpenAI(model="gpt-5.4")
        result = Agent(Scenario.CRAZY_CASTLE, llm=llm).run()

    Or attach to a running game::

        agent = Agent.from_game(game, llm=llm)
    """

    def __init__(
        self,
        scenario: Scenario,
        *,
        llm: BaseChatModel,
        mode: Mode = TickPerAction(),
        system_prompt: str | None = None,
        game_speed: int = 4,
        headless: bool = True,
        end_on_scenario_complete: bool = True,
        max_ticks: int | None = None,
        max_actions: int | None = None,
    ) -> None:
        self._game: RCT2 | None = None
        self.scenario = scenario
        self.llm = llm
        self.mode = mode
        self.system_prompt = system_prompt
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
        agent.end_on_scenario_complete = end_on_scenario_complete
        agent.max_ticks = max_ticks
        agent.max_actions = max_actions

        _warn_no_end_condition(end_on_scenario_complete, max_ticks, max_actions)
        return agent

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
        tools: list = []  # Phase 2 — no tools yet
        agent_executor = create_agent(self.llm, tools, system_prompt=prompt)

        messages: list = []
        start_time = time.monotonic()
        outcome: Outcome | None = None
        total_actions = 0
        total_ticks = 0
        tick_future: Future | None = None
        turn = 0
        mode = self.mode

        with ThreadPoolExecutor(max_workers=1) as executor:
            while outcome is None:
                turn += 1
                p = game.park
                d = p.date
                print(
                    f"\n=== Turn {turn} | Month {d.month} Year {d.year}"
                    f" | ${p.finance.cash:,} | Rating {p.rating}"
                    f" | Guests {p.guests.count()} ==="
                )

                outcome, actions, tick_future = self._run_turn(
                    game, agent_executor, executor, messages, mode, tick_future
                )
                total_actions += actions

                # --- Mode-specific: end of turn ---
                if isinstance(mode, TickPerAction):
                    if tick_future is not None:
                        tick_future.result()
                        tick_future = None
                elif isinstance(mode, PauseAndAct):
                    game.advance_ticks(mode.ticks_per_turn)
                elif isinstance(mode, RealTime):
                    game.pause()

                total_ticks = game.get_status().get("scenarioTicks", total_ticks)

                # Check end conditions (unless turn already ended it)
                if outcome is None:
                    if self.end_on_scenario_complete:
                        status = game.state.scenario_status()
                        if status != "inProgress":
                            outcome = Outcome.SCENARIO_COMPLETE
                    if self.max_ticks and total_ticks >= self.max_ticks:
                        outcome = Outcome.MAX_TICKS

        return RunResult(
            outcome=outcome,
            total_actions=total_actions,
            total_ticks=total_ticks,
            wall_time_seconds=time.monotonic() - start_time,
        )

    def _run_turn(
        self,
        game: RCT2,
        agent_executor,
        executor: ThreadPoolExecutor,
        messages: list,
        mode: Mode,
        tick_future: Future | None,
    ) -> tuple[Outcome | None, int, Future | None]:
        """Run one turn. Returns (outcome_or_None, actions_this_turn, tick_future)."""
        # --- Mode-specific: start of turn ---
        if isinstance(mode, TickPerAction):
            tick_future = executor.submit(game.advance_ticks, mode.ticks_per_action)
        elif isinstance(mode, RealTime):
            game.unpause()

        action_count = 0

        for chunk in agent_executor.stream({"messages": messages}):
            for node, updates in chunk.items():
                for msg in updates.get("messages", []):
                    if msg.type == "ai":
                        if msg.tool_calls:
                            if isinstance(mode, TickPerAction) and tick_future is not None:
                                tick_future.result()
                                tick_future = None
                            for tc in msg.tool_calls:
                                action_count += 1
                                print(f"  [{action_count}] -> {tc['name']}({tc['args']})")
                        if msg.content:
                            print(f"  Agent: {msg.content}")
                        messages.append(msg)

                    elif msg.type == "tool":
                        print(f"  <- {msg.name}: {msg.content[:150]}")
                        messages.append(msg)
                        if isinstance(mode, TickPerAction):
                            tick_future = executor.submit(
                                game.advance_ticks, mode.ticks_per_action
                            )

            # Check per-action end conditions
            if self.max_actions and (action_count) >= self.max_actions:
                return Outcome.MAX_ACTIONS, action_count, tick_future
            if isinstance(mode, PauseAndAct) and action_count >= mode.actions_per_turn:
                break

        return None, action_count, tick_future
