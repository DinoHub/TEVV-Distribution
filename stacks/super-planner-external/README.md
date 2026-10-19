# SUPER in your own Docker network

This stack is SUPER started by you, not by TEVV (`network = Network("my-autonomy", domain=0)`
in `interface.py`). TEVV joins its interface to your network for each run; it starts and stops
none of your containers.

Start SUPER once, from the workspace root:

```bash
docker network create my-autonomy
docker run -d --name my-super --network my-autonomy \
  -e ROS_DOMAIN_ID=0 -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  -v "$PWD/stacks/super-planner/files:/stack/files:ro" \
  dhdevspace/auto_mns:super_runtime-ms.1-cyclone \
  bash -lc 'set +u && source /opt/ros/humble/setup.bash \
    && source /workspace/generated/super_planner/.planner_ws/ros_ws/install/setup.sh \
    && exec ros2 run super_planner fsm_node --ros-args -p config_name:=/stack/files/config/click.yaml'
```

Then run the test and read the results:

```bash
./tevv run super-external
./tevv results super-external
```

Afterwards, stop SUPER yourself: `docker rm -f my-super` (and `docker network rm my-autonomy`).
If the network is not there when a run starts, the run says so and stops before anything flies.

SUPER keeps its state between runs, because nothing restarts it. Restart it (`docker restart my-super`)
when a run ended mid-flight.
