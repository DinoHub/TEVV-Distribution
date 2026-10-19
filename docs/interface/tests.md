# Tests and suites

## A test: which stack flies which drone

```yaml
# tests/cross-demo.yaml        (the file name is the test's id)
schema: tevv.test.v1
scenario: multi-cross-two      # a folder under scenarios/ (or a path)
drones:                        # drone -> stack (stacks/<id>/interface.py, or a built-in)
  Drone1: vio-openvins
  Drone2: super-planner
repeats: 1                     # optional, default 1
```

The scenario says what happens: the world, the drones and each drone's
mission with its observers, authored in ScenarioLab (observers in the
dashboard). The stacks say who flies and how. The test binds them. A drone
with a mission that the test leaves out is flown by `tevv-default`; a drone
named in `drones` must have a mission. The schema is
`platform/stacks/mns_stacks/schemas/tevv-test.v1.schema.json` in the platform.

In the dashboard, the Run step picks the stack for each drone and **Save
test** writes this file (a new test, or over one). It offers only what can
fly: a stack whose needs a drone lacks is shown, disabled, with the reason,
and PX4 with ArduPilot is refused. From a terminal, `test save` does the
same, with the same checks:

```bash
./tevv test save cross-demo --scenario multi-cross-two --drone Drone1=vio-openvins --drone Drone2=super-planner
./tevv stack list --scenario multi-cross-two   # each stack, and which of the scenario's drones it can fly
./tevv test init cross-demo --scenario multi-cross-two --drone Drone1=vio-openvins --drone Drone2=super-planner
./tevv test list                    # every test, and who flies each drone on which autopilot
./tevv test show cross-demo
./tevv interface cross-demo         # what each drone offers its stack; observers it cannot feed
./tevv run tests/cross-demo.yaml    # or: ./tevv run cross-demo   (--repeats N to override)
./tevv results cross-demo           # one row per run per mission
./tevv logs cross-demo --drone Drone2      # interface.py's output (-f while it runs)
./tevv stop cross-demo
```

`./tevv run scenarios/<s>` flies a scenario on its own: every drone with a
mission on `tevv-default`.

Before anything starts, a run refuses: a drone that is not in the scenario
or has no mission, an unknown or invalid stack, a drone that lacks a sensor
its stack needs, PX4 and ArduPilot in one scenario, and a mission whose
judged observers its stack or drone cannot feed. Results are described in
[results.md](results.md).

## A suite: a list of tests

```yaml
# suites/local-planner/suite.yaml
schema: tevv.suite.v2
name: Local planner suite
description: How well a local planner reaches goals in the container yard ...
tests:                             # run in this order, each as written
  - test: nav-open-course
    purpose: Goal following in open space (three goals, nothing in the way)
  - test: nav-detour
    purpose: Finding a way round a 30 m container row to a goal behind it
```

A suite adds nothing to its tests: each keeps its scenario, its stacks and its
repeats. A suite run runs them one after another, each into its own folder
under `generated/suites/<suite>/<run>/`, and gathers each test's verdicts.
To run a suite against another stack, point its tests at that stack (or copy
them).

```bash
./tevv suite init planner --tests nav-open-course nav-detour
./tevv suite check planner
./tevv suite run planner [--repeats N]
./tevv suite results planner [--run <run>] [--format md|csv]
./tevv suite runs planner
./tevv suite stop planner [--now]
```

The examples (`suites/vio-estimator`, `suites/local-planner`,
`suites/vio-nav-stack`) are starting points to copy, not a standard: what
passes is yours to decide, in each mission's observers.
