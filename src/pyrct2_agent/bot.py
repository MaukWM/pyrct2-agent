"""Minimal pyrct2 agent — LLM plays RollerCoaster Tycoon 2."""

from concurrent.futures import Future, ThreadPoolExecutor

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from pyrct2.client import RCT2
from pyrct2.scenarios import Scenario

from pyrct2_agent.prompts import SYSTEM_PROMPT
from pyrct2_agent.tools import make_tools

MAX_ACTIONS = 200

# Ticks advanced between each tool call. This is deterministic — every
# action always sees exactly this many ticks of game progression,
# regardless of LLM latency. The advance runs in parallel with LLM
# thinking to hide latency.
TICKS_PER_ACTION = 200


def play(
    scenario=Scenario.TEST_PARK,
    model="gpt-5.4",
    base_url=None,
    api_key=None,
    headless=False,
):
    from dotenv import load_dotenv

    load_dotenv()

    game = RCT2.launch(scenario, headless=headless)
    game.park.cheats.build_in_pause_mode()
    game.park.open()
    game.actions.game_set_speed(speed=4)

    tools = make_tools(game)
    llm = ChatOpenAI(
        model=model,
        model_kwargs={"parallel_tool_calls": False},
        **({"base_url": base_url} if base_url else {}),
        **({"api_key": api_key} if api_key else {}),
    )

    executor = ThreadPoolExecutor(max_workers=1)

    turn = 0
    while True:
        turn += 1
        agent = create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)
        p = game.park
        d = p.date
        print(
            f"\n=== Turn {turn} | Month {d.month} Year {d.year}"
            f" | ${p.finance.cash:,} | Rating {p.rating} | Guests {p.guests} ==="
        )

        # Start first tick advance — runs while LLM generates first action
        tick_future: Future | None = executor.submit(
            game.advance_ticks, TICKS_PER_ACTION
        )

        action_count = 0
        for chunk in agent.stream(
            {
                "messages": [
                    (
                        "user",
                        f"Turn {turn}. Do what you think is best."
                        f" You have up to {MAX_ACTIONS} actions.",
                    )
                ]
            },
        ):
            for node, updates in chunk.items():
                for msg in updates.get("messages", []):
                    if msg.type == "ai":
                        if msg.tool_calls:
                            # Wait for tick advance to finish before tool runs
                            if tick_future is not None:
                                tick_future.result()
                                tick_future = None
                            for tc in msg.tool_calls:
                                action_count += 1
                                print(
                                    f"  [{action_count}/{MAX_ACTIONS}]"
                                    f" -> {tc['name']}({tc['args']})"
                                )
                        if msg.content:
                            print(f"  Agent: {msg.content}")
                    elif msg.type == "tool":
                        print(f"  <- {msg.name}: {msg.content[:150]}")
                        # Kick off next tick advance while LLM thinks
                        tick_future = executor.submit(
                            game.advance_ticks, TICKS_PER_ACTION
                        )

            if action_count >= MAX_ACTIONS:
                print(f"\n  Hit {MAX_ACTIONS} action limit.")
                break

        # Wait for any pending ticks
        if tick_future is not None:
            tick_future.result()

        p = game.park
        d = p.date
        print(
            f"\n  --- Paused | Month {d.month} Year {d.year}"
            f" | ${p.finance.cash:,} | Rating {p.rating} | Guests {p.guests} ---"
        )
        input("  [Press Enter for fresh context + another 200 actions]")

    game.close()


if __name__ == "__main__":
    play()
