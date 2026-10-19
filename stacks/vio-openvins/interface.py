"""OpenVINS (stereo VIO) estimating its drone's pose while TEVV flies the
mission: a worked example of a stack that estimates but does not fly.

OpenVINS runs unmodified in its own container. This file writes its config
from TEVV's description of the stereo pair and the IMU (into the shared
folder OpenVINS waits on), feeds it the images and IMU under the names that
config gives, and hands its odometry back to TEVV as the estimate, which
TEVV scores. TEVV's own follower flies the drone (follow_waypoints).
"""
import math

from tevv import Container, Interface

LEFT, RIGHT, IMU = "/cam0/image_raw", "/cam1/image_raw", "/imu0"
# The camera's optical frame (z forward, x right, y down) in its body frame (x forward, FLU).
R_BODY_OPTICAL = [[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]]


def rot_rpy_deg(roll, pitch, yaw):
    r, p, y = (math.radians(v) for v in (roll, pitch, yaw))
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return [[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr]]


def t_imu_cam(cal):
    """T_imu_cam for OpenVINS: TEVV's IMU is on base_link (FLU), so it is the
    optical frame's pose in base_link."""
    mount = cal["T_base_cam"]
    rpy = rot_rpy_deg(*mount["rpy_deg"])
    r = [[sum(rpy[i][k] * R_BODY_OPTICAL[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    x, y, z = mount["xyz"]
    rows = [r[0] + [x], r[1] + [y], r[2] + [z], [0.0, 0.0, 0.0, 1.0]]
    return "\n" + "\n".join(f"    - [{', '.join(f'{v:.9f}' for v in row)}]" for row in rows)


def camera_block(index, cal, topic, other):
    k = cal["K"]
    return (f"cam{index}:\n  T_imu_cam:{t_imu_cam(cal)}\n  cam_overlaps: [{other}]\n  camera_model: pinhole\n"
            f"  distortion_coeffs: [0.0, 0.0, 0.0, 0.0]\n  distortion_model: radtan\n"
            f"  intrinsics: [{k[0]}, {k[4]}, {k[2]}, {k[5]}]\n  resolution: [{cal['width']}, {cal['height']}]\n"
            f"  rostopic: {topic}\n  timeshift_cam_imu: 0.0\n")


class VioOpenvins(Interface):
    name = "OpenVINS on TEVV's flight"
    description = ("TEVV's follower flies the drone through its mission's points; OpenVINS estimates the pose "
                   "from the stereo cameras and IMU. For estimator tests.")
    autopilot = "simpleflight"
    needs = ["ground_truth", "stereo_primary", "imu"]
    containers = {
        "openvins": Container(
            image="dhdevspace/auto_mns:vio-estimator-openvins-69488123-cyclone",
            command="until [ -f /shared/estimator_config.yaml ]; do sleep 1; done; "
                    "exec /entrypoint.sh ros2 launch ov_msckf subscribe.launch.py "
                    "config_path:=/shared/estimator_config.yaml use_stereo:=true max_cameras:=2"),
    }

    def setup(self):
        self.write_config()
        self.follow_waypoints()                       # TEVV flies the mission
        self.forward(self.stereo, left=LEFT, right=RIGHT)
        self.forward(self.imu, IMU)
        self.estimate_from("/ov_msckf/odomimu")       # its IMU is TEVV's base_link

    def write_config(self):
        stereo = self.stereo
        imucam = ("%YAML:1.0\n" + camera_block(0, stereo.left.calibration, LEFT, 1)
                  + camera_block(1, stereo.right.calibration, RIGHT, 0))
        imu = ((self.folder / "files" / "kalibr_imu_chain.yaml").read_text()
               .replace("@IMU_RATE@", str(self.imu.calibration.get("rate_hz_nominal", 200)))
               .replace("@IMU_TOPIC@", IMU))
        (self.shared / "kalibr_imucam_chain.yaml").write_text(imucam)
        (self.shared / "kalibr_imu_chain.yaml").write_text(imu)
        tmp = self.shared / "estimator_config.yaml.tmp"
        tmp.write_text((self.folder / "files" / "estimator_config.yaml").read_text())
        tmp.replace(self.shared / "estimator_config.yaml")   # last: OpenVINS starts when this appears
        self.log.info(f"OpenVINS config written for stereo pair {stereo.calibration.get('left')}/"
                      f"{stereo.calibration.get('right')}")
