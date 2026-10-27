# Example stacks

Finished stacks (`interface.py` and their files), imported from the v1.1
component packages with `./tevv stack import` and completed by hand. Your
stacks live in `stacks/`, which TEVV does not track: copy one there to use it.

```bash
cp -r examples/stacks/super stacks/
./tevv stack lock super      # pin its image by digest
./tevv stack check super
```

| Stack | What | Notes |
| --- | --- | --- |
| `openvins` | OpenVINS stereo VIO; TEVV's follower flies | Calibrated for the reference stereo rig; `check.py` refuses another. Its lockstep image (frame-status patch) is not published yet, so it declares no `Lockstep`. |
| `super` | SUPER local planner, ArduPilot | Lockstep participant on `/planner_state`; on sim time through `files/sim_time.launch.py`. |
| `mighty` | MIGHTY local planner, ArduPilot | Lockstep participant on `/NX01/point_A`; carries the position + velocity adaptor in `files/overlay/` until its image is rebuilt with it. |

Every container of a stack runs on Cyclone DDS, so its image needs
`ros-humble-rmw-cyclonedds-cpp`. The published OpenVINS, SUPER and MIGHTY images
do not have it: `images/` holds the one-line Dockerfiles that add it, and the stacks
name those `-cyclone` tags. Build them before a run (or push them once):

```bash
docker build -t dhdevspace/auto_mns:super_runtime-ms.1-cyclone -f examples/images/super_runtime-ms.1-cyclone.Dockerfile examples/images
docker build -t dhdevspace/auto_mns:mighty_algo_only-cyclone -f examples/images/mighty_algo_only-cyclone.Dockerfile examples/images
docker build -t dhdevspace/auto_mns:vio-estimator-openvins-69488123-cyclone -f examples/images/vio-estimator-openvins-69488123-cyclone.Dockerfile examples/images
```

## Example tests

A test (`tests/<id>.yaml`) says which stack flies each drone of a scenario;
the dashboard's Run step lists the tests in `tests/`, which TEVV does not track
either. `tests/` here holds tests that fly the stacks above:

| Test | Scenario | Who flies |
| --- | --- | --- |
| `planner-lockstep-super` | `planner-lockstep-xfs` (yard slalom) | Drone1: `super` |
| `planner-lockstep-mighty` | `planner-lockstep-xfs` (yard slalom) | Drone1: `mighty` |

```bash
cp examples/tests/planner-lockstep-super.yaml tests/
./tevv campaign run tests/planner-lockstep-super.yaml
```

The lockstep vs free comparisons are campaigns beside the scenario:
`scenarios/planner-lockstep-xfs/CampaignSpec.super.yaml` and
`CampaignSpec.mighty.yaml`. Neither is named `CampaignSpec.yaml`, which
`campaign run <folder>` would run in place of the scenario itself.

See [docs/interface/stacks.md](../docs/interface/stacks.md) for every declaration.
