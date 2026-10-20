# Testing your autonomy with TEVV

TEVV is four layers, each one file you can read:

```
ScenarioLab ──► scenarios/<s>/ScenarioSpec.yaml   WHAT happens     the world, the drones (airframe, sensors,
                                                                    start), each drone's mission (its points,
                                                                    reach radius, time budget)
dashboard  ──►    └─ each mission's observers      HOW it is judged (the one thing the dashboard edits)
you        ──► stacks/<id>/interface.py           WHO flies, HOW   the autopilot, the sensors it needs, your
                                                                    containers, and the code that wires TEVV's
                                                                    topics to yours (Python, TEVV SDK)
you        ──► tests/<t>.yaml                     WHICH stack flies WHICH drone, how many runs
(optional) ──► suites/<id>/suite.yaml             a kind of test: scenarios, each with its purpose; no stack,
                                                                    you pick it when you run (--stack)
```

| To | Read |
| --- | --- |
| bring your software: write a stack's `interface.py`; how a run goes, take-off to landing | [stacks.md](stacks.md) |
| know every topic a drone offers and what you send back | [topics.md](topics.md) |
| bind stacks to a scenario's drones, run, run a suite on your stack | [tests.md](tests.md) |
| read the verdicts: observers (of the mission, take-off or landing), how a run is judged | [results.md](results.md) |

TEVV ships no stack but its own: `tevv-default` (TEVV's follower flies the
mission on SimpleFlight; `tevv-default-px4` and `tevv-default-ardupilot` on
those autopilots). Whatever the stack, it flies its drone from take-off to
landing; TEVV referees and judges. `stacks/` and `tests/` are yours: git
ignores them. [stacks.md](stacks.md) writes a planner and an estimator inline to copy from. The example suites
under [suites/](../../suites) (`local-planner`, `vio`, `stack`) name no stack:
`./tevv suite run local-planner --stack my-planner` flies your planner on all
of them.

## Five minutes

```bash
./tevv stack init my-planner --autopilot px4 --container me/planner:1
$EDITOR stacks/my-planner/interface.py          # wire TEVV's topics to yours
./tevv stack check my-planner
./tevv test init my-test --scenario nav-open-course --drone Drone1=my-planner
./tevv interface my-test                        # what the drone gives you
./tevv run my-test
./tevv logs my-test                             # your prints, logs and errors
./tevv results my-test
```

Nothing is built for TEVV: your `interface.py` is mounted and run by TEVV's
pinned interface image; your own software stays in your own images.
