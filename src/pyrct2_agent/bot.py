"""Minimal pyrct2 agent — LLM plays RollerCoaster Tycoon 2."""

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from pyrct2.client import RCT2
from pyrct2.scenarios import Scenario

from pyrct2_agent.prompts import SYSTEM_PROMPT
from pyrct2_agent.tools import make_tools


def play(
    scenario=Scenario.TEST_PARK,
    model="gpt-5-mini",
    base_url=None,
    api_key=None,
    headless=False,
    turns=5,
    ticks_per_turn=1000,
):
    game = RCT2.launch(scenario, headless=headless)
    game.park.cheats.build_in_pause_mode()

    tools = make_tools(game)
    llm = ChatOpenAI(model=model, **({"base_url": base_url} if base_url else {}), **({"api_key": api_key} if api_key else {}))
    agent = create_agent(llm, tools, system_prompt=SYSTEM_PROMPT)

    for turn in range(turns):
        p = game.park
        d = p.date
        print(f"\n=== Turn {turn + 1}/{turns} | Month {d.month} Year {d.year} | ${p.finance.cash:,} | Rating {p.rating} ===")

        for chunk in agent.stream(
            {"messages": [("user", f"Turn {turn + 1}/{turns}. Do what you think is best.")]},
        ):
            for node, updates in chunk.items():
                for msg in updates.get("messages", []):
                    if msg.type == "ai":
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                print(f"  -> {tc['name']}({tc['args']})")
                        if msg.content:
                            print(f"  Agent: {msg.content[:300]}")
                    elif msg.type == "tool":
                        print(f"  <- {msg.name}: {msg.content[:150]}")

        game.advance_ticks(ticks_per_turn)

    print(f"\nGame over. Final rating: {game.park.rating}")
    game.close()


if __name__ == "__main__":
    play()
