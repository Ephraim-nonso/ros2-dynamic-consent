# Dynamic Consent for ROS 2 Human-Robot Interaction

A ROS 2 (Jazzy) package implementing **dynamic consent** for privacy-sensitive
robot capabilities. Instead of a single up-front disclosure, the robot requests
permission at the moment each capability (microphone, camera, location) becomes
necessary, and the user can refuse or revoke at any time.

The core invariant:

> A privacy-sensitive capability must not operate unless valid consent exists
> for that capability and session.

## Packages

| Package | Build type | Contents |
|---|---|---|
| `dynamic_consent_interfaces` | `ament_cmake` | Custom messages and services |
| `dynamic_consent_hri` | `ament_python` | Consent manager, privacy gate, UI, logger, simulator |

## Repository layout

```
dynamic_consent_interfaces/   # msg/ and srv/ definitions
dynamic_consent_hri/
├── dynamic_consent_hri/      # Python modules and ROS nodes
├── config/                   # privacy_policy.yaml + condition configs
├── launch/                   # static_demo / dynamic_demo launch files
├── logs/                     # anonymous CSV session logs (gitignored)
└── test/                     # pytest unit tests
docs/                         # architecture and research design
```

## Design principles

- **Fail closed** — any state other than `GRANTED` (including malformed
  policies, unknown capabilities, or a crashed UI) denies the capability.
- **ROS-free core** — consent state, policy validation, and log sanitisation
  are plain Python with no `rclpy` dependency, so the security-critical logic
  is unit-testable without a ROS installation. ROS nodes are thin wrappers.
- **Anonymous by construction** — the system never stores names, demographics,
  raw audio/images, or transcriptions. Sessions are identified only by a
  randomly generated code.

## Building (Ubuntu 24.04 / ROS 2 Jazzy)

```bash
source /opt/ros/jazzy/setup.bash
mkdir -p ~/dynamic_consent_ws/src
cd ~/dynamic_consent_ws/src
git clone <this-repo> dynamic_consent_ros2
cd ~/dynamic_consent_ws
colcon build --symlink-install
source install/setup.bash
```

Verify the interfaces:

```bash
ros2 interface show dynamic_consent_interfaces/msg/ConsentPrompt
ros2 interface show dynamic_consent_interfaces/srv/CheckConsent
```

## Running the demos

```bash
ros2 launch dynamic_consent_hri static_demo.launch.py
ros2 launch dynamic_consent_hri dynamic_demo.launch.py
```

## Running unit tests (no ROS required)

The pure-Python core tests run on any machine with Python ≥ 3.10:

```bash
cd dynamic_consent_hri
python3 -m pytest test/ -v
```

## Documentation

- [docs/architecture.md](docs/architecture.md) — components, topics, services
- [docs/dynamic_consent_pattern.md](docs/dynamic_consent_pattern.md) — consent
  state machine, prompts, fallbacks
- [docs/evaluation_scenario.md](docs/evaluation_scenario.md) — static vs
  dynamic study conditions and logging schema
