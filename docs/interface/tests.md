# Tests and suites

## A test: which stack flies which drone

```yaml
# tests/cross-demo.yaml        (the file name is the test's id)
schema: tevv.test.v1
scenario: multi-cross-two      # a folder under scenarios/ (or a path)
drones:                        # drone -> stack (stacks/<id>/interface.py, or a built-in)
  Drone1: my-vio
  Drone2: my-planner
repeats: 1                     # optional, default 1
```

The scenario says what happens: the world, the drones and each drone's
mission, authored in ScenarioLab, and what is judged: observers on the run,
the drones, their cameras and the missions (set in the dashboard). The stacks say who flies and how. The test binds them. A drone
with a mission that the test leaves out is flown by `tevv-default`; a drone
named in `drones` must have a mission. Tests are yours, like stacks: TEVV
ships none, and git ignores `tests/`. The schema is
`platform/stacks/mns_stacks/schemas/tevv-test.v1.schema.json` in the platform.

In the dashboard, the Run step picks the stack for each drone and **Save
test** writes this file (a new test, or over one). It offers only what can
fly: a stack whose needs a drone lacks is shown, disabled, with the reason,
and PX4 with ArduPilot is refused. From a terminal, `test save` does the
same, with the same checks:

```bash
./tevv test save cross-demo --scenario multi-cross-two --drone Drone1=my-vio --drone Drone2=my-planner
./tevv stack list --scenario multi-cross-two   # each stack, and which of the scenario's drones it can fly
./tevv test init cross-demo --scenario multi-cross-two --drone Drone1=my-vio --drone Drone2=my-planner
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
its stack needs, PX4 and ArduPilot in one scenario, and a judged observer
(on the drone or its mission) its stack or drone cannot feed. Results are described in
[results.md](results.md).

## A suite: a kind of test

A suite names a kind of test, such as `local-planner` or `vio`, and lists
scenarios. It names no stack: you choose the stack when you run it, so one
suite tests any planner, and runs of different stacks compare.

```yaml
# suites/local-planner/suite.yaml
schema: tevv.suite.v3
name: Local planner
description: How well a local planner reaches goals in the container yard ...
scenarios:                         # run in this order
  - scenario: nav-open-course
    purpose: Goal following in open space (three goals, nothing in the way)
    repeats: 2                     # optional, default 1
  - scenario: nav-detour
    purpose: Finding a way round a 30 m container row to a goal behind it
```

`suite run <suite> --stack <stack>` flies every drone with a mission, in every
scenario, on that stack (`tevv-default` without `--stack`), one scenario after
another, each into its own folder under
`generated/suites/<suite>/<run>/scenarios/<scenario>/`, and gathers each
scenario's verdicts. A scenario the stack cannot fly (a drone lacks a sensor it
needs, say) is skipped with the reason; the others still fly.

```bash
./tevv suite init planner --scenarios nav-open-course nav-detour
./tevv suite check planner --stack my-planner     # can my-planner fly every scenario?
./tevv suite run planner --stack my-planner [--repeats N]
./tevv suite results planner [--run <run>] [--format md|csv]   # "Suite planner with my-planner"
./tevv suite runs planner                         # every run, newest first, with its stack
./tevv suite stop planner [--now]
```

The examples (`suites/local-planner`, `suites/vio`, `suites/stack`) are
starting points to copy, not a standard: what passes is yours to decide, in
the scenario's observers. To fly a scenario with different stacks on
different drones, write a test instead.
