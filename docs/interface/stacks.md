# Stacks: who flies a drone, and how

A **stack** is a folder with one Python file, its customer interface:

```
stacks/<id>/
  interface.py        one class on the TEVV SDK: autopilot, needs, containers, setup()
  files/              optional: config your containers read (at /stack/files)
  requirements.txt    optional: Python packages interface.py imports
```

TEVV ships three stacks, built in: `tevv-default` (TEVV's waypoint follower
on AirSim SimpleFlight), `tevv-default-px4` and `tevv-default-ardupilot` (the
same follower on TEVV's PX4 or ArduPilot SITL). All three are the same
`TevvDefault` class with the default take-off and landing; only the autopilot
differs. Every other stack is yours:
`stacks/` is your folder (git ignores it), and a folder there named like a
built-in replaces it.

```bash
./tevv stack init my-planner --autopilot px4 --container me/planner:1   # a skeleton to edit
./tevv stack list                 # every stack, built-ins first
./tevv stack show my-planner      # its declarations and its interface.py
./tevv stack check my-planner     # can it fly a mission?
```

## A whole example

Your local planner flying its drone's mission. Say it is SUPER, in your own
image, with its config in `stacks/my-planner/files/config/planner.yaml`; this
is the whole of `stacks/my-planner/interface.py`:

```python
from tevv import Container, Interface

def velocity_command(msg):                           # your PositionTarget -> TEVV's command
    from mavros_msgs.msg import PositionTarget as PT
    out = PT(coordinate_frame=PT.FRAME_LOCAL_NED,    # MAVROS's name for its ENU frame
             type_mask=PT.IGNORE_PX | PT.IGNORE_PY | PT.IGNORE_PZ | PT.IGNORE_AFX | PT.IGNORE_AFY
                       | PT.IGNORE_AFZ | PT.IGNORE_YAW_RATE)
    out.header.frame_id = "odom"
    out.velocity, out.yaw = msg.velocity, msg.yaw
    return out

class MyPlanner(Interface):
    name = "SUPER local planner"
    autopilot = "px4"                                # what the drone flies on
    needs = ["ground_truth", "point_cloud"]          # what the drone must offer
    containers = {                                   # your software, unmodified
        "planner": Container(
            image="me/super-planner:1",
            command="ros2 run super_planner fsm_node --ros-args "
                    "-p config_name:=/stack/files/config/planner.yaml"),
    }
    ready = ["/planner_state"]                       # the mission starts once this is up

    def setup(self):                                 # TEVV's topics <-> your planner's
        self.forward(self.gt_odom, "/odom")
        self.forward(self.point_cloud, "/lidar")
        self.forward(self.next_waypoint, "/goal")
        self.command_from("/setpoint_raw/local", convert=velocity_command)
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
values: strings, lists, dicts, `Container(...)`, `Autopilot(...)`,
`Network(...)`, `Parameter(...)`, `Messages(...)`, `Scoring(...)` and
`Lockstep(...)` with plain arguments. An expression (`os.environ[...]`, a
function call, an f-string, a module constant) is refused with the line that
has it.

| Attribute | Default | What |
| --- | --- | --- |
| `name`, `description` | the class name, empty | For people: shown by `stack list` and the dashboard. |
| `autopilot` | `"simpleflight"` | `"simpleflight"`, `"px4"` or `"ardupilot"`, or `Autopilot(...)` (below). |
| `needs` | `[]` (`["ground_truth"]` for `TevvDefault`) | What the drone must offer: `ground_truth`, `imu`, `gnss`, `lidar`, `point_cloud`, `camera_primary`, `camera:<name>`, `stereo_primary`, `stereo:<name>`. A run refuses a drone that lacks one, naming what it has. |
| `containers` | `{}` | `name: Container(...)`, started before `setup()` runs. |
| `ready` | `[]` | Topics on your side that TEVV waits for, after take-off, before the mission starts (up to 240 s). |
| `drones` | `"one"` | `"one"`: an instance flies one drone (a test naming it for two drones runs it twice). `"many"`: one instance flies every drone a test gives it ([below](#one-stack-many-drones)). |
| `network` | `None` | `Network("<docker network>", domain=<ROS_DOMAIN_ID>)`: a stack you start yourself, in your own Docker network; declare no `containers` ([below](#a-stack-you-start-yourself)). |
| `parameters` | `{}` | `name: Parameter(default, ...)`: settings a test sets or sweeps ([below](#parameters)). |
| `messages` | `[]` | `Messages(image, packages=[...])`: your own ROS message types ([below](#your-own-message-types)). |
| `watch` | `[]` | Outputs of your software, of any type, for [the live check](#the-live-check) to judge: topics, or `Watch(topic, min_hz=...)` ([below](#watching-outputs-of-any-type)). |
| `scoring` | `None` | `Scoring(plan=..., checks={...})`: your plan's freshness and your own pass/fail limits ([below](#scoring-your-own-outputs)). |
| `lockstep` | `None` | `Lockstep(ack_on=... \| status_topic=..., timeout_ms=...)`: the simulation waits for your stack ([below](#sim-time-lockstep)). |

### Choosing an autopilot

| `autopilot =` | What TEVV starts for the drone | How `d.fc` ([The run](#the-run)) and your command reach it |
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
`d.fc` and the default take-off and landing work on it unchanged.

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
          run_as="platform",                # platform: the host user, HOME=/tmp; "image": the image's own user
          ports=["8080:80", "9000:9000/udp"],          # HOST:CONTAINER, optionally /udp
          volumes={"engines": "/engines"},              # a named volume that outlives a run
          once=False,                       # an init step: runs once, done at exit 0, never restarted
          fcu=False)                        # a second MAVLink link to the autopilot (see below)
```

`once=True` marks an init step, such as a container that downloads a model or
builds an engine into a volume and then exits: TEVV does not restart it, and
the live check does not count its clean exit as a crash. Discover accepts an
extra container that exits 0 while the main one keeps running, and `stack
wire` writes `once=True` for it.

Every container gets:

- `/stack` (read-only): your stack's folder (so `files/` is `/stack/files`);
- `/shared` (read-write): a folder shared with `interface.py`, kept with the
  run (`outputs/components/<id>/shared/` in the run's stack folder): write a
  config there that your software waits for (an estimator, for example,
  whose container starts with
  `until [ -f /shared/config.yaml ]; do sleep 1; done; exec ...`, and whose
  `setup()` writes `self.shared / "config.yaml"` from
  `self.stereo.left.calibration`);
- CycloneDDS (`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp`) on your stack's own
  domain. Install `ros-humble-rmw-cyclonedds-cpp` in your images; do not set
  `ROS_DOMAIN_ID` or `CYCLONEDDS_URI`.

Use sim time (`use_sim_time: true`); `/clock`, `/tf` and `/tf_static` are
always on your side. A launch file that declares no `use_sim_time` runs its
nodes on the wall clock: wrap it in one of your own that sets it for every
node (`SetParameter(name="use_sim_time", value=True)`, as the examples'
`files/sim_time.launch.py` do). Wall-clock timers (`create_wall_timer`)
stay on the wall clock either way.

`ports` publishes a container port on the host, as `"HOST:CONTAINER"` or
`"HOST:CONTAINER/udp"`. Host ports are 1024 or higher. A stack that
publishes host ports can be bound to one drone only: two drones' copies of it
would want the same port, so the generator refuses the second and names the
port.

`volumes` maps a name to an absolute path inside the container. Each is a named
Docker volume, `tevv-stack-<stack id>_<name>`, that outlives a run: the place
for a TensorRT engine cache that takes minutes to build and should not be
built again on every run. A host path on the left is not accepted (put team
files in `files/`, which is `/stack/files`), and neither is a path under
`/stack`, `/shared`, `/cfg` or `/mns/out`, which TEVV mounts itself.

`fcu=True` is accepted but nothing can honour it yet. It would give the
container its own MAVLink link to the drone's autopilot (so that it could run
its own MAVROS), and no autopilot offers a second link: PX4's router endpoints
belong to TEVV and AirSim, and ArduPilot's SITL serves MAVROS on tcp 5760
only. `stack check` refuses a stack that sets it, and says so. Use TEVV's
MAVROS topics, `/<drone>/mavros/...`, through the interface instead.

A stack of three containers, two of them on the GPU and sharing a TensorRT
engine cache. The main one is keyed by the stack id, `casio`, as `stack wire`
writes it:

```python
containers = {
    "casio":      Container(image="dhdevspace/auto_mns:casio-node"),
    "detection":  Container(image="dhdevspace/auto_mns:casio-detection",
                            gpu=True, volumes={"engines": "/engines"}),
    "da3":        Container(image="dhdevspace/auto_mns:casio-da3",
                            gpu=True, volumes={"engines": "/engines"}),
}
```

### Parameters

```python
parameters = {
    "v_max": Parameter(2.0, min=0.5, max=5.0, unit="m/s", label="Top speed"),
    "mode": Parameter("cautious", options=["cautious", "bold"]),
}
containers = {"planner": Container(image="me/planner:1",
                                   command="ros2 launch p p.launch.py v_max:={param.v_max}")}
```

A parameter's default sets its type (number, whole number, true/false or
text); `min`/`max` bound a number, `options` lists the allowed values, and
`label`, `unit` and `help` describe it in the dashboard. `{param.<name>}` in a
container's `command` or `env` is the run's value, and `setup()` reads it as
`self.params["v_max"]`. A test sets values, or a test plan sweeps them, under
`extensions."mns.parameters".components.<stack id>`; a value out of bounds is
refused before the run.

### Your own message types

```python
messages = [Messages("me/planner:1", packages=["planner_msgs"],
                     setup=["/ws/install/setup.bash"])]
```

TEVV copies the named packages out of the image once per run, so the
recorder, the viewer and your interface container know them: `setup()` can
import them, and a `Scoring(plan=...)` or `Lockstep(ack_on=...)` topic can be
of your own type. `setup` names setup.bash files to source in that image when
the packages live outside the usual workspaces (`/ros2_ws`, `/ws`,
`/workspace`).

### Scoring your own outputs

```python
scoring = Scoring(plan="/planner_state",
                  checks={"replan_interval_max_s": {"max": 2.0}})
```

A scenario's observers judge every stack the same way, on what TEVV owns.
`scoring` adds what only your stack can say:

- `plan`: a topic on your side your planner publishes once per new plan
  (any type). TEVV records when each arrives and reports the time between
  plans (`replan_interval_p50_s`, `_p95_s`, `_max_s`). Only for a stack that
  flies its drone.
- `checks`: pass/fail limits on the scorer's metrics, `{metric: {"min"|"max":
  limit}}`: a planner's when your stack flies (`goal_success_rate`,
  `min_clearance_m`, `replan_interval_max_s`, ...), an estimator's when it
  only estimates (`ate_rmse_m`, `availability`, ...).

With observers in the scenario, your checks join your drone's observer
scorer; without, your scorer runs on its own after each run.

### Watching outputs of any type

```python
watch = ["/detections", Watch("/depth/image", min_hz=5)]
```

A stack's useful outputs are often its own (detections, a depth image), which
TEVV has no wiring line for, so [the live check](#the-live-check) would have
nothing to look at. `watch` names outputs of your software, of any type, that
the check judges: each must be published during the window, and at `min_hz`
or more when you give one. The check fails, with the reason, when a watched
topic is never published, is advertised but silent, runs below `min_hz`, or
has a type the interface image does not have, which you fix by adding its
package to `messages=`.

`stack wire --watch TOPIC` (repeatable) writes the list for you, and
`--watch TOPIC=HZ` writes `Watch(TOPIC, min_hz=HZ)`. Without the flag it
writes the list empty, so name every topic again, with its rate, when you
wire again (the dashboard's Wire step sends the stack's own list and rates),
and `interface.py`
gets `# could watch:` comment lines for the outputs it found, so you can pick.

### Sim-time lockstep

```python
lockstep = Lockstep(ack_on="/planner_state", timeout_ms=10000)
```

Under sim-time lockstep (a lockstep camera, or `conditions.lockstep.grid_hz`
in the scenario) the simulation holds time at each slot until your stack has
caught up, so a slow step costs wall time, never flight time. Outside
lockstep the declaration does nothing.

Measured capacity, from one drone to ten stacks flown together, is in
[Stack capacity](../stack-capacity.md).

- `ack_on`: a topic on your side that goes quiet while your software is busy
  (say, blocked in a replan) and keeps publishing when it is idle. Any message
  there tells TEVV your stack has caught up with the latest sim time. A
  planner's trajectory topic is often the wrong choice: it is quiet between
  goals, so every slot then waits the whole timeout. A heartbeat timer in the
  same callback group as the replan is usually right.
- `status_topic`: instead, one `std_msgs/Header` per camera frame your
  software is done with (stamp: the frame's; `frame_id`: `processed`,
  `skipped` or `failed`), for an estimator.
- `timeout_ms` (default 2000): the longest the simulation waits for you at one
  slot. `participant` (default: the stack's id) names your waits in the logs.

The mission's budgets (take-off, mission, landing) count sim seconds under
lockstep.

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
| `on(src, callback)` | Your function gets each message (a pair gets `callback(left, right)`). An exact camera's frames arrive resampled, as `forward` publishes them. |
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

class MyVio(TevvDefault):                 # TEVV's follower flies, on SimpleFlight
    needs = ["ground_truth", "stereo_primary", "imu"]
    containers = {"vio": Container(image="me/vio:1")}

    def setup(self):
        super().setup()                   # follow_waypoints()
        self.forward(self.stereo, left="/cam0/image_raw", right="/cam1/image_raw")
        self.forward(self.imu, "/imu0")
        self.estimate_from("/vio/odom")
```

## The run

Your stack flies its drone's whole mission, take-off and landing included.
TEVV only referees: it tells your interface each phase (`takeoff`, `start`,
`end`), publishes the mission, judges it on ground truth and logs every
event. It never flies the drone. Per drone:

1. **Take-off.** TEVV calls your `takeoff(d)` step. When it returns, the
   interface reports the drone in position. Budget: 240 s, including the
   autopilot's own wait before it will arm (PX4's estimator can take a
   minute or two). Over it, or if the step raises, the mission ends
   `takeoff_failed`; TEVV never takes the drone over.
2. **Ready.** TEVV waits for your `ready` topics (up to 240 s), else the
   mission ends `error`.
3. **Mission.** TEVV publishes the points, `control_state` turns
   `external`, and `on_start(d)` is called. Your commands now reach the
   autopilot through the interface's gate; after 1 s without one, the drone
   holds.
4. **End.** At the first of: every point reached, `done`, an error, the
   time budget, a stop. The gate closes and `on_end(d, reason)` is called.
5. **Landing.** TEVV calls your `land(d)` step; when it returns, the drone
   has landed. Budget: 60 s. Over it, `land_timeout` is recorded; the
   mission's verdict does not change. A stopped run does not land.

Steps fly; notifications only tell. Override any of them:

| Method | Kind | Default |
| --- | --- | --- |
| `takeoff(d)` | step: return when the drone is in position | `d.fc.takeoff(d.takeoff_altitude)` |
| `on_start(d)` | notification: the mission started, you have control | nothing |
| `on_end(d, reason)` | notification: the mission ended (`completed`, `timeout`, `stopped`, `error`, ...) | nothing |
| `land(d)` | step: return once landed | `d.fc.land()` |

`d` is `self` for a one-drone stack, and each `Drone` handle for
`drones = "many"`. Each runs on its own thread, so a step may block. Each
phase is scored by its own observers ([results.md](results.md#take-off-and-landing)).

`d.fc` is the drone's flight controller, on the autopilot your stack
declares: MAVROS for TEVV's PX4 and ArduPilot SITLs, the bridge's AirSim API
for SimpleFlight. Positions are in `odom`.

| Call | What |
| --- | --- |
| `position()` | Where the drone is (ground truth): `(x, y, z)`. |
| `arm()`, `disarm()` | Arm or disarm (SimpleFlight does both in its take-off and landing). |
| `mode(name)` | Set a flight mode (`"OFFBOARD"`, `"GUIDED"`, ...; not on SimpleFlight). |
| `takeoff(z)` | Arm, climb to height `z` and hold. Returns when there. |
| `goto(x, y, z, yaw=None)` | Fly to a point, holding `yaw` if given. Returns at once. |
| `hold()` | Hold where the drone is. |
| `land()` | Land where the drone is. Returns at touchdown. |

`d.takeoff_altitude` is the `odom` height TEVV asks the take-off to reach:
the mission's start altitude above the ground the drone stands on. A call the
autopilot refuses raises, and the step fails.

Your own take-off, say a first stop at 1 m, then the climb facing north:

```python
import time
from tevv import Interface

class MyPlanner(Interface):
    autopilot = "px4"
    ...
    def takeoff(self, d):
        x, y, z = d.fc.position()
        d.fc.takeoff(z + 1.0)                            # arm, climb to 1 m, hold
        d.fc.goto(x, y, d.takeoff_altitude, yaw=1.5708)  # facing north (ENU)
        while abs(d.fc.position()[2] - d.takeoff_altitude) > 0.3:
            time.sleep(0.1)
```

Your containers cannot fly the take-off: your command reaches the autopilot
only during the mission. Your own SITL image (`Autopilot("px4",
image=...)`, [above](#choosing-an-autopilot)) gets the same `d.fc`.

## One stack, many drones

A stack that flies several drones at once, a swarm planner for instance,
declares `drones = "many"`. A test that names it for several drones gives
them all to **one** instance: one set of your containers, on one network and
domain, and one interface joined to every one of those drones. In `setup()`,
`self.drones` lists a handle per drone, with the same inputs and methods as
`self` has for a one-drone stack:

```python
class Swarm(Interface):
    autopilot = "px4"
    drones = "many"
    needs = ["ground_truth"]
    containers = {"planner": Container(image="me/swarm:1", command="ros2 launch swarm all.launch.py")}

    def setup(self):
        for d in self.drones:                      # d.name (Drone2), d.mission, d.gt_odom, ...
            d.forward(d.gt_odom, f"/{d.name}/odom")
            d.forward(d.next_waypoint, f"/{d.name}/goal")
            d.command_from(f"/{d.name}/setpoint")
            d.debug("goal", ...)                   # recorded per drone
```

Every drone flies on the stack's autopilot. `/clock` reaches your side once;
each drone's tf arrives as `/tevv/<drone>/tf` and `/tevv/<drone>/tf_static`
(the drones' frame names are the same). `passthrough()` gives your side
every drone's `/tevv/<drone>/...` names. An error in your code ends every
drone's mission.

## A stack you start yourself

If your stack already runs in your own Docker network on this machine,
declare where, and no containers:

```python
class MyPlanner(Interface):
    autopilot = "px4"
    network = Network("my-autonomy", domain=0)     # its Docker network and ROS_DOMAIN_ID
    ready = ["/planner_state"]

    def setup(self):
        self.forward(self.gt_odom, "/odom")
        self.command_from("/setpoint")
```

TEVV starts none of your containers. For each run it joins this interface
to your network, at a free address it picks there, and talks to your stack
on your domain with plain multicast discovery, like any container on that
network. Your domain must differ from the drones' (1, 2, ... by default).
Start your stack before the run: a run whose network is missing stops
before anything flies and says so. Your containers' logs stay with you;
`./tevv logs` has the interface's. Starting yours might look like:

```bash
docker network create my-autonomy
docker run -d --name my-planner --network my-autonomy \
  -e ROS_DOMAIN_ID=0 -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  me/planner:1 ros2 launch my_planner planner.launch.py
```

Nothing restarts it between runs, so it keeps its state: restart it
(`docker restart my-planner`) after a run that ended mid-flight. Stop it
yourself afterwards (`docker rm -f my-planner`).

## What stays fixed

Your stack cannot publish on the drone's side except through the four
outputs (`command`, `estimate`, `mission_status`, `debug/*`), cannot command
the drone outside the mission (the interface passes your command only while
`control_state` is `external`, and holds the drone after 1 s without one),
and cannot change the mission or its observers. Only `interface.py`'s steps
touch the autopilot, through `d.fc`; your containers never see MAVROS. TEVV
judges every phase on ground truth. That is what makes a TEVV result
comparable between stacks.

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
- **Errors.** An exception in `setup()`, a step or a callback ends the
  mission `interface_error` (`takeoff_failed` during take-off), with the
  reason in the results and the traceback in the log. The other drones fly
  on.
- **Python packages.** `requirements.txt` is installed into the interface
  container when it starts, from the wheels `./tevv stack lock` downloaded
  ([below](#pinning-a-stack)): lock it after each change.
- **Your editor.** `./tevv sdk` copies the SDK (the version TEVV runs) into
  `.tevv/sdk`; add it to your editor's Python path for autocomplete.

## Pinning a stack

```bash
./tevv stack lock my-planner
```

writes `stacks/my-planner/tevv.lock`: every image the stack declares
(containers and message types) by its registry digest, so a tag that moves
cannot change a rerun; and, when there is a `requirements.txt`, its packages
downloaded as wheels inside the image that runs `interface.py`
(`wheels/`), each pinned by hash in `requirements.lock`. A run then starts
each locked image by digest and installs only those wheels, offline, checking
every hash. An image the lock does not name runs by its tag, and `stack
check` warns; a `requirements.txt` that is not locked, or changed since, is
refused. Lock again after changing an image tag or a requirement, and commit
the lock with the stack.

## Onboarding a stack

If your software already exists as an image (or a Dockerfile folder) and you
have its camera calibration, these commands build the stack for you instead
of writing `interface.py` by hand. Each step records what it did, so you can
stop and come back.

```bash
./tevv stack prepare-image my-stack --dockerfile-dir ~/my-software
./tevv stack discover my-stack --image tevv-local/my-software:latest-tevv-cyclone   # its ROS graph
./tevv stack rig my-stack --kalibr-camchain camchain-imucam.yaml --kalibr-imu imu.yaml
./tevv stack wire my-stack --autopilot px4                                           # writes interface.py
./tevv stack lock my-stack                                                           # pins the images
./tevv stack live-check my-stack                                                     # flies it once
```

1. **prepare-image** builds your Dockerfile folder (`--dockerfile-dir DIR`) or
   takes a published image (`--image IMAGE`), and adds Cyclone DDS when the
   image lacks it, as `<repo>:<tag>-tevv-cyclone`. A Dockerfile folder is
   built as `tevv-local/<folder name>:latest` (`--tag TAG` names another
   tag), so `~/my-software` above becomes `tevv-local/my-software:latest`,
   and `tevv-local/my-software:latest-tevv-cyclone` once Cyclone is added.
   It prints the image it made: that is the one to discover. Give it the
   stack id to record the image for that stack; without an id it only
   builds.
2. **discover** starts the image (`--image IMAGE`, required: the image
   prepare-image printed), waits for its ROS graph to settle (unchanged for
   `--settle S` seconds), and lists each node with the topics it subscribes
   to and publishes, with their types. discover makes the stack's folder when it is
   missing. `--timeout S` (default 60) is the
   time its nodes may take to appear; `--settle` (1 to 600, default 5) is
   waited on top of it. `--command CMD` says what starts your
   software when the image's own command is not it, and `--gpu` runs it with
   the GPU. `--name NAME` names your main container in `interface.py`
   (default: the stack id; the Container name field in the dashboard). A stack of several containers names the others with
   `--also NAME=IMAGE` (with `--also-command NAME=CMD` and `--also-gpu NAME`
   for that one): every image runs together, as it will in a run, and the
   discovery records each as a container. The stack's folder is mounted
   read-only at `/stack` in all of them, so its `files/` is `/stack/files`.
   A container that starts its nodes late (one that builds a TensorRT
   engine first) needs a longer `--settle`, or its topics are missing. When
   your nodes publish nothing beyond the topics every node has, discover
   warns: a command that waits for the simulator (a take-off gate) shows only
   the gate, so discover a command that starts your nodes directly and add
   the gate back in `interface.py`.
   When a container stops before discovery finishes, discover says what its
   exit code means and what to do
   ([When discover stops short](#when-discover-stops-short)).
   When the discovery did not settle or its
   container exited, or the image differs from the one prepared, `wire`
   still writes `interface.py` but warns you to discover again.
3. **rig** describes the sensors your drone carries (below).
4. **wire** matches the discovered topics to what the rig gives the drone,
   and writes `stacks/<id>/interface.py`: one `forward`, `command_from` or
   `estimate_from` line per match, and a `# not wired:` comment for a topic
   left over. It writes every container discovery recorded, each with
   `run_as="image"`: discover runs them as the image's own user, so that is
   what it proved works (under the default, `platform`, the host user with
   `HOME=/tmp`, an image that writes to its own folders fails). `--watch TOPIC`
   (repeatable; `TOPIC=HZ` with the lowest rate you accept) adds an output of your software to `watch`
   ([Watching outputs of any type](#watching-outputs-of-any-type)); without
   it, `# could watch:` lines list the candidates.
   `--autopilot simpleflight|px4|ardupilot` picks what the drone
   flies on (default: the stack's current autopilot, else `simpleflight`).
   `--ready TOPIC` (repeatable, absolute) writes `ready = [...]`: topics of
   your software that must publish before TEVV hands it the drone; without
   the flag `ready` is empty (the Ready checkboxes in the dashboard's Wire
   step). `--command CMD` and `--also-command NAME=CMD` set what a container
   runs in a test when that differs from what discovery ran: for example
   MIGHTY is discovered with a command that starts it directly, and flown
   with the same command behind a take-off gate (the "What each container
   runs in a test" fields in the Wire step).
   When you have edited `interface.py` since, `wire` writes
   `interface.proposed.py` beside it instead; `--force` replaces your file.
5. **lock** is [Pinning a stack](#pinning-a-stack).
6. **live-check** flies the stack once and proves its topics flow
   ([The live check](#the-live-check)).

Your software keeps its own topic names; `interface.py` is the only place
that knows both sides. Onboarding takes an id of your own: `discover`, `rig`,
`wire`, `prepare-image` (with an id), `lock`, `replace` and `live-check`
refuse the built-in stacks' ids (`tevv-default`, `tevv-default-px4`,
`tevv-default-ardupilot`). Writing a rig or
`interface.py` clears the stack's live check, since what was checked has
changed.

### When discover stops short

Discover stops short in four ways, and says which, with the container's last
lines (or that it printed nothing). The dashboard's Discover step shows the
same explanation in its own words, with what to do, and folds the CLI's
message under Details.

- **No Cyclone DDS.** The image was not started: prepare it (the Image step,
  or `tevv stack prepare-image`) and discover the image that prints.
- **A container stopped.** Read its exit code (below).
- **No ROS 2 node appeared** within the timeout: give the command that
  starts your software (`--command`, the Start command field), or a longer
  `--timeout` when it downloads or builds something first.
- **The graph kept changing:** a node restarting in a loop (its last lines
  say why), or nodes that start one after another (a longer `--settle`).

Discover records what each image runs on its own (`image_command` in the
discovery: its entrypoint and command), so a container that stopped at once
is explained by what it ran. When it stops short it also looks inside the
image (`image_contents`): its colcon workspaces, the executables `ros2 run`
starts, launch files and parameter files outside `/opt/ros`, and names them.
The dashboard lists them with **Use**, which writes a start command for one:
its workspace sourced, `exec` so it stays in the foreground, and its
package's parameter file when there is exactly one. A start command that
only prepares the shell (`source`, `export`, `cd`, ...) is said to start
nothing.

#### Exit codes

A container's exit code is set by the shell and Docker: 126 and 127 come from
the shell, and 128 + N means the container was killed by signal N.

| Code | What it means | What to do |
|---|---|---|
| 0, no start command | It finished: the image's own command starts nothing that stays. Most often that command is a bare shell (`bash`), which ends at once when it has nothing to run; casio-detection's is `/entrypoint.node.sh bash`. | Give the command that starts your nodes, e.g. `source /ros2_ws/install/setup.bash && ros2 launch my_pkg bringup.launch.py`. |
| 0, a start command that only sets up | It only prepared the shell (for example `source /ros2_ws/install/setup.bash`) and started nothing. | Add the command that runs your software after it with `&&`; discover names what the image provides. |
| 0, with a start command | Your command finished instead of keeping your nodes running: it sent its work to the background with `&`, or its last command ran and ended. | End it with a command that stays in the foreground, e.g. `exec ros2 launch ...`; the container stops when the last command ends. |
| 1 | It failed: the reason is in its last lines. | Read them. A file it reads is missing (upload it under Files; it is at `/stack/files/<path>`), a package is not sourced, or it needs the GPU. |
| 2 | A command was given wrong arguments. | Check the command and its arguments. |
| 126 | A command was found but could not run: not executable, or no permission. | Make the file executable in the image (`chmod +x`) and readable by its user. |
| 127 | A command was not found: not installed, or its workspace is not sourced. | Source the workspace at the start of the command, and check its spelling. |
| 130 | It was interrupted (Ctrl-C, SIGINT). | Run it again. |
| 134 | It aborted (SIGABRT): a failed assertion, or an exception nothing caught. | Read its last lines: they name the node. |
| 137 | It was killed (SIGKILL), usually by the out-of-memory killer. | Free memory on the machine (other simulators or stacks), or have it load less. |
| 139 | It crashed with a segmentation fault (SIGSEGV). | Read its last lines; check the files it reads exist and, for CUDA or TensorRT, that it has the GPU. |
| 143 | It was told to stop (SIGTERM). | Something stopped it from outside; run it again. |
| Other above 128 | It was killed by signal (code minus 128). | Read its last lines. |
| Other | It failed. | Read its last lines. |

### What the stack folder gains

```
stacks/<id>/
  files/                your own files, read by your containers at /stack/files
  rig/
    rig.yaml            the sensors: cameras, IMU, lidar, where they sit on the drone
    fit.json            the fit report: your values, the simulator's, the differences (kept current from rig.yaml)
    kalibr-*.yaml       the Kalibr files you gave, copied beside it
  onboarding.json       what onboarding did so far
```

`onboarding.json` holds the discovery (when it ran, the nodes and topics),
the wiring written into `interface.py`, the image prepared for the stack,
every replacement (`stack replace`) and the live check. It holds no
registry logins: TEVV reaches registries only through your own Docker
configuration. Edit `rig/rig.yaml` by hand if you need to: it is checked
again the next time it is read (`stack rig --show`, `stack wire`, a run),
and an error there names the field to fix. Run `stack rig` again to refit
it.

### The rig

```bash
./tevv stack rig my-stack --kalibr-camchain camchain-imucam.yaml \
    --kalibr-imu imu.yaml --camera-names front,back \
    --topic front=/cam0/image_raw --topic back=/cam1/image_raw --topic imu=/imu0 \
    --rate front=20 --rate back=20 --imu-mount 0,0,90
./tevv stack rig my-stack --show        # the stored rig and its fit
```

The source is Kalibr's `camchain-imucam.yaml` (`--kalibr-camchain FILE`) and
optionally its `imu.yaml` (`--kalibr-imu FILE`, for the noise and update
rate), or known sensor models (`--model ID`, a camera, IMU or lidar,
repeatable) instead of Kalibr files. One drone renders at most four cameras
at the rate a rig asks for, so a rig with more is refused at this step.

| Flag | What |
| --- | --- |
| `--camera-names A,B` | One name per Kalibr camera, in `cam0`, `cam1` order (default `cam0`, `cam1`, ...). A name is a letter, then letters, digits or underscores. |
| `--topic CAMERA=TOPIC` | The topic your software reads that camera on; `imu=TOPIC` for the IMU. Repeatable. It wins over a guess by name when `wire` matches topics. |
| `--rate CAMERA=HZ` | The rate the camera is forwarded to your software at (`wire` writes it as `max_hz` on that camera's `forward`, and the fit report shows it). Kalibr does not record one, so a camera runs at 30 Hz unless you say so. The live check confirms the rate the simulator actually delivers. Repeatable. |
| `--imu-mount ROLL,PITCH,YAW` | Where the IMU sits on the drone, in degrees, in the drone's body frame (x forward, y left, z up). It matters on hardware where the IMU is not mounted level and facing forward; without it the IMU is taken to be at the body frame. A camera sits at the IMU's mount composed with Kalibr's `T_imu_cam`. |

If you have ROS `camera_info` files rather than a Kalibr calibration, give
one per camera, each with where the camera sits on the drone:

```bash
./tevv stack rig my-stack --camera-info front=siyi_a8.yaml \
    --camera-mount front=0.15,0,-0.10,0,25,0
```

`--camera-mount NAME=X,Y,Z,ROLL,PITCH,YAW` is in metres and degrees, in the
drone's body frame (x forward, y left, z up), right-handed, and a positive
pitch tilts the camera down: the example above is 0.15 m ahead of the body
origin, 0.10 m below it and tilted 25 degrees down. A `plumb_bob` camera is
fitted as radtan (a nonzero `k3` is refused, since the simulator's radtan has
none), `equidistant` is kept as it is, and `rational_polynomial` is refused.
A `camera_info` file cannot be combined with a Kalibr chain in one rig. When
a rig has cameras the simulator cannot render, they are reported first, before
any problem with the topic or rate names you gave.

### The fit report: exact or closest

The simulator renders a pinhole camera from a horizontal field of view
(square pixels, the centre of the image as the principal point, no
distortion), and its fisheye path takes Kannala-Brandt and double sphere
calibrations as they are. A camera that does not fit those is not drawn
as a lookalike. TEVV renders it wider and resamples it to your calibration
(below), though a camera that needs a fisheye render gets this only
[in lockstep](#the-live-check-in-lockstep). So your camera is either exact or,
in a few cases, a closest match,
and `stack rig` says which for each camera. `rig/fit.json` keeps your values,
the simulator's, and the differences (simulator minus yours, in pixels). TEVV
fits the rig again each time it generates a stack or shows the fit, so what you
see is what runs; `fit.json` is rewritten when it differs (after a TEVV update
that fits a camera differently, or when it is missing or damaged).

| Their model | Rendered as | Match |
|---|---|---|
| pinhole + equidistant (Kannala-Brandt) | fisheye, Kannala-Brandt series with their coefficients | exact |
| double sphere | fisheye, double sphere with their xi and alpha | exact |
| pinhole, square pixels, centred, no distortion, under 90 degrees across | pinhole at your field of view | exact |
| the same at 90 degrees across or wider (the simulator's pinhole stops below 90) | in lockstep: fisheye whose Kannala-Brandt series is the pinhole's, then resampled. Free: the closest-match pinhole | exact, by resampling, in lockstep only |
| pinhole + radtan, or fx different from fy, or a principal point more than half a pixel off centre | pinhole rendered wider at your focal length (the smaller of fx and fy), then resampled | exact, by resampling |
| the same, when the widened render would be 90 degrees or wider | in lockstep: fisheye rendered at the wider view, then resampled. Free: the closest-match pinhole | exact, by resampling, in lockstep only |
| omni, eucm | not supported | refused |

**Resampling.** The interface container resamples each frame of such a camera
to your fx, fy, cx and cy and your radtan distortion, and publishes a
`camera_info` with your values instead of the simulator's. Your software
sees the image size and calibration you gave. This is automatic in `forward`
and in `on` (your callback gets the resampled frame, and a pair gets both
resampled); `interface.py` does not change. A wide camera such as a ZED is
exact too, in lockstep: a 1280x720 ZED-like camera is rendered as a 1676x946
fisheye of 108.3 degrees corner to corner and resampled from that. Free, the
same camera is the closest-match pinhole, and its summary says
"(resampled to your calibration under lockstep)": the fisheye route is too slow
to deliver the camera's rate without lockstep. Rig fisheye renders use the
shared cubemap, one per mount point. `stack rig` prints what
it will do, for example
`camera left: resampled to your calibration (rendered 1344x768, 87.9 degrees across)`
or `(rendered as a fisheye 1676x946, 108.3 degrees corner to corner)`. A
pinhole render's field of view is measured across the image; a fisheye
render's from corner to corner, as the simulator's fisheye takes it.

Resampling costs CPU in the interface container, about 13 ms per frame for a
640x480 camera (measured in a live check). The container logs
`camera <name>: resampling takes N.N ms per frame` every 10 seconds. If a
frame arrives at a size other than the planned render, it passes through
unresampled with the simulator's `camera_info`, and the container warns once.

**Closest match.** TEVV refuses the resampling, and the camera stays a
closest match, when the render would need:

- more than 4096 pixels on a side,
- more than twice your pixel count,
- a fisheye field of view over 220 degrees, or
- a distortion that does not invert at the image corners.

The reason is in the camera's notes, and the summary names the differences,
for example `closest match: fx differs by +2.0 px, distortion error 3.4 px`.
The distortion error is the larger of your distortion the simulator does not
draw and, for a camera 90 degrees or wider, how far the fisheye render lands
from a true pinhole at the image corners.
Read them before you trust a comparison against your real recordings: a
distortion the simulator does not draw is a real difference in what your
software sees.

The fit is shown in `stack rig` and `stack show` (`fit`), in each run's
`interface.json` (`inputs.cameras[<name>].fit`), and in the dashboard's Rig
step, Rig tab, Overview and Live check. The
[live check](#the-live-check) records it per camera.

`stack rig` refuses a camera of the unsupported models (exit 1, naming the
camera, with the fit of the others; nothing is written); recalibrate with
Kalibr's pinhole-radtan, pinhole-equi or double sphere (`ds-none`) models.

### Statuses

`stack list` and `stack show` give each workspace stack one of four statuses,
and the dashboard's Stacks page shows the same word.

| Status | What makes it |
| --- | --- |
| ready | The live check passed, the images it ran on are the ones the stack pins now, `interface.py` and `rig/rig.yaml` are the files it checked, and `stack check` finds nothing wrong. |
| needs fix | A live check of the current `interface.py` and rig failed, a different image is pinned since it passed, or `stack check` finds a problem. Without such a live check the stack is `not checked`, whatever `stack check` says. |
| out of date | An image the stack pins has moved: a newer image sits under the same tag. This wins over the other three. |
| not checked | No live check has been recorded, or `interface.py` or `rig/rig.yaml` changed since it ran (an edit by hand counts: what was checked is no longer what would fly). Every stack you onboard starts here. |

A stack you onboard stays `not checked` until you run
[the live check](#the-live-check).

### The live check

```bash
./tevv stack live-check my-stack
./tevv stack live-check my-stack --seconds 60 --keep
./tevv stack live-check my-stack --lockstep
```

It flies your stack once on a scenario TEVV ships (the onboarding check), so
you need no test of your own to find out whether TEVV and your software reach
each other. The scenario is one drone over the XFS container yard, on the
autopilot your `interface.py` declares, and a small square to fly 2.5 m up.
The drone carries the scenario's IMU, GPS, barometer and magnetometer plus
your stack's rig (the cameras, IMU or lidar in `rig/rig.yaml`); a rig sensor
replaces the scenario's sensor of the same role. TEVV starts your stack, the
drone takes off (your interface's take-off, on your autopilot), and the
mission's referee hands the drone to your software; a stack that calls
`follow_waypoints()` is flown along the square by TEVV. Measuring starts at
that hand-over: for `--seconds` TEVV watches every topic `interface.py` wires,
on your stack's ROS domain and on the drone's, and judges them. The check
records nothing else and scores nothing.

| Flag | What |
| --- | --- |
| `--seconds S` | How long the topics are watched once the drone is handed to your stack (default 20). It cannot be longer than the check mission (150 s). |
| `--timeout S` | How long the check flight may run before it fails. By default it is what a campaign allows the check mission: about 990 s, and 20 times that when your stack runs sim-time lockstep (the simulation then runs slower than the clock on the wall). Give a number above 0 to use another. |
| `--lockstep` | Fly the check in sim-time lockstep ([below](#the-live-check-in-lockstep)). The dashboard's Live check step has the same choice, "Run in lockstep". |
| `--keep` | Leave the check stack running afterwards, the simulator included, to look at its logs (the probe may still be running in its interface container). |
| `--progress FILE` | Append the check's progress to FILE as JSON lines, the same `run.phase` events a campaign's runs write (`run_key` is `live-check-<id>`), plus the phase `watching` when TEVV starts watching the topics (its `detail` says whether from the hand-over or on the ground). A stop file in FILE's folder (`campaign.stop`, the marker that stops a campaign's run) stops the check: it ends as not judged (`flight_failed`, "stopped by the user") and records nothing. |

The check stack is generated into `<workspace>/generated/live-check/<id>`
(your workspace folder), and stopped at the end unless `--keep`. To read its
logs, or stop one you kept, give that full path:

```bash
make stacks ARGS="logs --stack <workspace>/generated/live-check/my-stack"
make stacks ARGS="stop --stack <workspace>/generated/live-check/my-stack"
```

Run it on a machine whose GPU is free: the simulator renders your cameras,
and one that is starved of the GPU delivers them too slowly to judge.

**What is expected.** An input is expected at its rig rate, capped by the
`max_hz` on its `forward` line when that is lower (`max_hz` alone when the
rig gives no rate; any rate above zero when neither does). An input passes at
half the rate asked or more; one that passes but is below 90% of it says
"slower than asked (N%)" in its reason. Under sim-time
lockstep rates are counted per second of simulation time, which is what your
sensors run on. A topic written as an f-string on `self.drone` alone
(`f"/{self.drone}/mavros/setpoint_raw/local"`) is read for the check's drone,
`Drone1`. A wiring call TEVV cannot read a topic from (an f-string on other
values, a variable, a call on a drone handle in a many-drone stack) is listed
as not checked, with its line, and does not fail the check.

**Pass.** Every input TEVV forwards reached your software at its expected
rate, and every output `interface.py` wires was published by your software;
the command and the estimate also reached the drone. Every topic in `watch`
was published by your software, at its `min_hz` when it sets one. The command
is not expected when TEVV flies your drone (`follow_waypoints()`), and a status only
has to be published (it may say nothing during the window). The verdict, the
images it ran on, the files it checked and the rate of each topic are
recorded in `onboarding.json` (with each camera's fit under `cameras`; a camera that is only a closest match adds a note, never a failure), and the stack becomes `ready`. Pinning other
images takes that back (`needs fix`), and so does editing `interface.py` or
the rig, by hand or with `wire` and `rig`, or a TEVV update that fits a camera
differently (exact or closest, resampled or not) (`not checked`); run the check
again.

**Fail (exit 1).** The verdict is recorded with one reason per problem, each
naming its topic and numbers, and the stack becomes `needs fix`. These are
yours to fix:

- Your stack never published its estimate, or a topic it lists in `ready`,
  within the wait after take-off, so TEVV never handed it the drone. TEVV
  still watches your topics, with the drone back on the ground, for
  `--seconds`, so the reasons below say why (often: nothing subscribes to an
  input your estimator needs).
- TEVV's interface stopped on your stack's error before the drone took off:
  a wiring line names a topic of a type it cannot pass on, or your `setup()`
  or a callback of yours raised. The interface has exited by then, so
  nothing is watched: the check records the fail from the interface's log,
  quoting its error line, followed by "your stack's interface stopped
  before TEVV could hand it the drone". (The same error during take-off is
  a failed take-off, which is not judged: see `not_handed_over` below.)
- None of your nodes appeared on the stack's ROS domain. Your image may set
  `ROS_DOMAIN_ID` or `CYCLONEDDS_URI` itself (TEVV sets both), or not run
  Cyclone DDS (`stack prepare-image` adds it), or its container is not
  running. Nodes that only launch your software (`ros2 launch`'s own) do not
  count.
- Nothing in your software subscribes to an input TEVV forwards. The reason
  lists the topics your software does subscribe to.
- A QoS mismatch: your software subscribes reliable but every publisher is
  best effort, or transient local but every publisher is volatile. Nothing
  is delivered, and the reason names both settings.
- Your software never published an output, or advertises the command or
  estimate but sent nothing during the window.
- Your publisher is best effort but TEVV subscribes reliable. Publish
  reliable.
- Your software publishes the command or estimate but nothing reached the
  drone. The reason quotes the interface's own log line when it has one (a
  message of a type it cannot pass on).
- Your stamps are more than 5 s behind or ahead of simulation time. Set
  `use_sim_time` in your nodes.
- A container of yours exited. The reason gives its exit code and its last
  log lines; one in a restart loop "keeps restarting", with its last exit
  code. Containers are named as `interface.py` names them. When one of yours
  is down, the reasons leave out the hint about the stack's ROS domain: the
  crash is why none of your nodes appeared.

**Could not check (exit 2).** Nothing is recorded and the stack keeps its
status: the problem is on TEVV's side, or the run never got far enough to
judge you. The error says which, and with `--json` its `type` names the
case:

| `type` | What happened |
| --- | --- |
| `flight_failed` | The check flight did not finish (the simulator failed, the scenario did not generate, or the timeout passed). The error names the check stack's folder; its logs say why. |
| `not_handed_over` | The run never handed control to your stack for a reason that is not your stack's: your interface never started, take-off failed, or TEVV saw no hand-over. |
| `tevv_short` | The simulator delivered an input below half its expected rate, or not at all, or TEVV published nothing on it or could not read its rate. Free the GPU of other simulators and run the check again. |
| `probe_failed` | TEVV's probe could not run, ended without a result (the error gives its exit code and last lines), or was still running at the end (the interface container may be stuck). Rebuild the interface image, or set `TEVV_INTERFACE_IMAGE` to one that starts, then run the check again. |
| `refused` | Nothing flew: a built-in stack, a stack that fails `stack check`, a stack on its drone's ROS domain, or a `--seconds` or `--timeout` out of range. |


### The live check in lockstep

```bash
./tevv stack live-check my-stack --lockstep
```

This flies the check in sim-time lockstep. The simulator waits for every
camera frame on a grid at the rig's highest camera rate (30 Hz when the rig
has no camera), so each camera delivers its full rate in simulation time.
Rates are judged per simulation second. The check runs slower than real time:
about 0.4 to 0.5 times real time for one drone in TEVV's tests, and more
cameras or drones slow it further.
How much slower with ten drones, each with its own stack, is in
[Stack capacity](../stack-capacity.md).

- **ArduPilot or SimpleFlight only.** Lockstep needs a steppable clock. A PX4
  stack is refused before anything flies. Switch with
  `tevv stack wire <id> --autopilot ardupilot`.
- **Cameras are captured on the grid.** The rig's cameras go through shared
  memory (a pinhole camera's topic is then the shared-memory one). Every camera
  is captured at the grid rate, and your stack still receives only the rate it
  asks for (`max_hz`).
- **Exact cameras.** A camera that needs a fisheye render (90 degrees or wider
  once widened) is resampled to your calibration only in lockstep. Free, it is
  the closest-match pinhole ([the fit report](#the-fit-report-exact-or-closest)).
- **The record says which mode flew.** `onboarding.json` holds `lockstep`, and
  a stack's status compares the fit of the mode it was checked in.

### Deleting a stack

The dashboard can delete a workspace stack: Delete stack on the stack's tabs,
or Delete on its card in the wizard. You type the stack's id to confirm. It
refuses built-in stacks, and any stack while a job, an upload or a live check
is running. The stack's folder goes; the live check's recordings are kept.

### Files your containers read

Model weights, launch files and configuration go in the stack's `files/`
folder, which every container sees read-only at `/stack/files`. Put them there
by copying into `stacks/<id>/files/`, or upload them on the dashboard's
Stacks page (the Files panel in Discover, and the Files tab afterwards): a
file may be up to 4 GiB and is streamed to disk. The dashboard refuses an
upload while a discovery or a live check of that stack is running. Anything
that should survive a run but is not yours to ship (a TensorRT engine cache)
belongs in a `volumes` entry instead.

### A worked example: casio-edge

casio-edge is a detection and depth stack of three containers. Discovery
brings them up together:

```bash
./tevv stack discover casio --image dhdevspace/auto_mns:casio-node \
    --also detection=dhdevspace/auto_mns:casio-detection --also-gpu detection \
    --also da3=dhdevspace/auto_mns:casio-da3 --also-gpu da3 --settle 30
./tevv stack rig casio --camera-info front=siyi_a8.yaml \
    --camera-mount front=0.15,0,-0.10,0,25,0
./tevv stack wire casio --autopilot px4 --watch /detections --watch /depth/image
```

The detector builds its TensorRT engine for about 20 s before its node
starts. `--settle 30` waits for it. With the default 5 s, `/detections` is
missing from the graph.

`wire` writes the three containers, the main one keyed `casio` after the
stack id, all with `run_as="image"` and `gpu=True` on `detection` and `da3`,
and `watch = ["/detections", "/depth/image"]` so the live check judges
the two outputs TEVV has no wiring line for. Add the `engines` volume to
`detection` and `da3` by hand: discovery cannot know it. Give `/depth/image` a
`Watch(..., min_hz=5)` if a slow depth stream should fail the check. The
camera is the SIYI A8, from its `camera_info` file, mounted 0.15 m ahead and
0.10 m below the body origin and tilted 25 degrees down.

### Out of date, and replace

```bash
./tevv stack outdated my-stack          # have the images my tevv.lock pins moved?
./tevv stack list --outdated            # the same for every workspace stack (asks the registries; slower)
./tevv stack replace my-stack            # says what would change, changes nothing
./tevv stack replace my-stack --yes     # do it
```

`stack outdated` compares each image in `tevv.lock` with what its tag points
to now. `stack replace` takes the newer image: it prepares the image again
when TEVV built or derived it, pins the stack again, notes the change in
`onboarding.json` and clears the live check. Without `--yes` it changes
nothing and tells you what it would replace. The stack's topics may have
changed with the image, so run `stack discover` again afterwards and look at
what `stack wire` proposes. A stack with no `tevv.lock` (one written by hand
and never locked) has nothing pinned, so it is not checked for a newer image;
`stack list --outdated` says so once in that stack's entry.

## From a component.yaml

```bash
./tevv stack import path/to/components/my-planner --id my-planner
```

writes `stacks/my-planner/interface.py` from a v1.1 component package and
copies its files beside it (`/cfg/component/...` becomes `/stack/...`). The
containers, needs, autopilot, ready topics, estimate, parameters, message
types, scoring and lockstep carry over as declarations. What a component did
differently is listed as a TODO in the file:

- a component read the bridge's topics directly; your containers now run on
  their own domain, so `setup()` forwards each input under the name your
  software reads. Names the component.yaml gives (its adaptor inputs, the
  ground truth and goal a planner reads) are filled in; the others are TODO
  lines.
- a planner that published MAVROS setpoints itself now hands them to TEVV
  (`command_from`).
- a `record:` list: TEVV records your command, estimate and plan itself;
  publish anything else with `self.debug(...)`.
- one-shot services and start order: your containers start together.

`examples/stacks/` holds three finished imports: `openvins` (an estimator
TEVV flies for), `super` and `mighty` (local planners, both lockstep
participants). Copy one into `stacks/` to use it; `examples/tests/` holds tests
that fly SUPER and MIGHTY on `planner-lockstep-xfs` (copy into `tests/`).
