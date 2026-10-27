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

See [docs/interface/stacks.md](../docs/interface/stacks.md) for every declaration.
