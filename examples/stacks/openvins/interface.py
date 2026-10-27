"""OpenVINS stereo VIO, as a stack (imported from components/openvins).

TEVV's waypoint follower flies the mission; OpenVINS estimates. config/ is the
frozen calibration of the reference stereo rig (calibration-campaign-v1), so
check.py runs first and refuses a rig the calibration does not describe.
OpenVINS reads the stereo pair and the IMU under the names its kalibr chains
give (config/kalibr_*.yaml), which is where setup() forwards them.

Sim-time lockstep: an OpenVINS built with the frame-status patch publishes one
std_msgs/Header per frame it is done with; with that image, add
    lockstep = Lockstep(status_topic="/ov_msckf/frame_status", participant="openvins")
"""
from tevv import Container, Scoring, TevvDefault


class Openvins(TevvDefault):
    name = "OpenVINS stereo VIO"
    autopilot = "px4"
    needs = ["ground_truth", "stereo_primary", "imu"]
    containers = {
        "ov_msckf": Container(
            "dhdevspace/auto_mns:vio-estimator-openvins-69488123",
            command=("OPENVINS_CONFIG=/stack/config python3 /stack/check.py"
                     " && exec ros2 launch ov_msckf subscribe.launch.py"
                     " config_path:=/stack/config/estimator_config.yaml use_stereo:=true max_cameras:=2")),
    }
    # Ready once it tracks features: OpenVINS publishes its track image from the
    # first stereo frames, but its odometry only after the drone starts moving.
    ready = ["/ov_msckf/trackhist"]
    scoring = Scoring(checks={"ate_rmse_m": {"max": 2.0}, "availability": {"min": 0.9}})

    def setup(self):
        super().setup()                       # TEVV's follower flies the mission
        self.forward(self.stereo, left="/camera/front/image_raw", right="/camera/front_right/image_raw")
        self.forward(self.imu, "/imu/data")
        self.estimate_from("/ov_msckf/odomimu")
