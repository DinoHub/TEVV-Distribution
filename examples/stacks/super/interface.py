"""SUPER local planner, as a stack (imported from components/super-lockstep).

SUPER and its adaptor run unmodified in dhdevspace/auto_mns:super_runtime-ms.1-cyclone, the published
image with Cyclone DDS added (examples/images/super_runtime-ms.1-cyclone.Dockerfile): every
container of a stack runs on Cyclone.
This folder adds, at /stack/files:
- sim_time.launch.py: the adaptor launch with use_sim_time on every node
  (it declares none, so SUPER sampled its trajectories on the wall clock).
- wait_airborne.py: SUPER starts once the drone is airborne and steady.
- config/click.yaml: SUPER's planner configuration for the XFS yard.

Under sim-time lockstep the simulation waits at each slot until SUPER
publishes /planner_state, whose timer shares SUPER's exclusive callback group
with the replan: it goes quiet exactly while a replan blocks, and keeps
publishing between goals. /planner_result would not do: it is quiet while
SUPER has no goal, so every slot between goals would wait the whole timeout.
On the XFS yard slalom (27 Oct) lockstep took SUPER's longest time without a
new plan from 2-5 s to 0.2-0.4 s.
"""
from tevv import Container, Interface, Lockstep, Scoring



class Super(Interface):
    name = "SUPER local planner"
    autopilot = "ardupilot"
    needs = ["ground_truth", "point_cloud"]
    containers = {
        "super": Container(
            "dhdevspace/auto_mns:super_runtime-ms.1-cyclone",
            command=(
                "set +u && source /opt/ros/humble/setup.bash"
                " && python3 /stack/files/wait_airborne.py"
                " && source /workspace/generated/super_planner/.planner_ws/ros_ws/install/setup.sh"
                " && source /workspace/generated/super_planner/adaptor_ws/install/setup.sh"
                " && export AMENT_PREFIX_PATH=/workspace/generated/super_planner/adaptor_ws/install/super_planner_adaptor"
                ":/workspace/generated/super_planner/adaptor_ws/install:$AMENT_PREFIX_PATH"
                " && export PYTHONPATH=/workspace/generated/super_planner/adaptor_ws/install/super_planner_adaptor/lib/python3.10/"
                "site-packages:/workspace/generated/super_planner/adaptor_ws/src/super_planner_adaptor:$PYTHONPATH"
                " && export PATH=/workspace/generated/super_planner/adaptor_ws/install/super_planner_adaptor/lib/super_planner_adaptor"
                ":$PATH"
                " && exec ros2 launch /stack/files/sim_time.launch.py use_planner:=true"
                " runtime_params_file:=/stack/files/config/click.yaml use_rviz:=false autopilot:=ardupilot"
                " vehicle_output_topic:=/$MNS_VEHICLE/mavros/setpoint_raw/local"),
            run_as="image"),
    }
    ready = ["/planner_state"]
    scoring = Scoring(plan="/planner_result", checks={"replan_interval_max_s": {"max": 2.0}})
    lockstep = Lockstep(ack_on="/planner_state", timeout_ms=10000, participant="super")

    def setup(self):
        # Copter1 is the check scenario's drone (planner-lockstep-xfs); rename for another scenario.
        self.forward(self.point_cloud, "/Copter1/registered_point_cloud")
        self.forward(self.gt_odom, "/ground_truth/odom")
        self.forward(self.next_waypoint, "/goal")
        self.command_from(f"/{self.drone}/mavros/setpoint_raw/local")
