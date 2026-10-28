# dhdevspace/auto_mns:mighty_algo_only-cyclone: the published mighty_algo_only with Cyclone DDS added.
# Every container of a stack runs on Cyclone (RMW_IMPLEMENTATION=rmw_cyclonedds_cpp,
# set by TEVV); an image without it cannot start a ROS node there.
#   docker build -t dhdevspace/auto_mns:mighty_algo_only-cyclone -f examples/images/mighty_algo_only-cyclone.Dockerfile examples/images
FROM dhdevspace/auto_mns:mighty_algo_only
USER root
RUN apt-get update && apt-get install -y --no-install-recommends ros-humble-rmw-cyclonedds-cpp \
 && rm -rf /var/lib/apt/lists/*
USER appuser
