# dhdevspace/auto_mns:super_runtime-ms.1-cyclone: the published super_runtime-ms.1 with Cyclone DDS added.
# Every container of a stack runs on Cyclone (RMW_IMPLEMENTATION=rmw_cyclonedds_cpp,
# set by TEVV); an image without it cannot start a ROS node there.
#   docker build -t dhdevspace/auto_mns:super_runtime-ms.1-cyclone -f examples/images/super_runtime-ms.1-cyclone.Dockerfile examples/images
FROM dhdevspace/auto_mns:super_runtime-ms.1
USER root
RUN apt-get update && apt-get install -y --no-install-recommends ros-humble-rmw-cyclonedds-cpp \
 && rm -rf /var/lib/apt/lists/*
USER appuser
