"""MIGHTY's adaptor launch on simulation time.

The adaptor launch file declares no use_sim_time, so MIGHTY ran on the wall
clock: it samples its trajectory at now(), and under sim-time lockstep the
wall clock runs on while the simulation holds, so the setpoints would race
ahead of the drone. This wraps it with use_sim_time true for every node it
starts. The launch arguments below are passed through.

Its adaptor sends position setpoints with velocity feed-forward
(type_mask_mode position_velocity, local_planner_adaptor): positions in the
frame of the odometry MIGHTY plans in. As a stack that is TEVV's ground
truth, the same frame TEVV's command path takes, so the adaptor's frame
offset is measured against that same odometry (zero) rather than against
MAVROS, which is not on the stack's side.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import SetParameter

PASS_THROUGH = ("namespace", "autopilot", "odom_external_topic", "term_goal_external_topic",
                "vehicle_output_topic", "runtime_params_file", "use_rviz")


def generate_launch_description():
    adaptor = os.path.join(get_package_share_directory("mighty_adaptor"),
                           "launch", "mighty_adaptor.launch.py")
    return LaunchDescription([
        SetParameter(name="use_sim_time", value=True),
        SetParameter(name="vehicle_odom_topic", value=LaunchConfiguration("odom_external_topic")),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(adaptor),
            launch_arguments={name: LaunchConfiguration(name) for name in PASS_THROUGH}.items()),
    ])
