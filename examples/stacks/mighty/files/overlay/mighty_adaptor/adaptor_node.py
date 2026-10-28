#!/usr/bin/env python3
import copy
import rclpy
from rclpy.node import Node
from dynus_interfaces.msg import Goal
from nav_msgs.msg import Odometry
from dynus_interfaces.msg import State
from mavros_msgs.msg import PositionTarget
from rclpy.qos import qos_profile_sensor_data
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy


def get_vec3(msg, path):
    cur = msg
    for part in path.split('.'):
        cur = getattr(cur, part)
    return float(cur.x), float(cur.y), float(cur.z)


def get_scalar(msg, path, default=0.0):
    if not path:
        return default
    cur = msg
    for part in path.split('.'):
        cur = getattr(cur, part)
    return float(cur)


def assert_has_attr_path(msg, path, label):
    cur = msg
    traversed = []
    for part in path.split('.'):
        traversed.append(part)
        if not hasattr(cur, part):
            raise AssertionError(
                f"{label} mapping error: manifest path {path!r} is invalid. "
                f"Missing attribute {part!r} after "
                f"{'.'.join(traversed[:-1]) or '<root>'}. "
                f"Incoming message type: {type(msg).__name__}"
            )
        cur = getattr(cur, part)
    return cur


def assert_vec3_path(msg, path, label):
    cur = assert_has_attr_path(msg, path, label)
    if not (hasattr(cur, 'x') and hasattr(cur, 'y') and hasattr(cur, 'z')):
        raise AssertionError(
            f"{label} mapping error: manifest path {path!r} is not a Vector3-like field "
            f"with x/y/z. Incoming message type: {type(msg).__name__}"
        )
    return cur


def assert_scalar_path(msg, path, label):
    cur = assert_has_attr_path(msg, path, label)
    if hasattr(cur, 'x') or hasattr(cur, 'y') or hasattr(cur, 'z'):
        raise AssertionError(
            f"{label} mapping error: manifest path {path!r} resolved to a vector-like field, "
            f"but a scalar was expected. Incoming message type: {type(msg).__name__}"
        )
    return cur


def all_zero(msg, paths):
    for path in paths:
        cur = msg
        for part in path.split('.'):
            cur = getattr(cur, part)
        if hasattr(cur, 'x') and hasattr(cur, 'y') and hasattr(cur, 'z'):
            if (
                float(cur.x) != 0.0
                or float(cur.y) != 0.0
                or float(cur.z) != 0.0
            ):
                return False
        elif float(cur) != 0.0:
            return False
    return True


def get_bool_param(node, name, default=False):
    if node.has_parameter(name):
        return bool(node.get_parameter(name).value)
    return default


def resolve_publish_policy(autopilot, policy):
    autopilot = str(autopilot).strip().lower()
    policy = str(policy).strip().lower()
    if policy != 'auto':
        return policy
    if autopilot == 'px4':
        return 'always'
    if autopilot == 'ardupilot':
        return 'never'
    return 'never'


def resolve_start_phase(autopilot, phase):
    autopilot = str(autopilot).strip().lower()
    phase = str(phase).strip().lower()
    if phase != 'auto':
        return phase
    if autopilot == 'px4':
        return 'pre_mode'
    if autopilot == 'ardupilot':
        return 'post_mode'
    return 'post_mode'


class ExternalAdaptor(Node):
    def __init__(self):
        super().__init__('mighty_external_adaptor')
        self.declare_parameter('odom_external_topic', '/Copter1/ground_truth/odom')
        self.declare_parameter('odom_planner_topic', 'state')
        self.pub_odom = self.create_publisher(
            State,
            self.get_parameter('odom_planner_topic').value,
            10,
        )
        self.create_subscription(
            Odometry,
            self.get_parameter('odom_external_topic').value,
            self.odom_cb,
            10,
        )
        self.declare_parameter('term_goal_external_topic', '/goal')
        self.declare_parameter('term_goal_planner_topic', 'term_goal')
        self.pub_term_goal = None
        self.declare_parameter('occupancy_external_topic', '/Copter1/registered_point_cloud')
        self.declare_parameter('occupancy_planner_topic', 'sensor_point_cloud')
        self.pub_occupancy = None
        self.pub_out_planner_odom = None
        self.pub_out_debug_image = None
        self.declare_parameter('planner_output_topic', 'goal')
        self.declare_parameter('vehicle_output_topic', '/Copter1/mavros/setpoint_raw/local')
        self.declare_parameter('autopilot', 'px4')
        self.declare_parameter('heartbeat_enabled', True)
        self.declare_parameter('heartbeat_rate_hz', 20.0)
        self.declare_parameter('heartbeat_publish_policy', 'auto')
        self.declare_parameter('heartbeat_start_phase', 'auto')
        self.declare_parameter('heartbeat_prestream_sec', 1.0)
        self.declare_parameter('heartbeat_stale_timeout_sec', 20.0)
        self.declare_parameter('external_mode_active', False)
        self.autopilot = str(self.get_parameter('autopilot').value).strip().lower()
        self.heartbeat_enabled = bool(self.get_parameter('heartbeat_enabled').value)
        self.heartbeat_rate_hz = float(self.get_parameter('heartbeat_rate_hz').value)
        self.heartbeat_publish_policy = resolve_publish_policy(
            self.autopilot,
            self.get_parameter('heartbeat_publish_policy').value,
        )
        self.heartbeat_start_phase = resolve_start_phase(
            self.autopilot,
            self.get_parameter('heartbeat_start_phase').value,
        )
        self.heartbeat_prestream_sec = float(
            self.get_parameter('heartbeat_prestream_sec').value
        )
        self.heartbeat_stale_timeout_sec = float(
            self.get_parameter('heartbeat_stale_timeout_sec').value
        )
        self.external_mode_active = bool(
            self.get_parameter('external_mode_active').value
        )
        self.last_vehicle_msg = None
        self.last_vehicle_msg_valid = False
        self.first_heartbeat_stamp = None
        self.last_vehicle_msg_stamp = None
        self.pub_vehicle = self.create_publisher(
            PositionTarget,
            self.get_parameter('vehicle_output_topic').value,
            10,
        )
        # position_velocity: where the planner's frame sits in the vehicle's.
        # Empty topics: the planner's odometry input, and MAVROS's local
        # position next to vehicle_output_topic.
        self.declare_parameter('planner_frame_odom_topic', '')
        self.declare_parameter('vehicle_odom_topic', '')
        planner_frame_odom_topic = self.get_parameter('planner_frame_odom_topic').value
        if not planner_frame_odom_topic and self.has_parameter('odom_external_topic'):
            planner_frame_odom_topic = self.get_parameter('odom_external_topic').value
        planner_frame_odom_topic = planner_frame_odom_topic or '/Copter1/ground_truth/odom'
        vehicle_output_topic = self.get_parameter('vehicle_output_topic').value
        vehicle_odom_topic = self.get_parameter('vehicle_odom_topic').value
        if not vehicle_odom_topic and vehicle_output_topic.endswith('setpoint_raw/local'):
            vehicle_odom_topic = (
                vehicle_output_topic[: -len('setpoint_raw/local')] + 'local_position/odom'
            )
        vehicle_odom_topic = vehicle_odom_topic or '/Copter1/mavros/local_position/odom'
        self.planner_frame_pos = None
        self.vehicle_frame_pos = None
        self.create_subscription(
            Odometry,
            planner_frame_odom_topic,
            self.planner_frame_odom_cb,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            Odometry,
            vehicle_odom_topic,
            self.vehicle_frame_odom_cb,
            qos_profile_sensor_data,
        )
        self.get_logger().info(
            f'position_velocity: planner frame from {planner_frame_odom_topic}, '
            f'vehicle frame from {vehicle_odom_topic}'
        )
        self.heartbeat_timer = None
        if (
            self.heartbeat_enabled
            and self.heartbeat_rate_hz > 0.0
            and hasattr(self, 'pub_vehicle')
        ):
            self.heartbeat_timer = self.create_timer(
                1.0 / self.heartbeat_rate_hz,
                self.heartbeat_cb,
            )
        qos_profile = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(
            Goal,
            self.get_parameter('planner_output_topic').value,
            self.planner_output_cb,
            qos_profile,
        )
        self.get_logger().info('Adaptor ready')

    def odom_cb(self, msg):
        out = State()
        if hasattr(out, 'header'):
            out.header = msg.header
        if hasattr(out, 'pos'):
            out.pos.x = msg.pose.pose.position.x
            out.pos.y = msg.pose.pose.position.y
            out.pos.z = msg.pose.pose.position.z
        if hasattr(out, 'vel'):
            out.vel.x = msg.twist.twist.linear.x
            out.vel.y = msg.twist.twist.linear.y
            out.vel.z = msg.twist.twist.linear.z
        if hasattr(out, 'quat'):
            out.quat = msg.pose.pose.orientation
        self.pub_odom.publish(out)

    def publish_vehicle_msg(self, out):
        now = self.get_clock().now()
        self.last_vehicle_msg = copy.deepcopy(out)
        self.last_vehicle_msg_valid = True
        if self.first_heartbeat_stamp is None:
            self.first_heartbeat_stamp = now
        self.last_vehicle_msg_stamp = now
        self.pub_vehicle.publish(out)

    def heartbeat_cb(self):
        if not self.last_vehicle_msg_valid:
            return

        if self.last_vehicle_msg_stamp is None:
            return

        age_sec = (
            self.get_clock().now() - self.last_vehicle_msg_stamp
        ).nanoseconds / 1e9

        if age_sec > self.heartbeat_stale_timeout_sec:
            return

        if not self.heartbeat_enabled:
            return

        if self.heartbeat_publish_policy == 'never':
            return

        if (
            self.heartbeat_start_phase == 'post_mode'
            and not self.external_mode_active
        ):
            return

        msg = copy.deepcopy(self.last_vehicle_msg)
        if hasattr(msg, 'header'):
            msg.header.stamp = self.get_clock().now().to_msg()
        self.pub_vehicle.publish(msg)

    def planner_output_cb(self, msg):
        px, py, pz = get_vec3(msg, 'p')
        vx, vy, vz = get_vec3(msg, 'v')
        out = PositionTarget()
        out.header.stamp = (
            self.get_clock().now().to_msg()
        )
        if hasattr(msg, 'header'):
            out.header.frame_id = msg.header.frame_id
        out.coordinate_frame = PositionTarget.FRAME_LOCAL_NED
        offset = self.frame_offset()
        if offset is None:
            out.type_mask = (
                PositionTarget.IGNORE_PX
                | PositionTarget.IGNORE_PY
                | PositionTarget.IGNORE_PZ
                | PositionTarget.IGNORE_AFX
                | PositionTarget.IGNORE_AFY
                | PositionTarget.IGNORE_AFZ
            )
        else:
            out.type_mask = (
                PositionTarget.IGNORE_AFX
                | PositionTarget.IGNORE_AFY
                | PositionTarget.IGNORE_AFZ
            )
            out.position.x = px + offset[0]
            out.position.y = py + offset[1]
            out.position.z = pz + offset[2]
        out.velocity.x = vx
        out.velocity.y = vy
        out.velocity.z = vz
        out.yaw = get_scalar(
            msg, 'yaw', 0.0
        )
        out.yaw_rate = get_scalar(
            msg, 'dyaw', 0.0
        )
        self.publish_vehicle_msg(out)

    def planner_frame_odom_cb(self, msg):
        p = msg.pose.pose.position
        self.planner_frame_pos = (p.x, p.y, p.z)

    def vehicle_frame_odom_cb(self, msg):
        p = msg.pose.pose.position
        self.vehicle_frame_pos = (p.x, p.y, p.z)

    def frame_offset(self):
        if self.planner_frame_pos is None or self.vehicle_frame_pos is None:
            return None
        return tuple(
            v - p for v, p in zip(self.vehicle_frame_pos, self.planner_frame_pos)
        )


def main():
    rclpy.init()
    node = ExternalAdaptor()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
