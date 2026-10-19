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
(optional) ──► suites/<id>/suite.yaml             a list of tests, each with its purpose
```

| To | Read |
| --- | --- |
| bring your software: write a stack's `interface.py` | [stacks.md](stacks.md) |
| know every topic a drone offers and what you send back | [topics.md](topics.md) |
| bind stacks to a scenario's drones, run, group tests into suites | [tests.md](tests.md) |
| read the verdicts: observers, how a run is judged | [results.md](results.md) |

The worked examples are in [stacks/](../../stacks): `super-planner` (a
planner flying on PX4), `vio-openvins` (an estimator while TEVV flies on
SimpleFlight) and `vio-nav-stack` (an estimator feeding a planner that flies
on the estimate). Their tests are in [tests/](../../tests), including
`cross-demo`: two drones, two stacks, two autopilots in one scenario.

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
