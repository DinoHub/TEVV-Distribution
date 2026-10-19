# Observers and results

A scenario is a test: a list of **missions**, one per drone that flies.
Each mission's **observers** say what that mission is judged on. TEVV
provides the observer types; you pick the ones you want, as many as you
like, and give each an acceptance check. Each run is judged once, after the
drones land, by TEVV's metrics service: every mission over its own **test
segment** (its hand-over to its end), on its own drone's data only (see
[topics.md](topics.md#the-lifecycle-of-a-run)).

```yaml
missions:
  - id: survey
    drone: Drone1
    ...
    observers:
      - {id: no-crash,  type: collisions,      check: {max: 0}}     # judged: at most 0
      - {id: short,     type: path_length,     check: {max: 60}}    # "pass if the path flown is under 60 m"
      - {id: accurate,  type: estimate_ate,    check: {max: 1.0}}
      - {id: rpe,       type: estimate_rpe}                          # no check: reported, not judged
```

- `id`: yours; it is the observer's column in the results.
- `type`: one of the types below.
- `check`: one of `max` (at most), `min` (at least) or `eq` (equals), with
  your threshold. Leave it out to report the value without judging it.

Add them in the dashboard (Observers step, per mission: the one thing the
dashboard edits), or write them under each mission in the scenario's
`ScenarioSpec.yaml`. ScenarioLab, which authors the missions, keeps them as
they are.

Before a run starts, TEVV refuses a mission whose **judged** observers its
stack or drone cannot feed: an `estimate_*` observer on a stack that
estimates nothing, `cloud_clearance` on a drone without a lidar. `./tevv
interface <test>` shows the same problems ahead of time.

## How a run is judged

Two separate answers per mission:

- **ended**: how the mission stopped: `completed`, `timeout`, `stopped` or
  `error`.
- **verdict**: `PASS` when every observer of the mission with a check
  passes and the mission did not end in `error`; `FAIL` otherwise.

They are independent. A mission that ends `timeout` is still judged on what
its drone did: a planner that ran out of time fails `goals_reached`. A
mission that `completed` can still fail, e.g. it reached every point but hit
something.

| `ended` | When |
| --- | --- |
| `completed` | Every point reached, or `done` on `/tevv/<drone>/mission_status`. |
| `timeout` | The mission's `timeout_s` ran out (counted from its hand-over). |
| `stopped` | `./tevv stop <test>`, or an operator took the drone (changed its flight mode). |
| `error` | The flight failed, or the drone's stack never became ready (TEVV did not hand over). The other missions fly on. |

**The run** passes only if every mission passes. A run's `ended` is its
worst mission's (`error`, then `stopped`, then `timeout`, then
`completed`).

An observer the run cannot measure (no geofence in the scenario, no estimate
published) is **skipped** with the reason, and does not fail the run.

## Observer types

Observers read only what TEVV owns: the simulator's record, ground truth,
and the interface topics of the mission's drone (its estimate, command and
point cloud: in the table below, `/tevv/estimate` means
`/tevv/<drone>/estimate`, and so on). Nothing in them is specific to a
component. A collision between two drones counts for both missions.

**Safety**

| Type | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- |
| `collisions` | **Collisions**. Contacts with anything in flight. Settling onto the ground at spawn and touching down are set apart; a contact faster than 2 m/s counts wherever it happens. | count | at most | at most 0 |
| `geofence` | **Geofence violations**. Entering a keep-out zone or leaving a keep-in zone in flight (the scenario's zones). | count | at most | at most 0 |
| `obstacle_clearance` | **Obstacle clearance**. Closest approach to static geometry in flight, from a probe sphere around the vehicle. Nothing inside the probe radius passes any limit up to the radius; a collision is no clearance at all. | m | at least | at least 0.5 |

**Progress**

| Type | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- |
| `area_coverage` | **Area coverage**. Share of each coverage zone's ground that came within its footprint radius of the vehicle; the least-covered zone. | ratio | at least | at least 0.9 |
| `goals_reached` | **Goals reached**. Share of the mission's goals the vehicle reached (within the course's advance radius); a path counts its last waypoint. | ratio | at least, equals | at least 1.0 |
| `path_length` | **Path length**. Distance flown over the test segment (from the path's start or the hand-over to the run's end). | m | at most, at least | at most 100 |
| `test_duration` | **Time taken**. Length of the test segment, from its start to the run's end. | s | at most, at least | at most 300 |

**Flight**

| Type | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- |
| `cloud_clearance` | **Clearance to sensed obstacles**. Closest approach to the recorded point cloud (/tevv/sensors/point_cloud) more than 0.5 m above the local ground. | m | at least | at least 0.3 |
| `command_rate` | **Command rate**. Setpoints per second on /tevv/command after the first goal. | Hz | at least | at least 10 |
| `jerk` | **Jerk**. RMS jerk of the ground-truth velocity: how smooth the flight was. | m/s^3 | at most | at most 50 |
| `navigation_error` | **Autopilot position error**. The autopilot's own position estimate against ground truth, RMS. | m | at most | at most 2.0 |
| `path_efficiency` | **Path efficiency**. Straight-line distance over distance flown, per goal reached; 1 is a straight line. | ratio | at least | at least 0.5 |
| `response_time` | **Response time**. From the first goal to the vehicle moving 0.5 m. | s | at most | at most 5 |
| `speed_mean` | **Mean speed**. Mean ground-truth speed over the segment. | m/s | at most, at least | at least 0.5 |
| `time_to_goal` | **Time to goal**. Mean time from each goal being sent to it being reached, over the goals reached. | s | at most | at most 120 |

**Estimate**

| Type | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- |
| `estimate_ate` | **Absolute trajectory error (ATE)**. RMS position error of /tevv/estimate after the best SE(3) fit onto ground truth. | m | at most | at most 2.0 |
| `estimate_ate_max` | **Largest position error**. Largest position error of /tevv/estimate after alignment. | m | at most | at most 3.0 |
| `estimate_availability` | **Estimate availability**. Share of the segment, after the first estimate, with an estimate less than 0.5 s old. | ratio | at least | at least 0.9 |
| `estimate_final_drift` | **Final drift**. Position error at the end of the segment as a share of the distance flown. | % | at most | at most 5.0 |
| `estimate_rate` | **Estimate rate**. Estimates per second on /tevv/estimate. | Hz | at least | at least 5.0 |
| `estimate_rpe` | **Relative error per second (RPE)**. RMS error of the estimated motion over each 1 s window: local drift. | m | at most | at most 0.3 |
| `estimate_scale_error` | **Scale error**. How far a Sim(3) fit's scale is from 1 (large for estimators that never fixed scale). | % | at most | at most 5.0 |
| `estimate_yaw_drift` | **Yaw drift**. Heading error growth of /tevv/estimate. | deg/min | at most | at most 2.0 |
| `time_to_first_estimate` | **Time to first estimate**. From the recording's first ground truth to the first /tevv/estimate. | s | at most | at most 60 |

**Record**

| Type | What it measures | Unit | Checks | Default |
| --- | --- | --- | --- | --- |
| `complete_record` | **Complete record**. The run's events are whole: the run ended and no sequence was lost (1), or not (0). | - | equals | equals 1 |

`./tevv observers` lists the same catalog. New types are added to TEVV's
metrics service; ScenarioLab and the dashboard offer them without changes.

In the table, a "goal" is a mission point, and the "advance radius" is the
mission's reach radius (`reach_radius_m`).

## Running more than once

The number of runs is chosen when you run the test, not in the scenario:

```bash
./tevv run tests/cross-demo.yaml --repeats 3
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
`goals` (points reached), then one column per observer id with the value it
was judged on (an id that clashes with a built-in column gets
` (observer)`). A scenario with one mission gives one row per run.

Per run, the metrics service's `evaluated.json` holds the run's verdict,
every observer result tagged with its `mission` and `drone`
(`{id, type, label, unit, value, check, passed, skipped, reason}`), and
`missions`: each mission's verdict, failure reason and observers. The run's
folder under `generated/campaigns/<test>/runs/<run>/` holds:

| File | What |
| --- | --- |
| `bag/` | The first drone's recording (rosbag2). |
| `drones/<drone>/bag/` | Each other drone's recording. |
| `events.jsonl` | The simulator's event record. |
| `validation.json` | The recording's quality gates. |
| `metrics/<run>/missions/<mission>.json` | One per mission: how it ended, its segment, its hand-over, each point. |
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

Two drones with two stacks (a test with `drones: {Drone1: vio-openvins,
Drone2: super-planner}`): OpenVINS estimates while TEVV's follower flies
`survey`, and SUPER flies `cross` through it. Each row is one mission,
with the observers that mission lists:

```console
[results] run      mission  drone   stack          ended      verdict  goals  ...
[results] base-r1  cross    Drone2  super-planner  completed  PASS     3/3    ...
[results] base-r1  survey   Drone1  vio-openvins   completed  PASS     3/3    ...
```

Earlier single-mission runs, from the worked examples: OpenVINS on the yard
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
