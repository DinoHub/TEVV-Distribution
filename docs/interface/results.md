# Observers and results

Each **observer** is a check: a type TEVV provides, with your acceptance
limit. It sits in the scenario on **what it judges**, in one of four places:

| Where | What it judges | Examples |
| --- | --- | --- |
| `runtime.observers` | the run as a whole (the simulation) | `sim_speed`, `complete_record` |
| `vehicles[].observers` | a drone: what it did and what its stack produced | `collisions`, `estimate_ate`, `jerk` |
| `vehicles[].cameras.<name>.observers` | one camera of a drone | `camera_rate` |
| `missions[].observers` | the mission's progress | `goals_reached`, `time_to_goal` |

Most observers sit on a drone or one of its cameras. A mission takes only
the types about its own goals. Each run is judged once, after the drones
land, by TEVV's metrics service, the only judge: a mission and its drone over
the mission's **test segment** (its hand-over to its end, see
[topics.md](topics.md#the-lifecycle-of-a-run)), on that drone's data only;
a camera, the run, and a drone with no mission over the whole run.

```yaml
runtime:
  observers:
  - {id: speed, type: sim_speed, check: {min: 0.9}}                  # the simulator kept up
vehicles:
- name: Drone1
  observers:
  - {id: no-crash,  type: collisions,   check: {max: 0}}             # judged: at most 0
  - {id: accurate,  type: estimate_ate, check: {max: 1.0}}
  - {id: rpe,       type: estimate_rpe}                              # no check: reported, not judged
  - {id: clean-takeoff, type: collisions, phase: takeoff, check: {max: 0}}
  cameras:
    front:
      observers:
      - {id: rate, type: camera_rate, check: {min: 27}}              # this camera's real frame rate
missions:
- id: survey
  drone: Drone1
  ...
  observers:
  - {id: goals, type: goals_reached, check: {min: 1.0}}              # every point reached
```

- `id`: yours, unique where the observer sits. The same id on two drones is
  two observers.
- `type`: one of the types below. Each type says what it judges (the
  **Judges** column); on the wrong kind of thing it is refused, naming where
  it goes.
- `check`: one of `max` (at most), `min` (at least) or `eq` (equals), with
  your threshold. Leave it out to report the value without judging it.
- `phase`: `takeoff`, `mission` (the default) or `landing`: what part of the
  flight it judges. Only a mission's observers, and those of a drone that
  flies a mission, have one.

Add them in the dashboard (Observers step: the run, each drone with its
cameras, each mission; **Phase** picks the phase), or write them in the
scenario's `ScenarioSpec.yaml`. ScenarioLab, which authors the world, the
drones and the missions, keeps them as they are. A sensor profile's camera
may carry observers too: every drone with that profile gets them. A copy of
vehicle 1 made by a test's `vehicle_count` keeps its cameras' observers, so
"every camera of every drone at 27 Hz" holds for the copies too.

Before a run starts, TEVV refuses a **judged** observer the drone's stack or
the drone cannot feed: an `estimate_*` observer on a stack that estimates
nothing, `cloud_clearance` on a drone without a lidar, a plan observer on a
stack that declares no `Scoring(plan=...)`, an observer that needs a stack on
a drone with no mission. `./tevv interface <test>` shows the same problems
ahead of time.

A scenario written before observers sat on what they judge lists drone
checks on its missions; TEVV refuses those and says where they go.
`./tevv scenario migrate-observers <scenario>` moves them onto the drone
(and the run's onto `runtime`), keeping the file's comments.

## Take-off and landing

The stack flies its own take-off and landing ([stacks.md](stacks.md#the-run)),
so each mission records three segments, on ground truth:

| Phase | From | To |
| --- | --- | --- |
| `takeoff` | `takeoff_start` | `in_position` (or `takeoff_failed`) |
| `mission` | the hand-over (`control_handover`) | the mission's end (`run_end`), as before |
| `landing` | `landing_start` | `landed` (or `land_timeout`) |

An observer with `phase: takeoff` or `phase: landing` (on the mission, or on
its drone) is computed over that segment only. Any drone type can judge
take-off or landing except those about the goals or the plans:
`navigation_error`, `command_rate`, `replan_interval` and `plan_rate` judge
the mission phase only, as do the mission's own types. The `estimate_*` observers and the other observers of what
your stack publishes use that phase's window alone (`estimate_ate` fits its
own alignment over it). For example:

```yaml
- {id: vio-init,      type: time_to_first_estimate, phase: takeoff}
- {id: clean-takeoff, type: collisions,             phase: takeoff, check: {max: 0}}
- {id: soft-landing,  type: jerk,                   phase: landing}
```

A phased observer keeps its own column in the results, and its result
carries `phase`. A run with no such segment (a take-off that never
started) skips it, with the reason. Each mission's
`missions/<mission>.json` lists its `segments` (`takeoff`, `mission`,
`landing`, each with its start, end and how it ended) and `landing` (how the
landing ended). A `land_timeout` does not change the mission's verdict.

## How a run is judged

Two separate answers per mission:

- **ended**: how the mission stopped: `completed`, `timeout`, `stopped` or
  `error`.
- **verdict**: `PASS` when every observer with a check passes (the
  mission's, its drone's and its cameras') and the mission did not end in
  `error`; `FAIL` otherwise.

They are independent. A mission that ends `timeout` is still judged on what
its drone did: a planner that ran out of time fails `goals_reached`. A
mission that `completed` can still fail, e.g. it reached every point but hit
something.

| `ended` | When |
| --- | --- |
| `completed` | Every point reached, or `done` on `/tevv/<drone>/mission_status`. |
| `timeout` | The mission's `timeout_s` ran out (counted from its hand-over). |
| `stopped` | `./tevv stop <test>`, or an operator took the drone (changed its flight mode). |
| `takeoff_failed` | The stack's take-off did not reach position within 240 s, or raised. The mission never started. |
| `interface_error` | The stack's `interface.py` raised. |
| `error` | The flight failed, or the drone's stack never became ready (TEVV did not hand over). The other missions fly on. |

**The run** passes only if every mission passes and every observer outside
the missions passes too (the run's, a drone with no mission's). A run with no
observer that has a check is **not judged** (no verdict), unless a mission
ended in error, which fails it. A run's `ended` is its
worst mission's (`error`, then `interface_error`, `takeoff_failed`,
`stopped`, `timeout`, then `completed`).

An observer the run cannot measure (no geofence in the scenario, no estimate
published) is **skipped** with the reason, and does not fail the run.

## Observer types

Observers read only what TEVV owns: the simulator's record, ground truth,
the cameras' delivery, and the interface topics of the drone (its estimate,
command, plans and point cloud: in the table below, `/tevv/estimate` means
`/tevv/<drone>/estimate`, and so on). Nothing in them is specific to a
component, and a stack sets no limits of its own. A collision between two
drones counts for both.

**Safety**

| Type | Judges | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- | --- |
| `collisions` | drone | **Collisions**. Contacts with anything in flight. Settling onto the ground at spawn and touching down are set apart; a contact faster than 2 m/s counts wherever it happens. | count | at most | at most 0 |
| `geofence` | drone | **Geofence violations**. Entering a keep-out zone or leaving a keep-in zone in flight (the scenario's zones). | count | at most | at most 0 |
| `obstacle_clearance` | drone | **Obstacle clearance**. Closest approach to static geometry in flight, from a probe sphere around the vehicle. Nothing inside the probe radius passes any limit up to the radius; a collision is no clearance at all. | m | at least | at least 0.5 |

**Progress**

| Type | Judges | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- | --- |
| `area_coverage` | mission | **Area coverage**. Share of each coverage zone's ground that came within its footprint radius of the vehicle; the least-covered zone. | ratio | at least | at least 0.9 |
| `goals_reached` | mission | **Goals reached**. Share of the mission's goals the vehicle reached (within the course's advance radius); a path counts its last waypoint. | ratio | at least, equals | at least 1.0 |
| `path_length` | drone | **Path length**. Distance flown over the test segment (from the path's start or the hand-over to the run's end). | m | at most, at least | at most 100 |
| `test_duration` | mission | **Time taken**. Length of the test segment, from its start to the run's end. | s | at most, at least | at most 300 |

**Flight**

| Type | Judges | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- | --- |
| `cloud_clearance` | drone | **Clearance to sensed obstacles**. Closest approach to the recorded point cloud (/tevv/sensors/point_cloud) more than 0.5 m above the local ground. | m | at least | at least 0.3 |
| `command_rate` | drone | **Command rate**. Setpoints per second on /tevv/command after the first goal. | Hz | at least | at least 10 |
| `jerk` | drone | **Jerk**. RMS jerk of the ground-truth velocity: how smooth the flight was. | m/s^3 | at most | at most 50 |
| `navigation_error` | drone | **Autopilot position error**. The autopilot's own position estimate against ground truth, RMS. | m | at most | at most 2.0 |
| `path_efficiency` | mission | **Path efficiency**. Straight-line distance over distance flown, per goal reached; 1 is a straight line. | ratio | at least | at least 0.5 |
| `response_time` | mission | **Response time**. From the first goal to the vehicle moving 0.5 m. | s | at most | at most 5 |
| `speed_mean` | drone | **Mean speed**. Mean ground-truth speed over the segment. | m/s | at most, at least | at least 0.5 |
| `time_to_goal` | mission | **Time to goal**. Mean time from each goal being sent to it being reached, over the goals reached. | s | at most | at most 120 |
| `replan_interval` | drone | **Longest time without a new plan**. The longest gap between two of the stack's plans (its `Scoring(plan=...)` topic). | s | at most | at most 2.0 |
| `plan_rate` | drone | **Plan rate**. The stack's plans per second. | Hz | at least | at least 1.0 |
| `goal_to_plan` | mission | **Time from goal to plan**. From each new goal to the stack's first plan for it, mean. | s | at most | at most 2.0 |

**Estimate**

| Type | Judges | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- | --- |
| `estimate_ate` | drone | **Absolute trajectory error (ATE)**. RMS position error of /tevv/estimate after the best SE(3) fit onto ground truth. | m | at most | at most 2.0 |
| `estimate_ate_max` | drone | **Largest position error**. Largest position error of /tevv/estimate after alignment. | m | at most | at most 3.0 |
| `estimate_availability` | drone | **Estimate availability**. Share of the segment, after the first estimate, with an estimate less than 0.5 s old. | ratio | at least | at least 0.9 |
| `estimate_final_drift` | drone | **Final drift**. Position error at the end of the segment as a share of the distance flown. | % | at most | at most 5.0 |
| `estimate_rate` | drone | **Estimate rate**. Estimates per second on /tevv/estimate. | Hz | at least | at least 5.0 |
| `estimate_rpe` | drone | **Relative error per second (RPE)**. RMS error of the estimated motion over each 1 s window: local drift. | m | at most | at most 0.3 |
| `estimate_scale_error` | drone | **Scale error**. How far a Sim(3) fit's scale is from 1 (large for estimators that never fixed scale). | % | at most | at most 5.0 |
| `estimate_yaw_drift` | drone | **Yaw drift**. Heading error growth of /tevv/estimate. | deg/min | at most | at most 2.0 |
| `time_to_first_estimate` | drone | **Time to first estimate**. From the recording's first ground truth to the first /tevv/estimate. | s | at most | at most 60 |

**Sensors**

| Type | Judges | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- | --- |
| `camera_rate` | camera | **Camera rate**. New frames per second this camera delivered (distinct capture stamps; a re-published frame does not count), measured in its drone's bridge for 20 s from 10 s after the mission starts. | Hz | at least | at least 20 |

**Record**

| Type | Judges | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- | --- |
| `complete_record` | run | **Complete record**. The run's events are whole: the run ended and no sequence was lost (1), or not (0). | - | equals | equals 1 |
| `sim_speed` | run | **Simulation speed**. Simulated seconds per wall-clock second over the run; 1 is real time (lower under lockstep, by design). | x | at least | at least 0.9 |

`./tevv observers` lists the same catalog. New types are added to TEVV's
metrics service; ScenarioLab and the dashboard offer them without changes.

In the table, a "goal" is a mission point, and the "advance radius" is the
mission's reach radius (`reach_radius_m`).

## Running more than once

The number of runs is chosen when you run the test, not in the scenario:

```bash
./tevv run cross-demo --repeats 3                 # your test, tests/cross-demo.yaml
./tevv suite run local-planner --stack my-planner --repeats 3
```

The results table has one row per run per mission, so you see the spread.

## Where results are

```bash
./tevv results <test>               # summary and table
./tevv results <test> --format md   # the table as Markdown
./tevv results <test> --format csv  # the table as CSV
```

The table has one row per run per mission: `run`, `mission`, `drone`,
`stack` (who flew it), `ended`, `verdict`, `failed` (each failed observer),
`goals` (points reached), then one column per observer with the value it
was judged on: the mission's and its drone's by id, its cameras' as
`<camera>.<id>`, and on every row the run's as `run.<id>` and those of a
drone with no mission as `<drone>.<id>` (a name that clashes with a built-in
column gets ` (observer)`). A scenario with one mission gives one row per
run.

Per run, the metrics service's `evaluated.json` holds the run's verdict
(`null`: not judged), every observer result with its `owner` and
`owner_key` (`simulation`, `Drone1`, `Drone1/front`, `mission:survey`) and,
when it belongs to one, its `mission` and `drone`
(`{id, type, label, unit, value, check, passed, skipped, reason}`),
`checks` keyed `<owner key>/<id>`, `owners` (each owner's verdict), and
`missions`: each mission's verdict, failure reason and observers. The run's
folder under `generated/campaigns/<test>/runs/<run>/` holds:

| File | What |
| --- | --- |
| `bag/` | The first drone's recording (rosbag2). |
| `drones/<drone>/bag/` | Each other drone's recording. |
| `events.jsonl` | The simulator's event record. |
| `validation.json` | The recording's quality gates. |
| `metrics/<run>/missions/<mission>.json` | One per mission: how it ended, its take-off, mission and landing segments, its hand-over, each point. |
| `metrics/<run>/mission.json` | The run as a whole: every mission's summary, and one block spanning them all. |

## Recording valid, and viewed

Besides its verdict, each run says:

- **recording valid**: whether the recorded data passed its own quality
  gates (ground truth smooth and at least 30 Hz, the IMU at rest reading
  gravity, the autopilot healthy, and for camera runs image rates, stamps,
  stereo pairing and intrinsics). It does not change the verdict; it says
  whether the recording is clean enough to re-use. `validation.json` lists
  `failed_checks` with each gate's measurement. The dashboard marks such a
  run "recording invalid".
- **viewed**: the run was streamed to the dashboard's Sim tab (`view.json`
  in its folder). Only runs started from the dashboard are.

## Examples

`./tevv results multi-cross-three`: three drones, each flown by
`tevv-default`, crossing paths:

```console
[results] run      mission      drone   stack         ended      verdict  goals
[results] base-r1  diagonal     Drone3  tevv-default  completed  PASS     3/3
[results] base-r1  north-south  Drone2  tevv-default  completed  PASS     3/3
[results] base-r1  east-west    Drone1  tevv-default  completed  PASS     3/3
```

Two drones with two stacks (a test with `drones: {Drone1: my-vio, Drone2:
my-planner}`, here OpenVINS and SUPER): OpenVINS estimates while TEVV's
follower flies `survey`, and SUPER flies `cross` through it. Each row is one
mission, with the observers that mission lists:

```console
[results] run      mission  drone   stack       ended      verdict  goals  ...
[results] base-r1  cross    Drone2  my-planner  completed  PASS     3/3    ...
[results] base-r1  survey   Drone1  my-vio      completed  PASS     3/3    ...
```

Earlier single-mission runs, with OpenVINS and SUPER as stacks: OpenVINS on the yard
box reached an ATE of 0.20 m with 100 % availability; SUPER flew the yard
square's three points with 1.78 m clearance in about 20 s.

The detour test (`super-yard-detour`, one point behind the yard's
containers) shows two ways a mission fails:

- In one run SUPER stopped short of the containers, holding about 1.9 m
  clear, and did not find a way round in the 180 s budget: `ended: timeout`,
  `goals_reached` failed.
- In another it reached the point in 32 s, but the simulator's event record
  stopped 10 s into the flight. `no-crash` cannot be claimed from a record
  that saw nothing, so it fails with "the simulator's record stops … before
  the test segment ends", and `path` is reported with the same reason.
