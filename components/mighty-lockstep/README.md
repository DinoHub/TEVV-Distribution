# mighty-lockstep

The MIGHTY local planner (`dhdevspace/auto_mns:mighty_algo_only`, unmodified) as a
sim-time lockstep participant, with the configuration tuned for the XFS yard
(`files/mighty.yaml`: map buffer 15 m, so the search can route round the
container row). Attach it with `--component components/mighty-lockstep`, or run
`scenarios/planner-lockstep-xfs/CampaignSpec.mighty.yaml`.

- **`lockstep: {participant: mighty, ack_on: /NX01/point_A, timeout_ms: 1000}`.**
  MIGHTY replans on a 10 ms timer in a callback group of its own and publishes
  `point_A` (and its trajectory) on every successful replan; its setpoints come
  from another group and keep flowing during a replan, so they would prove
  nothing. `point_A` is a `geometry_msgs/PointStamped`, which the bridge's relay
  can read; the trajectory's `dynus_interfaces` type is not in the bridge image.
  MIGHTY publishes nothing while it has no goal, so the timeout is short: an idle
  slot (between goals, landing) costs 1 s of wall time, not of flight.
- **`files/sim_time.launch.py`** runs the adaptor launch with `use_sim_time`:
  MIGHTY samples its trajectory at `now()`, which must be sim time when the
  simulation holds.

MIGHTY's timers are wall-clock timers, as SUPER's are: with the simulation slower
than real time it replans more often per simulated second.
