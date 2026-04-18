# pyrct2-agent

LLM agent that plays [RollerCoaster Tycoon 2](https://openrct2.io/) via [pyrct2](https://github.com/MaukWM/pyrct2). Give it a scenario and an LLM — it builds rides, places paths, and tries to meet the objective.

## Install

```bash
pip install pyrct2-agent
pyrct2 setup        # finds OpenRCT2, installs the bridge plugin
```

## Quick start

```python
from pyrct2_agent import Agent
from pyrct2.scenarios import Scenario
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="gpt-5",
    model_kwargs={"parallel_tool_calls": False}, # If you don't disable this, it can result in weird or incoherent map states (sometimes)
)
result = Agent(Scenario.CRAZY_CASTLE, llm=llm, max_actions=50).run()
print(result)
```

## Modes

The agent loop supports three timing strategies:

| Mode | Behavior |
|------|----------|
| `TickPerAction()` | Game advances N ticks per tool call. Ticks run in background while LLM thinks. (default) |
| `PauseAndAct()` | Game paused during thinking. N actions per turn, then M ticks advance. |
| `RealTime()` | Game runs continuously. LLM latency = real game time passing. |

```python
from pyrct2_agent import Agent, PauseAndAct

result = Agent(
    Scenario.TEST_PARK,
    llm=llm,
    mode=PauseAndAct(ticks_per_turn=2000, actions_per_turn=10),
).run()
```

## Tools

12 builtin tools across three categories:

| Category | Tools |
|----------|-------|
| Observe | `get_park_status`, `show_map` |
| Paths | `place_path`, `place_path_line`, `remove_path` |
| Rides | `list_available_rides`, `place_ride`, `place_stall`, `set_ride_price`, `get_rides`, `check_ride_connectivity`, `demolish_ride` |

## Custom tools

```python
from langchain_core.tools import tool

def my_tools(game):
    @tool
    def hire_handyman() -> str:
        """Hire a handyman."""
        game.park.staff.hire(StaffType.HANDYMAN)
        return "Hired"
    return [hire_handyman]

# Add alongside builtins
Agent(scenario, llm=llm, extra_tools=my_tools)

# Or replace all builtins
Agent(scenario, llm=llm, tools=my_tools)
```

## Configuration

```python
Agent(
    scenario,
    llm=llm,
    mode=TickPerAction(ticks_per_action=200),   # timing strategy
    system_prompt="custom prompt here",         # override default
    game_speed=4,                               # 0-7
    headless=True,                              # hide game window
    end_on_scenario_complete=True,              # stop when objective met
    max_ticks=100_000,                          # tick limit
    max_actions=200,                            # action limit
)
```

## Requirements

- Python 3.12+
- [OpenRCT2](https://openrct2.io/) with RCT2 game data
- [pyrct2](https://github.com/MaukWM/pyrct2) (`pip install pyrct2-agent` pulls it in)
- An OpenAI API key (or any [LangChain-compatible LLM](https://python.langchain.com/docs/integrations/chat/))
