# Dynamic Consent for ROS 2 Human–Robot Interaction

[![ROS 2 Jazzy CI](https://github.com/Ephraim-nonso/ros2-dynamic-consent/actions/workflows/ros2_jazzy_ci.yml/badge.svg)](https://github.com/Ephraim-nonso/ros2-dynamic-consent/actions/workflows/ros2_jazzy_ci.yml)

A ROS 2 Jazzy research package for managing consent around privacy-sensitive
robot capabilities. Instead of relying only on a broad notice at the beginning
of an interaction, the robot can request permission when each capability is
needed. A participant can accept, refuse, or later revoke permission, and every
refusal has a useful privacy-preserving fallback.

The package includes static and dynamic consent conditions, anonymous study
logging, and an interactive Gazebo Harmonic visitor-assistance demonstration.

> A privacy-sensitive capability must not operate unless valid consent exists
> for that capability and anonymous session.

## Current implementation

| Phase | Status | Delivered capability |
|---|---|---|
| 1 | Complete | Custom consent messages and services |
| 2 | Complete | Strict policy loader, consent state machine, and ROS manager |
| 3 | Complete | Fail-closed privacy gate and terminal consent UI |
| 4 | Complete | Static/dynamic study conditions and purpose-centred policies |
| 5 | Complete | Anonymous, schema-controlled CSV event logging |
| 6 | Complete | Interactive Gazebo world and consent-controlled motion |
| 7 | Complete | Embodied assistance actions, dashboard, and coordinated reset |
| 8 | Complete | Live ROS integration, failure-mode, and headless Gazebo tests |
| 9 | In development | Consent-guarded real microphone and Gazebo logical camera |

## Seven privacy policies

The demonstration uses capability policies rather than treating a sensor name
as sufficient consent context.

| Capability | Purpose | Privacy dimensions | Refusal fallback |
|---|---|---|---|
| `person_recognition` | Recognise a returning user | Informational, social | Anonymous temporary session |
| `speech_input` | Understand the requested destination | Informational | On-screen destination menu |
| `interaction_memory` | Remember destinations and assistance preferences | Informational, psychological | Session-only memory |
| `body_pose_tracking` | Detect pointing, mobility difficulty, or a possible fall | Informational, physical | Direction and assistance controls |
| `route_guidance` | Provide indoor navigation | Informational, physical | Written directions |
| `proximity_or_private_space_access` | Follow the user or cross a declared private boundary | Physical, social | Wait at the boundary and show instructions |
| `remote_assistance_stream` | Connect an authorised staff member | Informational, social | Local help or in-person staff |

Each policy also declares its data inputs, processing operation and location,
recipients, retention, consent expiry, and fallback. See
[`privacy_policy.yaml`](dynamic_consent_hri/config/privacy_policy.yaml) for the
authoritative definitions.

## How it works

```text
Capability request
        │
        ▼
  Privacy gate ─────► Consent manager ─────► Consent prompt/UI
        │                    ▲                       │
        │                    └──── explicit decision┘
        │
        ├── valid grant ────► authorised capability action
        └── otherwise ──────► blocked outcome and configured fallback
                                  │
                                  ▼
                         anonymous event logger
```

The consent manager owns the anonymous session and consent state. The privacy
gate is the only path from a capability request to authorisation. Unknown
capabilities, malformed policies, missing services, pending prompts, expired
grants, stale sessions, and unavailable UI all fail closed.

The Gazebo adapter reacts only to validated scenario outcomes. It cannot grant
consent itself. Granted stages produce short, bounded, stage-specific robot
actions; refused stages keep the robot useful without performing the rejected
privacy-sensitive action.

Phase 9 adds an explicit sensor boundary. A Gazebo logical camera provides
GPU-independent simulated person-presence observations, while a real ALSA
microphone is opened only after `speech_input` authorization. Authorized audio
is transcribed locally and can be displayed and spoken by the assistant. Raw
audio, transcripts, model names, and poses are never written to the anonymous
study log.

## Packages

| Package | Build type | Contents |
|---|---|---|
| `dynamic_consent_interfaces` | `ament_cmake` | Consent messages and services |
| `dynamic_consent_hri` | `ament_python` | Manager, gate, UI, logger, scenario, dashboard, controller, and Gazebo adapter |

## Repository layout

```text
dynamic_consent_interfaces/       Custom msg and srv definitions
dynamic_consent_hri/
├── config/                       Privacy and Gazebo configuration
├── dynamic_consent_hri/          Python core and ROS nodes
├── launch/                       Static and dynamic Gazebo launch files
├── test/                         Unit and live integration tests
└── worlds/                       Self-contained Gazebo study world
docs/                             Architecture, protocol, and phase guides
```

## Requirements

- Ubuntu 24.04
- ROS 2 Jazzy
- Gazebo Harmonic through `ros_gz`
- Python 3.10 or newer

Install the Gazebo integration if needed:

```bash
sudo apt update
sudo apt install ros-jazzy-ros-gz
```

For the guarded real-microphone demonstration, install the offline recognizer
and local speech engine:

```bash
sudo apt install -y python3-pocketsphinx pocketsphinx-en-us espeak-ng
```

## Build

```bash
source /opt/ros/jazzy/setup.bash
mkdir -p ~/dynamic_consent_ws/src
cd ~/dynamic_consent_ws/src
git clone https://github.com/Ephraim-nonso/ros2-dynamic-consent.git

cd ~/dynamic_consent_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Source ROS and the workspace in every new terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ~/dynamic_consent_ws/install/setup.bash
```

## Run the Gazebo study demonstration

Run one condition at a time.

Dynamic consent asks at the moment each of the seven capabilities is needed:

```bash
ros2 launch dynamic_consent_hri gazebo_dynamic_demo.launch.py
```

Static consent presents one combined notice and applies one decision to all
seven capabilities for that session:

```bash
ros2 launch dynamic_consent_hri gazebo_static_demo.launch.py
```

Use the terminal UI to select:

```text
[1] Allow
[2] Refuse
[3] View more information
```

The participant-facing dashboard reports the current stage, decision outcome,
fallback, embodied action, and session completion. The same world, robot,
stage order, and motion parameters are used in both conditions; only consent
timing changes.

### UTM and limited OpenGL support

The launch defaults to the Ogre 1 renderer because UTM guests using virgl on
Apple Silicon may expose only an OpenGL 2.1 desktop context. On a machine with
stronger graphics support, request Ogre 2 with:

```bash
ros2 launch dynamic_consent_hri gazebo_dynamic_demo.launch.py \
  render_engine:=ogre2
```

To run without the Gazebo graphical client:

```bash
ros2 launch dynamic_consent_hri gazebo_dynamic_demo.launch.py \
  headless:=true
```

Headless mode still runs physics, consent handling, robot motion, dashboard
updates, and anonymous logging.

## Run the guarded-sensor demonstration

The UTM-compatible sensor demonstration combines a real Linux microphone with
a non-rendering Gazebo logical camera:

```bash
ros2 launch dynamic_consent_hri gazebo_sensor_dynamic_demo.launch.py
```

For the static-consent comparison:

```bash
ros2 launch dynamic_consent_hri gazebo_sensor_static_demo.launch.py
```

After allowing `speech_input`, speak during the eight-second capture window.
PocketSphinx processes the audio locally, `/assistant/transcript` displays the
result, and `espeak-ng` reads it aloud. Refusal leaves the microphone closed;
revocation or session reset closes an active capture and discards its buffered
result.

The logical camera publishes a privacy-filtered boolean presence result. It is
not an RGB camera, face recognizer, biometric system, or lip-reading model. Its
purpose is to demonstrate the same consent-enforcement boundary without using
Ogre 2 in the OpenGL-limited VM.

## Reset between trials

From another sourced terminal:

```bash
ros2 service call /study/reset std_srvs/srv/Trigger "{}"
```

Wait for `reset_complete` before beginning the next trial:

```bash
ros2 topic echo /study/control_status \
  --qos-durability transient_local \
  --qos-reliability reliable
```

A successful reset restores the Gazebo world, clears the old consent state,
creates a fresh anonymous session, opens a new log, and restarts the selected
condition.

## Observe the demonstration

Useful topics include:

```bash
ros2 topic echo /scenario/status
ros2 topic echo /gazebo_demo/status
ros2 topic echo /study/status \
  --qos-durability transient_local \
  --qos-reliability reliable
ros2 topic echo /capability/authorized
ros2 topic echo /capability/blocked
ros2 topic echo /sensors/logical_camera/status
ros2 topic echo /perception/person_present
ros2 topic echo /sensors/microphone/status
ros2 topic echo /perception/speech/status
ros2 topic echo /assistant/transcript
```

Previously granted consent can be withdrawn with:

```bash
ros2 service call /consent/revoke \
  dynamic_consent_interfaces/srv/RevokeConsent \
  "{session_id: 'session_XXXXXXXX', capability_id: 'speech_input'}"
```

## Anonymous study logging

The logger creates one private CSV file per anonymous session under
`~/.ros/dynamic_consent/logs` by default. It records only closed-schema study
events such as requests, decisions, execution outcomes, and response times.
It rejects participant-entered text, raw sensor content, unsafe identifiers,
cross-session events, symbolic-link targets, and malformed records.

The logger disables itself if raw sensor storage is enabled. This project does
not store names, demographics, audio, images, transcripts, or biometric data.

## Testing

Run the complete ROS 2 package test suite on the Ubuntu VM:

```bash
cd ~/dynamic_consent_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash

colcon test --packages-select dynamic_consent_hri \
  --event-handlers console_direct+
colcon test-result --verbose
```

Run the ROS integration tests without Gazebo:

```bash
python3 -m pytest \
  src/ros2-dynamic-consent/dynamic_consent_hri/test \
  -m "not gazebo" -v
```

Run only the headless Gazebo end-to-end test:

```bash
python3 -m pytest \
  src/ros2-dynamic-consent/dynamic_consent_hri/test/integration/test_gazebo_headless_smoke.py \
  -v
```

The ROS-free core tests also run on systems without ROS. Live ROS and Gazebo
modules skip cleanly when their runtime is unavailable.

Phase 8 verifies dynamic grant/revocation, static session rotation, unanswered
prompts, unknown capabilities, missing consent services, missing policies,
ordered seven-stage execution, odometry, dashboard completion, and coordinated
Gazebo reset.

The `ROS 2 Jazzy CI` GitHub Actions workflow performs the same dependency
resolution, build, and test process in a clean Ubuntu 24.04 environment on
every pull request and push to `main`. Colcon logs are retained for 14 days,
including when a job fails.

## Safety and scope

This is a research demonstration of consent orchestration—not a production
privacy, security, biometric, perception, or autonomous-navigation system.
Gazebo visualises policy-controlled outcomes; it does not collect real faces,
speech, body pose, location history, or remote-assistance streams.

A passing software suite does not replace deployment threat modelling,
research ethics review, participant usability testing, legal review, real
sensor validation, or hardware safety assessment.

## Documentation

- [System architecture](docs/architecture.md)
- [Dynamic consent and policy pattern](docs/dynamic_consent_pattern.md)
- [Evaluation scenario](docs/evaluation_scenario.md)
- [Phase 5 anonymous logging](docs/phase5_anonymous_logging.md)
- [Phase 6 Gazebo demonstration](docs/phase6_gazebo_demo.md)
- [Phase 7 embodied interaction](docs/phase7_embodied_interaction.md)
- [Phase 8 integration testing](docs/phase8_integration_testing.md)
- [Phase 9 guarded sensors](docs/phase9_guarded_sensors.md)

## License

Apache-2.0
