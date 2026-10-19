"""SUPER, started by you in your own Docker network: a worked example of a
stack TEVV does not start (network = Network(...)).

Your stack runs wherever you run it on this machine, in your own Docker
network and ROS domain; TEVV starts none of its containers. TEVV joins this
interface to your network, on your domain, and wires it exactly as the
super-planner stack does. Start SUPER first (README.md), then run the test.
"""
from tevv import Interface, Network

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


class SuperPlannerExternal(Interface):
    name = "SUPER local planner, started by you"
    description = ("SUPER runs in your own Docker network (my-autonomy, ROS domain 0); TEVV only joins its "
                   "interface to that network. Start it before the run (README.md).")
    autopilot = "px4"
    needs = ["ground_truth", "point_cloud"]
    network = Network("my-autonomy", domain=0)
    ready = ["/planner_state"]

    def setup(self):
        self.forward(self.gt_odom, SUPER_ODOM)
        self.forward(self.point_cloud, SUPER_CLOUD)
        self.forward(self.next_waypoint, SUPER_GOAL)
        self.command_from(SUPER_SETPOINT, convert=velocity_command)
