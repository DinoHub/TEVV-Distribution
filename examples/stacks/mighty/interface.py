"""MIGHTY local planner, as a stack (imported from components/mighty-lockstep).

MIGHTY and its adaptor run unmodified in dhdevspace/auto_mns:mighty_algo_only.
This folder adds, at /stack/files:
- sim_time.launch.py: the adaptor launch with use_sim_time on every node.
- wait_airborne.py: MIGHTY starts once the drone is airborne and steady.
- mighty.yaml: MIGHTY's parameters for the XFS yard.
- overlay/mighty_adaptor: the adaptor regenerated with position + velocity
  setpoints (DinoHub/local_planner_adaptor#1), ahead of the image's on
  PYTHONPATH until the image is rebuilt with it. Velocity-only setpoints let
  MIGHTY's plan drift away from the drone (it plans from its own last
  setpoint): it stalled short of goals under lockstep and overshot them
  free-running.

Under sim-time lockstep the simulation waits at each slot until MIGHTY has
published point_A (only on a successful replan) or 1 s has passed. MIGHTY
hands out its setpoints on a wall-clock timer, so with the simulation slower
than real time the drone follows its path faster than planned; a fair
lockstep comparison needs that timer on sim time in MIGHTY itself.
"""
from tevv import Container, Interface, Lockstep, Messages, Scoring



class Mighty(Interface):
    name = "MIGHTY local planner"
    autopilot = "ardupilot"
    needs = ["ground_truth", "point_cloud"]
    containers = {
        "mighty": Container(
            "dhdevspace/auto_mns:mighty_algo_only",
            command=(
                "source /opt/ros/humble/setup.bash"
                " && python3 /stack/files/wait_airborne.py"
                " && source /workspace/generated/mighty/.planner_ws/decomp_ws/install/setup.bash"
                " && source /workspace/generated/mighty/.planner_ws/ros_ws/install/setup.bash"
                " && export AMENT_PREFIX_PATH=/workspace/generated/mighty/adaptor_ws/install/mighty_adaptor:$AMENT_PREFIX_PATH"
                " && export PYTHONPATH=/stack/files/overlay"
                ":/workspace/generated/mighty/adaptor_ws/install/mighty_adaptor/lib/python3.10/site-packages:$PYTHONPATH"
                " && exec ros2 launch /stack/files/sim_time.launch.py namespace:=NX01 autopilot:=ardupilot"
                " odom_external_topic:=/ground_truth/odom term_goal_external_topic:=/goal"
                " vehicle_output_topic:=/$MNS_VEHICLE/mavros/setpoint_raw/local"
                " runtime_params_file:=/stack/files/mighty.yaml use_rviz:=false"),
            run_as="image"),
    }
    ready = ["/NX01/point_current_state"]
    # MIGHTY's trajectory and goal types, for the recorder, the viewer and this interface.
    messages = [Messages("dhdevspace/auto_mns:mighty_algo_only", packages=["dynus_interfaces"],
                         setup=["/workspace/generated/mighty/.planner_ws/ros_ws/install/setup.bash"])]
    scoring = Scoring(plan="/NX01/point_A", checks={"replan_interval_max_s": {"max": 2.0}})
    lockstep = Lockstep(ack_on="/NX01/point_A", timeout_ms=1000, participant="mighty")

    def setup(self):
        self.forward(self.point_cloud, "/Copter1/registered_point_cloud")
        self.forward(self.gt_odom, "/ground_truth/odom")
        self.forward(self.next_waypoint, "/goal")
        self.command_from(f"/{self.drone}/mavros/setpoint_raw/local")
