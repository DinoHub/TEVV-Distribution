"""One stack instance flying several drones: a worked example of drones = "many".

A test that names this stack for several drones gives them all to one
instance, with one interface on every one of those drones (ADP's model: a
stack controls the entities it is given). Here TEVV's own follower flies each
drone's mission, and each drone's height above its spawn point is published
as a debug topic, recorded with the run and shown in Monitor. A swarm planner
has the same shape: for each drone, forward its inputs to the planner's
per-drone topics and read the planner's per-drone setpoints back.
"""
from tevv import Interface


class FollowMany(Interface):
    name = "TEVV's follower, one instance for many drones"
    description = ("One instance flies every drone a test gives it: TEVV's follower on each drone's mission, "
                   "with each drone's height as a debug topic. The shape of a multi-drone stack.")
    autopilot = "simpleflight"
    drones = "many"
    needs = ["ground_truth"]

    def setup(self):
        from std_msgs.msg import Float32

        for d in self.drones:                      # one handle per drone: d.name, d.gt_odom, d.forward(...)
            d.follow_waypoints()
            d.on(d.gt_odom, lambda msg, d=d: d.debug("height", Float32(data=float(msg.pose.pose.position.z))))
            self.log.info(f"{d.name}: {len(d.mission.get('points') or [])} point(s) to fly")
