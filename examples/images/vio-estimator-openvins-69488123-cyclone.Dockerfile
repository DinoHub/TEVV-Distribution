# dhdevspace/auto_mns:vio-estimator-openvins-69488123-cyclone: the published vio-estimator-openvins-69488123 with Cyclone DDS added.
# Every container of a stack runs on Cyclone (RMW_IMPLEMENTATION=rmw_cyclonedds_cpp,
# set by TEVV); an image without it cannot start a ROS node there.
#   docker build -t dhdevspace/auto_mns:vio-estimator-openvins-69488123-cyclone -f examples/images/vio-estimator-openvins-69488123-cyclone.Dockerfile examples/images
FROM dhdevspace/auto_mns:vio-estimator-openvins-69488123
USER root
RUN apt-get update && apt-get install -y --no-install-recommends ros-humble-rmw-cyclonedds-cpp \
 && rm -rf /var/lib/apt/lists/*
