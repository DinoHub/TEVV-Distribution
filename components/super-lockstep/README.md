# super-lockstep

The SUPER local planner (`dhdevspace/auto_mns:super_runtime-ms.1`, unmodified) as a
sim-time lockstep participant. Attach it with
`--component components/super-lockstep`, or list it under `mns.components` in a
CampaignSpec (`scenarios/planner-lockstep-xfs`).

What the package adds to the image, all from this folder:

- **`lockstep: {participant: super, ack_on: /planner_state, timeout_ms: 10000}`.**
  The bridge's lockstep relay acknowledges each lockstep slot when SUPER publishes
  on `/planner_state` after sim time reached it. That timer shares SUPER's exclusive
  callback group with the replan, so it stops exactly while a replan blocks, and the
  simulation waits for the plan instead of the drone flying the old one. SUPER's
  `/planner_result` is not used: it is quiet while SUPER has no goal, and every slot
  between goals would wait the full timeout.
- **`files/sim_time.launch.py`.** The adaptor launch file declares no
  `use_sim_time`, so SUPER sampled its trajectories on the wall clock, which runs on
  while the simulation holds. The wrapper sets `use_sim_time` for every node it
  starts and passes the launch arguments through.
- **`files/wait_airborne.py`.** SUPER starts once the drone is airborne and steady.
- **`files/config/click.yaml`.** SUPER's planner configuration for the XFS yard.

SUPER's own timers are wall-clock timers (`create_wall_timer`), so under lockstep,
with the simulation slower than real time, it replans more often per simulated second
than it would in real time. Lockstep bounds how long the drone flies without a new
plan; a strictly fair comparison also needs the planner's timers on sim time.
