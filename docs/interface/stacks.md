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
          run_as="platform")                # platform: the host user, HOME=/tmp; "image": the image's own user
```

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

### Sim-time lockstep

```python
lockstep = Lockstep(ack_on="/planner_state", timeout_ms=10000)
```

Under sim-time lockstep (a lockstep camera, or `conditions.lockstep.grid_hz`
in the scenario) the simulation holds time at each slot until your stack has
caught up, so a slow step costs wall time, never flight time. Outside
lockstep the declaration does nothing.

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
