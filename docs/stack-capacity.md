# Stack capacity: drones, stacks and sensor rate

Whether a machine can onboard N drones, each flown by its own autonomy stack, and still give every stack its cameras at the rate it asks for. Measured 2026-10-28.

## The answer

Ten drones, each with its own OpenVINS stereo stack, all flew the whole square at the full 30 Hz at the stack in lockstep, with no missed capture slots. It takes about 22 minutes of wall time per minute of mission on this host. Flying free, none of them reach 30 Hz: one drone gets 16.3 Hz, and the rate falls roughly as one over the number of drones (3.0 Hz at ten).

The notes under the table say what happened on an earlier layout of the ten drones. Lockstep gives the rate, not real time: the stack sees time at the right rate because the simulation waits for it.

## What was measured

- **Template.** `ov-exact`: an OpenVINS stereo stack with two 30 Hz pinhole cameras (`cam0`, `cam1`), rendered at the stack's exact calibration.
- **One stack per drone.** Each drone flies its own copy of the template (`cap-01` to `cap-NN`) on ArduPilot, on the XFS yard, one 6 m square each at 2.5 m. Lockstep is ArduPilot only; PX4 is refused.
- **Reached.** A run reaches the rate when the stack's own lowest camera rate, measured inside the stack in simulation time, is at least 95% of the rate asked, and under lockstep no capture slot was missed.
- **Free** means the simulation runs at its own pace and the cameras publish whatever the host can render.
- **Lockstep** means the simulation holds at each capture slot until every camera frame is delivered, so each camera gets its full rate in simulation time and a slow step costs wall time, never flight time.
- **Wall time per minute of mission** is one divided by the real-time factor.

## Capacity: OpenVINS stereo, exact calibration

| N | Mode | Lowest camera rate at the stack (of 30 Hz) | Missed slots | Real-time factor | Wall minutes per mission minute | Wall time of the run (s) | Peak CPU | Peak GPU | Missions | Reached |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | free | 16.3 Hz (55%) | not counted | 1.0 | 1.0 | 200 | 707% | 92%, 6137 MiB | 1 of 1 passed | no |
| 1 | lockstep | 29.7 Hz (99%) | 0 | 0.4134 | 2.4 | 400 | 687% | 100%, 7447 MiB | 1 of 1 passed; points reached 5 of 5 | yes |
| 2 | free | 14.5 Hz (48%) | not counted | 1.0 | 1.0 | 205 | 1006% | 92%, 6538 MiB | 2 of 2 passed | no |
| 2 | lockstep | 29.8 Hz (99%) | 0 | 0.2848 | 3.5 | 560 | 785% | 94%, 8741 MiB | 2 of 2 passed; points reached 5 of 5 each | yes |
| 5 | free | 7.5 Hz (25%) | not counted | 1.0005 | 1.0 | 205 | 1752% | 91%, 6728 MiB | 5 of 5 passed | no |
| 5 | lockstep | 29.8 Hz (99%) | 0 | 0.1552 | 6.4 | 1045 | 1159% | 98%, 12476 MiB | 5 of 5 passed; points reached 5 of 5 each | yes |
| 10 | free | 3.0 Hz (10%) | not counted | 0.9987 | 1.0 | 225 | 1802% | 65%, 7496 MiB | 10 of 10 passed | no |
| 10 | lockstep | 29.8 Hz (99%) | 0 | 0.0459 | 21.8 | 3440 | 2482% | 100%, 15832 MiB | 10 of 10 passed; points reached 5 of 5 each | yes |

Peak CPU is the sum over all containers (100% is one core). Peak GPU is utilisation and memory used. Missions: how many drones passed their mission (it ended without touching anything), and under lockstep the points reached of the square's five. The wall time column is seconds; wall minutes per mission minute is one divided by the real-time factor. The one-, two- and five-drone rows were flown on an earlier layout, whose squares at those counts stayed clear of the yard's containers (all passed).

### Notes on ten drones in lockstep

- An earlier 12 m grid, four drones wide, flew some squares into the yard's containers, in free and lockstep runs alike. The layout now keeps every square in the clear area (two columns 12 m apart, rows 9 m apart), which limits a run to at most 10 drones on XFS. The ten-drone rows above were flown on the new layout.
- On the earlier layout, in two of three ten-drone lockstep runs, one drone's ArduPilot never started using GPS within the 240 s (simulation time) take-off budget, so it never gave a position and could not take off. Both such drones stood in a column on lower ground that the new layout no longer uses, and it did not recur on the new layout. The cause is not established.
- GPU memory reached 15832 of 16303 MiB. Ten drones with two cameras each is near this card's memory limit.
- The accepted hold (`r.Fisheye.LockstepHold 0`) is not usable at ten drones: in two attempts every drone's ground truth read the same height, about 175 to 185 m off, from the start, and no mission flew.
- The first attempt failed before flight: TEVV's ready wait gave up at 240 s while probing ten stacks one after another under load. The ready wait now probes each drone's bridge once per pass and waits longer under lockstep.

## What the stack gets in the live check

`./tevv stack live-check STACK --lockstep` flies one drone and probes the stack's cameras from inside the stack (see [Stack interface](interface/stacks.md)). Same host, one drone each.

| Stack | Camera | Mode | Rate at the stack (of 30 Hz) | Real-time factor | camera_info the stack got |
| --- | --- | --- | --- | --- | --- |
| OpenVINS fisheye stack | 752x480 Kannala-Brandt, exact | lockstep | 29.6 to 29.8 Hz | 0.38 | the team's exact calibration |
| OpenVINS fisheye stack | closest-match pinhole | free | 19.4 Hz | 1.0 | closest match (fx 0.7 px off; distortion differs by up to 95.6 px at the edge) |
| OpenVINS pinhole stack | 640x480 pinhole radtan, exact by resampling | lockstep | 29.5 to 30.0 Hz | 0.42 | the team's exact calibration |
| OpenVINS pinhole stack | same | free | 16.7 Hz (56%) | 1.0 | exact |

## Conclusions

- Free running on this host: with this template no drone count reaches 30 Hz at the stack, not even one drone (16.3 Hz). The rate falls roughly as one over N: 16.3, 14.5, 7.5 and 3.0 Hz for 1, 2, 5 and 10 drones.
- Lockstep: every drone count tested delivers the full 30 Hz at the stack with no missed slots. At ten drones, all ten flew the whole square at the full 30 Hz at the stack.
- The cost is wall time. A minute of mission takes about 2.4 minutes with one drone, 3.5 with two, 6.4 with five and 21.8 with ten.
- Lockstep gives the rate, not real time.
- At ten drones the card's memory is nearly full (15832 of 16303 MiB).

## Host

| | |
| --- | --- |
| CPU | Intel Core Ultra 9 285K, 24 cores |
| Memory | 62 GB |
| GPU | NVIDIA GeForce RTX 5080, 16303 MiB, driver 580.178.04 |
| Simulator | TEVV runtime host v1.1 lockstep build, level XFS |
| Interface image | built from the lockstep branch |
| Autopilot | ArduPilot |

Numbers from another host will differ, mostly in the real-time factor. Run nothing else on the GPU while measuring.

## Reproduce

The tool is `tools/stack-capacity/capacity.py` in MnS-Integration-Platform; its README has the full options.

```bash
python3 tools/stack-capacity/capacity.py prepare \
  --template ov-exact --count 10 --out /data/capacity/n10 \
  --workspace "$MNS_WORKSPACE_ROOT"
python3 tools/stack-capacity/capacity.py run --dir /data/capacity/n10 --mode free
python3 tools/stack-capacity/capacity.py run --dir /data/capacity/n10 --mode lockstep --grid-hz 30
```

Without `--timeout`, the tool's wall cap scales with the number of drones and the mode: 3600 s free, 900 + 600 s per drone in lockstep (6900 s at ten drones; the ten-drone lockstep run took 3440 s). On a slower host give more, for example `--timeout 7200` or above.

Prepare clones the template into one stack per drone and writes the scenario and test. Each run flies the test with `mns-stacks campaign run`, probes every stack from inside, and appends its rows to `results.md` in the output folder.
