# TEVV

TEVV is a containerised simulation environment for testing drone autonomy.
You author a scenario in ScenarioLab (an Unreal editor): the world, the drones
and each drone's mission. You say who flies each drone with a stack (your
software and a Python `interface.py` that wires it to TEVV's topics). TEVV
generates and runs it (Unreal + Cosys-AirSim; SimpleFlight, PX4 or ArduPilot
per drone; ROS 2 Humble); each stack flies its drone from take-off to
landing, and TEVV judges each mission. Everything runs in Docker,
from a terminal or a browser dashboard.

This repository is the customer distribution (`DinoHub/TEVV-Distribution`;
its historical name is `M-S-Simulation-Runtime-Stack`): it holds the whole
product, not one stack.

## Requirements

- Ubuntu 22.04 or later with a desktop session, and an NVIDIA GPU with a current driver
- Docker Engine with Compose v2, and the NVIDIA Container Toolkit
- About 35 GB of free disk for the first setup
- Google Chrome or Chromium for the dashboard
- Access to the private `dhdevspace/auto_mns` images (Docker Hub) and the
  `DinoHub/TEVV-Airsim` pack releases (GitHub). Ask your TEVV contact.

`./setup.sh` checks each of these and prints the fix for anything missing.

## Quick start

```bash
git clone https://github.com/DinoHub/TEVV-Distribution.git tevv
cd tevv
./setup.sh           # checks the machine, logs in to Docker Hub, pulls the images
./download-packs.sh  # downloads the starter levels (logs in to GitHub)
./tevv up            # the dashboard: open http://localhost:3001 in Chrome
```

Then fly a test from a terminal, or from the dashboard:

```bash
./tevv run scenarios/vio-baseline-box             # TEVV's built-in stack (tevv-default) flies it
./tevv results vio-baseline-box
./tevv suite run local-planner --stack my-planner # a kind of test, flown by your stack
```

To test your own software, write a stack: [docs/interface/](docs/interface/README.md).
`./tevv help` lists every command. Stop the dashboard with `./tevv down`.

## Find your way

**Use it**

| I want to... | Read |
| --- | --- |
| test my own planner, estimator or whole stack | [Testing your autonomy](docs/interface/README.md) |
| go from a fresh clone to my first rosbag | [User Guide](docs/USER_GUIDE.md) |
| connect my own autonomy stack to a running simulation | [User Guide: connecting your autonomy stack](docs/USER_GUIDE.md#connecting-your-autonomy-stack) |
| know which ROS 2 topics a stack will publish | [What will this stack publish?](docs/topics.md) |
| fly, author or run a campaign from a terminal, without the browser | [Headless: `make fly`, `make author`, `make campaign`](docs/stacks.md) |
| choose a fisheye rig (tiled or shared cubemap) and set it up for VIO | [Fisheye rig performance](docs/fisheye-rig-performance.md) |
| fly a scored run matrix to characterise an estimator | [Campaigns](docs/campaigns.md), then [the reference campaign](scenarios/vio-reference/README.md) |
| fly the same campaign on a GPU cluster (NVIDIA OSMO) | [Campaigns: OSMO](docs/campaigns.md#the-same-campaign-on-a-cluster-osmo), then the [OSMO runbook](docs/osmo-runbook.md) |
| fix something that went wrong | [User Guide: troubleshooting](docs/USER_GUIDE.md#9-troubleshooting) |

**Understand it**

| I want to... | Read |
| --- | --- |
| see which service does what, and which file each step leaves on disk | [How it fits together](docs/how-it-fits-together.md) |
| see how OSMO and Kubernetes map onto this repo | [OSMO and Kubernetes for this repo](docs/osmo-kubernetes-concepts.md), [One run, end to end](docs/osmo-run-flow.md) |
| know what each evaluator measures, and what decides pass or fail on OSMO | [Evaluation on OSMO](docs/osmo-evaluation.md) |
| know what Loki and Alloy keep, and how to check them | [Logs on OSMO](docs/osmo-logs.md) |
| read the TEVV platform architecture this stack maps onto | [docs/platform-architecture/](docs/platform-architecture/README.md) |
| know where runs, bags and packs are stored | [User Guide: where everything is stored](docs/USER_GUIDE.md#7-where-everything-is-stored) |

**Maintain it**

| I want to... | Read |
| --- | --- |
| pick an engine line, or install, update or remove content packs | [packs/README.md](packs/README.md) |
| change, pin or verify a container image | [Changing a container image](docs/images.md) |
| understand which images `make dashboard` pulls, or run my own dashboard build | [How the dashboard gets its images](docs/dashboard-images.md) |
| see what a release pins | [Release notes](docs/releases/v1.0.0.md) |
| know why there is one image catalog | [ADR 0002](docs/adr/0002-one-image-catalog.md) |
| know what each script under `tools/` is for | [tools/README.md](tools/README.md) |

Updating an existing checkout is covered in the
[User Guide](docs/USER_GUIDE.md#updating-an-existing-checkout).
