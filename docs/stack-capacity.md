# Stack capacity: drones, stacks and sensor rate

Whether a machine can onboard N drones, each flown by its own autonomy stack, and still give every stack its cameras at the rate it asks for. Measured 2026-10-28.

## The answer

Ten drones, each with its own OpenVINS stereo stack, reach the full 30 Hz at the stack in lockstep with no missed capture slots, measured on the eight that took off (two did not take off, for a reason not yet known), at about 20 minutes of wall time per minute of mission on this host. Flying free, none of them reach it: one drone gets 16.3 Hz, and the rate falls roughly as one over the number of drones (3.1 Hz at ten).

The notes under the table say what is known about the two that did not take off, and why the lockstep rows will be flown again. Lockstep gives the rate, not real time: the stack sees time at the right rate because the simulation waits for it.

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
| 1 | free | 16.3 Hz (55%) | not counted | 1.0 | 1.0 | 200 | 707% | 92%, 6137 MiB | 1/1 flown | no |
| 1 | lockstep | 29.7 Hz (99%) | 0 | 0.4192 | 2.4 | 355 | 660% | 91%, 7512 MiB | points reached 4 of 5 | yes |
| 2 | free | 14.5 Hz (48%) | not counted | 1.0 | 1.0 | 205 | 1006% | 92%, 6538 MiB | 2/2 flown | no |
| 2 | lockstep | 29.8 Hz (99%) | 0 | 0.2816 | 3.6 | 490 | 742% | 94%, 8732 MiB | points reached 3 of 5 | yes |
| 5 | free | 7.5 Hz (25%) | not counted | 1.0005 | 1.0 | 205 | 1752% | 91%, 6728 MiB | 5/5 flown | no |
| 5 | lockstep | 29.8 Hz (99%) | 0 | 0.1574 | 6.4 | 875 | 2342% | 98%, 12324 MiB | points reached 1 of 5 | yes |
| 10 | free | 3.1 Hz (10%) | not counted | 0.9915 | 1.0 | 235 | 1900% | 64%, 8384 MiB | 10/10 flown | no |
| 10 | lockstep | 29.9 Hz (100%) on the 8 that flew | 0 | 0.0506 | 19.8 | 4755 | 2313% | 100%, 15832 MiB | points reached 1 of 5 | rate yes; 2 drones did not take off |

Peak CPU is the sum over all containers (100% is one core). Peak GPU is utilisation and memory used. Missions: free, how many missions were flown to the end; lockstep, the points reached of the square's five.

These lockstep missions ended early because TEVV's follower timed its route on wall time (fixed), so the lockstep rates were measured over a short flight and mostly after it; the re-flown numbers will replace them.

### Notes on ten drones in lockstep

- The first attempt failed before flight: TEVV's ready wait gave up at 240 s while probing ten stacks one after another under load. The ready wait now probes each drone's bridge once per pass and waits longer under lockstep. In the second attempt all ten were ready by 365 s.
- Two drones (Drone3 and Drone7) never took off. Their ArduPilot never started using GPS within the 240 s (simulation time) take-off budget, so it never gave a position and could not arm. The simulator's GPS gave them a 3D fix like the others, and the other eight started using GPS and armed in the same second. This was not seen at ten drones free or at five or fewer in lockstep. The cause is not yet known.
- GPU memory reached 15832 of 16303 MiB. Ten drones with two cameras each is near this card's memory limit.

## What the stack gets in the live check

`./tevv stack live-check STACK --lockstep` flies one drone and probes the stack's cameras from inside the stack (see [Stack interface](interface/stacks.md)). Same host, one drone each.

| Stack | Camera | Mode | Rate at the stack (of 30 Hz) | Real-time factor | camera_info the stack got |
| --- | --- | --- | --- | --- | --- |
| OpenVINS fisheye stack | 752x480 Kannala-Brandt, exact | lockstep | 29.6 to 29.8 Hz | 0.38 | the team's exact calibration |
| OpenVINS fisheye stack | closest-match pinhole | free | 19.4 Hz | 1.0 | closest match (fx 0.7 px off; distortion differs by up to 95.6 px at the edge) |
| OpenVINS pinhole stack | 640x480 pinhole radtan, exact by resampling | lockstep | 29.5 to 30.0 Hz | 0.42 | the team's exact calibration |
| OpenVINS pinhole stack | same | free | 16.7 Hz (56%) | 1.0 | exact |

## Conclusions

- Free running on this host: with this template no drone count reaches 30 Hz at the stack, not even one drone (16.3 Hz). The rate falls roughly as one over N: 16.3, 14.5, 7.5 and 3.1 Hz for 1, 2, 5 and 10 drones.
- Lockstep: every drone count tested delivers the full 30 Hz at the stack with no missed slots, at ten drones on the eight that took off (two did not take off, for a reason not yet known).
- The cost is wall time. A minute of mission takes about 2.4 minutes with one drone, 3.6 with two, 6.4 with five and 19.8 with ten.
- Lockstep gives the rate, not real time.
- At ten drones the card's memory is nearly full and two drones did not take off, for a reason not yet known.

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

Without `--timeout`, the tool's wall cap scales with the number of drones and the mode: 3600 s free, 900 + 600 s per drone in lockstep (6900 s at ten drones; the ten-drone lockstep run took 4755 s). On a slower host give more, for example `--timeout 7200` or above.

Prepare clones the template into one stack per drone and writes the scenario and test. Each run flies the test with `mns-stacks campaign run`, probes every stack from inside, and appends its rows to `results.md` in the output folder.
