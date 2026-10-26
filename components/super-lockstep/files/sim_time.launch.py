"""SUPER's adaptor launch on simulation time.

The adaptor launch file declares no use_sim_time, so SUPER ran on the wall
clock: under sim-time lockstep the sim holds while the wall clock runs on,
and a trajectory sampled on the wall would race ahead of the drone. This
wraps it with use_sim_time true for every node it starts. Arguments after the
launch file are passed through.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import SetParameter

PASS_THROUGH = ("use_planner", "runtime_params_file", "use_rviz", "autopilot", "vehicle_output_topic")


def generate_launch_description():
    adaptor = os.path.join(get_package_share_directory("super_planner_adaptor"),
                           "launch", "super_planner_adaptor.launch.py")
    return LaunchDescription([
        SetParameter(name="use_sim_time", value=True),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(adaptor),
            launch_arguments={name: LaunchConfiguration(name) for name in PASS_THROUGH}.items()),
    ])
