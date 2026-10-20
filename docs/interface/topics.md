# The TEVV interface: what a drone offers, what a stack sends back

TEVV gives every stack the **same fixed interface**: one set of ROS 2
topics with fixed names, the same for every drone, under that drone's
namespace `/tevv/<drone>/...` (below, `/tevv/<d>/`). Your stack's
`interface.py` reads them (`self.gt_odom`, `self.imu`, ...) and wires them to
your software's own names ([stacks.md](stacks.md)); `passthrough()` gives
your software these names as they are. `./tevv interface <test> --drone <d>`
prints what one drone offers, with rates and sizes.

## Frames

| Frame | What it is |
| --- | --- |
| `odom` | Your drone's world frame. ENU (x east, y north, z up). It is fixed at that drone's spawn point; the drone may settle onto the ground below it, so z on the ground is not necessarily 0. Ground truth, the point cloud, the mission and position commands all use it. Each drone has its own `odom`. |
| `base_link` | The vehicle body. FLU (x forward, y left, z up). Ground truth and your estimate are of this frame; the IMU is mounted at it with the same axes. |
| `<camera>_optical` | A camera's optical frame (z forward, x right, y down). Its mount on `base_link` is in its calibration (`self.camera(...).calibration["T_base_cam"]`). |

## TEVV → your stack

Only what your stack lists in `needs` is available, plus the mission and the
clock, which always come. Message types are standard ROS 2 Humble types.

### Ground truth: `/tevv/<d>/gt/*`

What the simulator knows to be true. A planner or controller may use it as
its state; an estimator must not (it is what the estimator is scored against).

| Topic | Type | Frame | `needs` |
| --- | --- | --- | --- |
| `/tevv/<d>/gt/odom` | `nav_msgs/msg/Odometry` | `odom` → `base_link`; pose and twist | `ground_truth` |

### Sensors: `/tevv/<d>/sensors/*`

What the drone's simulated sensors measure, as the scenario configures them.
A run refuses a drone that lacks a sensor your stack needs, naming what it has.

| Topic | Type | Frame | `needs` |
| --- | --- | --- | --- |
| `/tevv/<d>/sensors/imu` | `sensor_msgs/msg/Imu` | at `base_link`, FLU axes (`T_base_imu` is identity) | `imu` |
| `/tevv/<d>/sensors/gnss` | `sensor_msgs/msg/NavSatFix` | | `gnss` |
| `/tevv/<d>/sensors/lidar/points` | `sensor_msgs/msg/PointCloud2` | the lidar's own frame | `lidar` |
| `/tevv/<d>/sensors/point_cloud` | `sensor_msgs/msg/PointCloud2` | `odom` (registered with ground truth) | `point_cloud` |
| `/tevv/<d>/sensors/<name>/image_raw` | `sensor_msgs/msg/Image` (`bgr8`) | `<name>_optical` | `camera_primary`, `camera:<name>` |
| `/tevv/<d>/sensors/<name>/camera_info` | `sensor_msgs/msg/CameraInfo` | `<name>_optical` | (with its image) |

`stereo_primary` or `stereo:<name>` gives you both cameras of a stereo pair
(same stamps, rectified). Camera `<name>`s come from your drone in the scenario; `./tevv interface`
lists the ones a drone has.

The lidar, unless the scenario configures another, is an Ouster OS1-64 as the
simulator models it: 64 channels on the real vertical table (about ±16.6°),
2048 points per channel per rotation, 0.5 to 120 m, with intensity and noise.
Each message is one whole 360° sweep, stamped when the sweep completed; the
per-point `time` field is each point's offset from that stamp (≤ 0), for
motion correction. The simulator renders the lidar in the GPU, so the sweep
rate follows its frame rate: about 6 to 8 sweeps per second on a large level
rather than the sensor's 10.

### The mission: `/tevv/<d>/mission/*` and `/tevv/<d>/control_state`

Always published, all latched, all in `odom`.

| Topic | Type | What |
| --- | --- | --- |
| `/tevv/<d>/mission/waypoints` | `nav_msgs/msg/Path` | Every point of your drone's mission, in order. Published once, at hand-over. |
| `/tevv/<d>/mission/next` | `geometry_msgs/msg/PoseStamped` | The point to reach next. When the drone comes within the mission's reach radius of it, the next point is published. |
| `/tevv/<d>/control_state` | `std_msgs/msg/String` | Who flies the drone: `tevv` or `external` (your stack). |

The points are where the drone must go. How it gets there (straight lines,
around obstacles, at what speed) is up to the stack that flies it.

### Always: `/clock`, `/tf`, `/tf_static`

The simulator's clock and TF tree.

## Your stack → TEVV

Four outputs, and nothing else leaves your stack's network.

| Output | Type | SDK | What TEVV does with it |
| --- | --- | --- | --- |
| command | `mavros_msgs/msg/PositionTarget` | `command_from`, `send_*`, `follow_waypoints` | Passes it to the autopilot, while `control_state` is `external`. See [Commands](#commands). |
| estimate | `nav_msgs/msg/Odometry` | `estimate_from`, `send_estimate` | Scores it against ground truth: the pose of `base_link` (FLU) in any fixed world frame of yours (TEVV aligns your world to `odom` before it scores). Stamp each estimate with the sim time of the measurement it was computed from. |
| mission status | `std_msgs/msg/String` | `report_done`, `status_from` | `done` ends your drone's mission as `completed`. |
| debug | any | `debug("name", msg)` | Recorded with the run on `/tevv/<d>/debug/<name>` and shown in Monitor; never acted on. |

Your `ready` topics are also carried out, so TEVV can see when your stack is up.

### Commands

`/tevv/<d>/command` takes a MAVROS `PositionTarget`, so any setpoint MAVROS
takes, with its `type_mask`:

- `coordinate_frame: 1` (`FRAME_LOCAL_NED`, MAVROS's name for its ENU local
  frame): positions, velocities and accelerations in `odom`. TEVV moves a
  position from `odom` to the autopilot's frame; velocities and
  accelerations pass as they are (the axes are the same).
- `coordinate_frame: 8` (`FRAME_BODY_NED`): body-frame velocities, passed as
  they are.

TEVV runs the autopilot (PX4 or ArduPilot SITL, or SimpleFlight, as your
stack chose). Your containers never arm it, change its mode, or talk
MAVLink: they send setpoints, and the interface passes them to the autopilot
while the mission runs. Take-off and landing are `interface.py`'s steps,
through `d.fc` ([stacks.md](stacks.md#the-run)). On SimpleFlight each
setpoint becomes a velocity command (a position is flown with a proportional
term toward it). If your commands stop for more than **1 s**, the drone holds
where it is until they resume.

## The lifecycle of a run

A scenario's test is a list of **missions**, at most one per drone. Each
mission is a list of points for one drone, with a reach radius and a time
budget. A drone without a mission stays on the ground. The drone's **stack**
flies it: the test names it ([tests.md](tests.md)), else `tevv-default`.

A mission's points are in metres, ENU, relative to the ground under the
**first** drone's start, the same frame for every mission. TEVV gives each
drone its points in that drone's own `odom`.

Before anything flies, TEVV starts the simulator and each drone's autopilot
(the one its stack chose), then each drone's stack: its containers and its
interface container, which runs `interface.py`'s `setup()`. Then every
mission runs at the same time. The stack flies it, take-off and landing
included; TEVV referees each on its own (it says the phase, publishes the
mission and judges it on ground truth, and flies nothing):

1. **Take-off** (`takeoff_start`): the stack's `takeoff(d)` step climbs to
   the mission's start altitude (`/tevv/<d>/control_state` is `tevv`). It
   ends at `in_position`; not within 240 s, the mission ends
   `takeoff_failed`.
2. TEVV waits for the stack's `ready` topics (and, for a stack that
   estimates, its first estimate). If they do not come within 240 s, the
   mission ends `error` without a hand-over and the drone lands. The other
   missions go on.
3. **Segment start** (`control_handover`): TEVV publishes
   `/tevv/<d>/mission/waypoints` and the first `/tevv/<d>/mission/next`,
   and sets `/tevv/<d>/control_state` to `external`; your
   `/tevv/<d>/command` now reaches the autopilot.
4. A point counts as reached when ground truth comes within the mission's
   **reach radius** (`reach_radius_m`, *Reach radius m* in ScenarioLab;
   default 1 m). TEVV then publishes the next point on `mission/next`.
5. **Segment end** (`run_end`), at the first of: every point reached
   (`completed`), `done` on `/tevv/<d>/mission_status` (`completed`), the
   time budget `timeout_s` from the hand-over (`timeout`), the run being
   stopped or an operator taking the drone (`stopped`), or `interface.py`
   raising (`interface_error`).
   `/tevv/<d>/control_state` goes back to `tevv` (`control_reclaimed`), and
   your command no longer reaches the autopilot.
6. **Landing** (`landing_start`): the stack's `land(d)` step lands the
   drone. It ends at `landed`; not within 60 s, `land_timeout` is recorded
   and the verdict is unchanged.

Each mission has its own **test segment**, from its hand-over to its end.
Its observers are computed over that segment, on its own drone's data.
Take-off and landing are segments of their own, judged only by observers
with `phase: takeoff` or `phase: landing`
([results.md](results.md#take-off-and-landing)). The run ends when every
mission has ended; TEVV then stops every stack and then its own side.

How a mission **ended** is separate from whether it **passed**, and the run
passes only if every mission passes: see [results.md](results.md).
