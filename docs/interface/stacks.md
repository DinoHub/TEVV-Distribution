# Stacks: who flies a drone, and how

A **stack** is a folder with one Python file, its customer interface:

```
stacks/<id>/
  interface.py        one class on the TEVV SDK: autopilot, needs, containers, setup()
  files/              optional: config your containers read (at /stack/files)
  requirements.txt    optional: Python packages interface.py imports
```

TEVV ships three stacks: `tevv-default` (TEVV's waypoint follower on AirSim
SimpleFlight), `tevv-default-px4` and `tevv-default-ardupilot` (the same
follower on TEVV's PX4 or ArduPilot SITL). A folder of the same name in
`stacks/` replaces a built-in.

```bash
./tevv stack list                 # every stack, built-ins first
./tevv stack show super-planner   # its declarations and its interface.py
./tevv stack check super-planner  # can it fly a mission?
./tevv stack init my-planner --autopilot px4 --container me/planner:1   # a skeleton to edit
```

## A whole example

SUPER, a local planner, flying its drone's mission
([stacks/super-planner](../../stacks/super-planner/interface.py)):

```python
from tevv import Container, Interface

class SuperPlanner(Interface):
    name = "SUPER local planner"
    autopilot = "px4"                                # what the drone flies on
    needs = ["ground_truth", "point_cloud"]          # what the drone must offer
    containers = {                                   # your software, unmodified
        "super": Container(
            image="dhdevspace/auto_mns:super_runtime-ms.1-cyclone",
            command="... ros2 run super_planner fsm_node --ros-args "
                    "-p config_name:=/stack/files/config/click.yaml"),
    }
    ready = ["/planner_state"]                       # hand over once this is up

    def setup(self):                                 # TEVV's topics <-> SUPER's
        self.forward(self.gt_odom, "/px4vision_custom_0/mavros/local_position/odom")
        self.forward(self.point_cloud, "/px4vision_custom_0/lidar")
        self.forward(self.next_waypoint, "/goal")
        self.command_from("/px4vision_custom_0/mavros/setpoint_raw/local", convert=velocity_command)
```

## How it runs

```
 TEVV side (the drone's domain)            interface.py (one container per drone)          your stack's domain
 ──────────────────────────────            ──────────────────────────────────────          ───────────────────
 ground truth, sensors, mission  ──►  self.gt_odom, self.imu, ...  ──forward / on──►  your topics, any names
 /tevv/<drone>/command (gated)   ◄──  command_from / send_*        ◄──────────────    your setpoints
 /tevv/<drone>/estimate          ◄──  estimate_from / send_estimate◄──────────────    your odometry
 /tevv/<drone>/debug/<name>      ◄──  self.debug(...)  (recorded, shown in Monitor)
```

For each drone with a mission, TEVV starts its stack's `containers` on their
own Docker network and ROS 2 domain, and one **interface container** that
runs your `interface.py` on both sides. Your software never sees TEVV's
names and TEVV never sees yours; `interface.py` is the only code that
touches both, and it is plain Python you own. The file is mounted, not built
into an image: edit it and run again.

A stack used on two drones runs twice, once per drone, each seeing only its
own drone.

## The declarations (class attributes)

TEVV reads these **without running your file**, so write them as plain
values: strings, lists, dicts, `Container(...)` and `Autopilot(...)` with
plain arguments. An expression (`os.environ[...]`, a function call) is
refused with the line that has it.

| Attribute | Default | What |
| --- | --- | --- |
| `name`, `description` | the class name, empty | For people: shown by `stack list` and the dashboard. |
| `autopilot` | `"simpleflight"` | `"simpleflight"`, `"px4"` or `"ardupilot"`, or `Autopilot(...)` (below). |
| `needs` | `[]` (`["ground_truth"]` for `TevvDefault`) | What the drone must offer: `ground_truth`, `imu`, `gnss`, `lidar`, `point_cloud`, `camera_primary`, `camera:<name>`, `stereo_primary`, `stereo:<name>`. A run refuses a drone that lacks one, naming what it has. |
| `containers` | `{}` | `name: Container(...)`, started before `setup()` runs. |
| `ready` | `[]` | Topics on your side that TEVV waits for, after take-off, before it hands the drone over (up to 240 s). |

### Choosing an autopilot

| `autopilot =` | What TEVV starts for the drone | How TEVV takes off, holds and lands |
| --- | --- | --- |
| `"simpleflight"` | nothing: AirSim's built-in controller | the bridge's AirSim API (velocity commands) |
| `"px4"` | TEVV's pinned PX4 SITL, and MAVROS in the drone's bridge | MAVROS, OFFBOARD |
| `"ardupilot"` | TEVV's pinned ArduPilot SITL, and MAVROS | MAVROS, GUIDED |

Your command is the same on every autopilot (a `PositionTarget`), so a stack
moves to another autopilot by changing this one line.

```python
autopilot = Autopilot("ardupilot", params={"WPNAV_SPEED": 500})   # SITL parameters
autopilot = Autopilot("px4", image="me/px4-custom:1")             # your own SITL image (advanced)
```

`params` go to that drone's SITL (ArduPilot). `image` replaces TEVV's SITL
image for that drone; it must keep TEVV's SITL contract, and `stack check`
warns that results are then not comparable with TEVV's pinned autopilot.

One scenario can mix autopilots per drone, with one exception: PX4 and
ArduPilot cannot fly together (AirSim has one clock: ArduPilot needs it
stepped, PX4 free-running). SimpleFlight mixes with either. A drone with no
mission has no stack and stays parked on SimpleFlight.

### Containers

```python
Container(image="me/planner:1",            # required
          command="ros2 launch my_pkg my.launch.py",   # a string runs in bash -lc; a list is exec form
          env={"MY_SETTING": "1"},
          gpu=True,                         # give it the GPU
          entrypoint=None, working_dir=None,
          run_as="platform")                # platform: the host user, HOME=/tmp; "image": the image's own user
```

Every container gets:

- `/stack` (read-only): your stack's folder (so `files/` is `/stack/files`);
- `/shared` (read-write): a folder shared with `interface.py`, kept with the
  run (`outputs/components/<id>/shared/` in the run's stack folder): write a
  config there that your software waits for (see
  [vio-openvins](../../stacks/vio-openvins/interface.py));
- CycloneDDS (`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`) on your stack's own
  domain. Install `ros-humble-rmw-cyclonedds-cpp` in your images; do not set
  `ROS_DOMAIN_ID` or `CYCLONEDDS_URI`.

Use sim time (`use_sim_time: true`); `/clock`, `/tf` and `/tf_static` are
always on your side.

## setup(): wiring

`setup()` runs once, in the interface container, after your containers have
started. Anything Python can do is allowed there.

### Inputs (TEVV's side)

Each is an `Input` with `.name` (its TEVV name, `/tevv/<drone>/...`), `.type`
and `.calibration` (a camera's `K`, `D`, size, `T_base_cam`; a stereo pair's
baseline). Only what `needs` lists is available, plus the mission.

| Attribute | Type | Role |
| --- | --- | --- |
| `self.gt_odom` | `nav_msgs/Odometry` (`odom` → `base_link`) | `ground_truth` |
| `self.imu` | `sensor_msgs/Imu` (at `base_link`, FLU) | `imu` |
| `self.gnss` | `sensor_msgs/NavSatFix` | `gnss` |
| `self.lidar` | `sensor_msgs/PointCloud2` (sensor frame) | `lidar` |
| `self.point_cloud` | `sensor_msgs/PointCloud2` (registered, `odom`) | `point_cloud` |
| `self.camera()` / `self.camera("front")` | `sensor_msgs/Image` + `CameraInfo` | `camera_primary` / `camera:front` |
| `self.stereo` / `self.stereo_pair("front")` | `.left` and `.right` cameras | `stereo_primary` / `stereo:front` |
| `self.waypoints` | `nav_msgs/Path`, latched | the mission's points |
| `self.next_waypoint` | `geometry_msgs/PoseStamped`, latched | the point to reach next |
| `self.control_state` | `std_msgs/String`, latched | `tevv` or `external` (you have control) |

Plus `self.drone` (its name), `self.mission` (id, points, reach radius,
speed, time budget), `self.interface` (everything, with types, frames, QoS
and rates), `self.shared` and `self.folder` (paths), `self.node` (an rclpy
node on your side) and `self.log`.

`./tevv interface <test> --drone <d>` prints exactly what a drone offers;
the full catalog is in [topics.md](topics.md).

### Wiring helpers

| Call | What |
| --- | --- |
| `forward(src, "/topic", convert=fn, frame_id=..., encoding=..., max_hz=...)` | Republish an input on your side. `convert` turns each message into anything (any type). A camera also publishes its `camera_info` (beside the image, or `info=`). |
| `forward(self.stereo, left="/cam0/image_raw", right="/cam1/image_raw")` | Both cameras of a pair. |
| `on(src, callback)` | Your function gets each message (a pair gets `callback(left, right)`). |
| `subscribe("/topic", MsgType, callback)` / `publisher("/topic", MsgType)` | Your own topics on your side. |
| `command_from("/topic", type=None, frame="ENU", convert=fn)` | Your command, sent to TEVV. `PositionTarget`, `Twist(Stamped)` (`frame="FLU"` for body velocities), `PoseStamped` or `Odometry`; the type is found from the topic. |
| `send_position(x, y, z, yaw=None)` / `send_velocity(vx, vy, vz, yaw_rate=None, frame="world")` / `send_command(msg)` | Fly from your own code. |
| `follow_waypoints(speed_mps=None)` | Let TEVV's follower fly the mission. |
| `estimate_from("/topic", body="base_link", world="ENU")` / `send_estimate(odom)` | Your pose estimate, scored. `body` may be a camera (`"camera:front"`, `"stereo_primary.left"`). |
| `status_from("/topic", done="done")` / `report_done()` | End the mission early. |
| `passthrough()` | Give your software TEVV's names as they are, and read its `/tevv/<drone>/command`, `estimate` and `mission_status`. |
| `debug("name", msg)` | Any message on `/tevv/<drone>/debug/<name>`: recorded, shown in Monitor, never acted on. |
| `describe()` | Log what this drone offers. |

**Exactly one thing flies the drone**: your stack (`command_from`,
`send_*`, `passthrough`) or TEVV's follower (`follow_waypoints`). `stack
check` refuses a stack that does both or neither. To fly the follower and run
your estimator beside it, subclass `TevvDefault`:

```python
from tevv import Container, TevvDefault

class MyVio(TevvDefault):                 # TEVV flies on SimpleFlight
    needs = ["ground_truth", "stereo_primary", "imu"]
    containers = {"vio": Container(image="me/vio:1")}

    def setup(self):
        super().setup()                   # follow_waypoints()
        self.forward(self.stereo, left="/cam0/image_raw", right="/cam1/image_raw")
        self.forward(self.imu, "/imu0")
        self.estimate_from("/vio/odom")
```

## What stays fixed

Your stack cannot publish on the drone's side except through the four
outputs (`command`, `estimate`, `mission_status`, `debug/*`), cannot fly
outside the hand-over (TEVV only passes your command while
`control_state` is `external`, and holds the drone after 1 s without one),
and cannot change the mission or its observers. That is what makes a TEVV
result comparable between stacks.

## Editing and debugging

- **Edit and rerun.** `interface.py`, `files/` and `requirements.txt` are
  read at each run; nothing is built. Your containers' images are yours to
  build, as before.
- **Print.** `print()` and `self.log.info(...)` go to the interface
  container's log: `./tevv logs <test> --drone <d>` (`-f` follows a run in
  progress); after the run it is kept in the run's stack folder,
  `outputs/components/<id>/logs/interface.log`, beside each of your
  containers' logs (`--container <name>`).
- **Debug topics.** `self.debug("goal_received", msg)` publishes on
  `/tevv/<drone>/debug/goal_received`, recorded with the run and shown in
  Monitor (Lichtblick). Write the name as a literal: TEVV reads the names
  from the file before the run to know what to record.
- **Watch.** `./tevv watch <test>` in a second terminal, while the test
  runs: each save restarts only that drone's interface container (the
  simulator and your containers stay up), and TEVV's follower carries on from
  the point TEVV says is next. A restart mid-flight spoils that run's scores;
  it is for iterating.
- **Errors.** An exception in `setup()` or a callback ends the mission
  `interface_error`, with the reason in the results and the traceback in the
  log. The other drones fly on.
- **Python packages.** `requirements.txt` is installed into the interface
  container when it starts.
- **Your editor.** `./tevv sdk` copies the SDK (the version TEVV runs) into
  `.tevv/sdk`; add it to your editor's Python path for autocomplete.
