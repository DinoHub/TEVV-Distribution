"""SUPER (a local planner) flying its drone's mission: a worked example.

SUPER runs unmodified in its own container, with its own config
(files/config/click.yaml, which names SUPER's native topics). This file is
the whole customer interface: it feeds SUPER TEVV's ground truth, the
registered point cloud and the point to reach next, under the names SUPER
expects, and hands SUPER's setpoints back to TEVV as the drone's command.
Nothing in TEVV knows SUPER.
"""
from tevv import Container, Interface

# SUPER's own topic names (files/config/click.yaml).
SUPER_ODOM = "/px4vision_custom_0/mavros/local_position/odom"
SUPER_CLOUD = "/px4vision_custom_0/lidar"
SUPER_GOAL = "/goal"
SUPER_SETPOINT = "/px4vision_custom_0/mavros/setpoint_raw/local"


def velocity_command(msg):
    """SUPER's PositionTarget -> TEVV's command: its velocity (odom ENU) and yaw."""
    from mavros_msgs.msg import PositionTarget as PT
    out = PT()
    out.header.frame_id = "odom"
    out.coordinate_frame = PT.FRAME_LOCAL_NED          # MAVROS's name for its ENU frame
    out.type_mask = (PT.IGNORE_PX | PT.IGNORE_PY | PT.IGNORE_PZ | PT.IGNORE_AFX | PT.IGNORE_AFY
                     | PT.IGNORE_AFZ | PT.IGNORE_YAW_RATE)
    out.velocity = msg.velocity
    out.yaw = msg.yaw
    return out


class SuperPlanner(Interface):
    name = "SUPER local planner"
    description = ("The SUPER planner flies the drone to each published point on ground-truth odometry and "
                   "the lidar's point cloud. For planner tests.")
    autopilot = "px4"
    needs = ["ground_truth", "point_cloud"]
    containers = {
        "super": Container(
            image="dhdevspace/auto_mns:super_runtime-ms.1-cyclone",
            command="set +u && source /opt/ros/humble/setup.bash"
                    " && source /workspace/generated/super_planner/.planner_ws/ros_ws/install/setup.sh"
                    " && exec ros2 run super_planner fsm_node --ros-args"
                    " -p config_name:=/stack/files/config/click.yaml"),
    }
    ready = ["/planner_state"]          # TEVV hands over once SUPER's state machine is up

    def setup(self):
        self.forward(self.gt_odom, SUPER_ODOM)
        self.forward(self.point_cloud, SUPER_CLOUD)
        self.forward(self.next_waypoint, SUPER_GOAL)
        self.command_from(SUPER_SETPOINT, convert=velocity_command)
