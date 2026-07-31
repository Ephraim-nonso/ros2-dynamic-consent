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
| `dynamic_consent_hri` | `ament_python` | Consent manager, privacy gate and terminal UI |

## Repository layout

```
dynamic_consent_interfaces/   # msg/ and srv/ definitions
dynamic_consent_hri/
├── dynamic_consent_hri/      # Python modules and ROS nodes
├── config/                   # privacy_policy.yaml
├── logs/                     # anonymous CSV session logs (gitignored)
└── test/                     # pytest unit tests
docs/                         # architecture and research design
```

## Design principles

- **Fail closed** — any state other than `GRANTED` (including malformed
  policies, unknown capabilities, or a crashed UI) denies the capability.
- **ROS-free core** — consent state, policy validation, gate decisions and UI
  formatting are plain Python with no `rclpy` dependency, so the
  security-critical logic is unit-testable without a ROS installation. ROS
  nodes are thin wrappers.
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

## Phase 3 interactive demonstration

Phase 3 provides the consent manager, fail-closed privacy gate and terminal
UI. The manager publishes the anonymous active session, so the nodes agree on
the session without a participant identifier or repeated command-line value.

After building, source ROS and the workspace in every terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ~/dynamic_consent_ws/install/setup.bash
```

Start these nodes in separate terminals:

```bash
ros2 run dynamic_consent_hri consent_manager
ros2 run dynamic_consent_hri privacy_gate
ros2 run dynamic_consent_hri consent_ui
```

Before requesting a capability, observe the two possible outcomes in two more
terminals:

```bash
ros2 topic echo /capability/authorized
ros2 topic echo /capability/blocked
```

Request simulated microphone access:

```bash
ros2 topic pub --once /capability/requested std_msgs/msg/String \
  "{data: speech_input}"
```

The UI asks for an explicit decision. Allow publishes `speech_input` on
`/capability/authorized`; refusal publishes it on `/capability/blocked` and
the gate reports the configured `show_destination_menu` fallback. No input,
EOF, or closing the UI leaves the request pending and never authorizes it.

To test revocation, copy the session id printed by the manager and call:

```bash
ros2 service call /consent/revoke \
  dynamic_consent_interfaces/srv/RevokeConsent \
  "{session_id: 'session_XXXXXXXX', capability_id: 'speech_input'}"
```

The next `speech_input` request is blocked. Expired grants are also denied and
cause a new prompt. Static/dynamic condition launch files, the deterministic
scenario and anonymous logger are later phases and are not advertised as
runnable yet.

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
