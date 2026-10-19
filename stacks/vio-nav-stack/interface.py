"""A whole stack under test: OpenVINS (stereo VIO) feeding SUPER (a local
planner), which flies on OpenVINS's estimate, not on ground truth. A worked
example of a stack that estimates its own pose and flies on it.

Frames. OpenVINS's world is fixed where it initialised, with its own heading;
goals and commands are in TEVV's odom. So the stack takes one known start
pose, as a real mission gets its origin from the operator: the ground truth
nearest the stamp of OpenVINS's first estimate gives T_odom_vio, once. After
that ground truth is no longer read, and SUPER flies on the estimate alone:
when OpenVINS drifts, SUPER's idea of where it is drifts with it. That is what
a stack test measures.
"""
import json
import math

from tevv import Container, Interface

SUPER_ODOM = "/px4vision_custom_0/mavros/local_position/odom"   # files/config/click.yaml
SUPER_CLOUD = "/px4vision_custom_0/lidar"
SUPER_GOAL = "/goal"
SUPER_SETPOINT = "/px4vision_custom_0/mavros/setpoint_raw/local"
VIO_ODOM = "/ov_msckf/odomimu"
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



def q_mul(a, b):
    """Hamilton product of quaternions (x, y, z, w)."""
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def q_rotate(q, v):
    x, y, z, _ = q_mul(q_mul(q, (v[0], v[1], v[2], 0.0)), (-q[0], -q[1], -q[2], q[3]))
    return (x, y, z)


def pose_of(msg):
    p, o = msg.pose.pose.position, msg.pose.pose.orientation
    return (p.x, p.y, p.z), (o.x, o.y, o.z, o.w)


def stamp_s(msg):
    return msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9


def align(gt, vio):
    """T_odom_vio = T_odom_base (ground truth) * inverse(T_vio_base (estimate))."""
    (tg, qg), (tv, qv) = gt, vio
    q = q_mul(qg, (-qv[0], -qv[1], -qv[2], qv[3]))
    r = q_rotate(q, tv)
    return (tg[0] - r[0], tg[1] - r[1], tg[2] - r[2]), q


def apply(transform, pose):
    (t, q), (tp, qp) = transform, pose
    r = q_rotate(q, tp)
    return (t[0] + r[0], t[1] + r[1], t[2] + r[2]), q_mul(q, qp)


def velocity_command(msg):
    """SUPER's PositionTarget -> TEVV's command: its velocity (odom ENU) and yaw."""
    from mavros_msgs.msg import PositionTarget as PT
    out = PT()
    out.header.stamp = msg.header.stamp
    out.header.frame_id = "odom"
    out.coordinate_frame = PT.FRAME_LOCAL_NED
    out.type_mask = (PT.IGNORE_PX | PT.IGNORE_PY | PT.IGNORE_PZ | PT.IGNORE_AFX | PT.IGNORE_AFY
                     | PT.IGNORE_AFZ | PT.IGNORE_YAW_RATE)
    out.velocity = msg.velocity
    out.yaw = msg.yaw
    return out


class VioNavStack(Interface):
    name = "VIO navigation stack (OpenVINS + SUPER)"
    description = "OpenVINS estimates the pose from the stereo pair and IMU; SUPER plans and flies on it."
    autopilot = "px4"
    needs = ["ground_truth", "stereo_primary", "imu", "point_cloud"]
    containers = {
        "openvins": Container(
            image="dhdevspace/auto_mns:vio-estimator-openvins-69488123-cyclone",
            command="until [ -f /shared/estimator_config.yaml ]; do sleep 1; done; "
                    "exec /entrypoint.sh ros2 launch ov_msckf subscribe.launch.py "
                    "config_path:=/shared/estimator_config.yaml use_stereo:=true max_cameras:=2"),
        "super": Container(
            image="dhdevspace/auto_mns:super_runtime-ms.1-cyclone",
            command="set +u && source /opt/ros/humble/setup.bash"
                    " && source /workspace/generated/super_planner/.planner_ws/ros_ws/install/setup.sh"
                    " && exec ros2 run super_planner fsm_node --ros-args"
                    " -p config_name:=/stack/files/config/click.yaml"),
    }
    ready = ["/planner_state"]        # SUPER's state machine is up (it needs OpenVINS's estimate first)

    def setup(self):
        from nav_msgs.msg import Odometry

        self.write_config()
        self.forward(self.stereo, left=LEFT, right=RIGHT)
        self.forward(self.imu, IMU)
        self.forward(self.point_cloud, SUPER_CLOUD)
        self.forward(self.next_waypoint, SUPER_GOAL)
        self.command_from(SUPER_SETPOINT, convert=velocity_command)
        self.super_odom = self.publisher(SUPER_ODOM, Odometry)
        self.truth, self.transform = [], None
        self.on(self.gt_odom, self.on_truth)
        self.subscribe(VIO_ODOM, Odometry, self.on_vio)

    def on_truth(self, msg):
        if self.transform is None:                 # only until the start pose is taken
            self.truth.append((stamp_s(msg), pose_of(msg)))
            del self.truth[:-400]

    def on_vio(self, msg):
        msg.header.frame_id, msg.child_frame_id = "odom", "base_link"
        self.send_estimate(msg)                    # OpenVINS's IMU is TEVV's base_link; TEVV aligns worlds
        if self.transform is None:
            if not self.truth:
                return
            t = stamp_s(msg)
            _, gt = min(self.truth, key=lambda item: abs(item[0] - t))
            self.transform, self.truth = align(gt, pose_of(msg)), []
            (x, y, z), q = self.transform
            self.log.info(f"start pose taken: T_odom_vio t=({x:.2f}, {y:.2f}, {z:.2f}); ground truth no longer read")
            (self.shared / "start_pose.json").write_text(json.dumps(
                {"taken_at_stamp": t, "T_odom_vio": {"t": [x, y, z], "q": list(q)}}, indent=2) + "\n")
        (x, y, z), q = apply(self.transform, pose_of(msg))
        out = Odometry()
        out.header.stamp = msg.header.stamp
        out.header.frame_id, out.child_frame_id = "odom", "base_link"
        p, o = out.pose.pose.position, out.pose.pose.orientation
        p.x, p.y, p.z = x, y, z
        o.x, o.y, o.z, o.w = q
        out.twist = msg.twist                      # body-frame velocity: unchanged by a world transform
        self.super_odom.publish(out)
        self.debug("super_odom", out)              # what SUPER believed: recorded, shown in Lichtblick

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
        tmp.replace(self.shared / "estimator_config.yaml")
