# Phase 6: interactive Gazebo demonstration

## Outcome

Phase 6 places the existing seven-stage consent study in a small Gazebo
building. It does not grant permissions or simulate private data. The existing
privacy gate remains authoritative; a separate adapter converts only validated
scenario outcomes into short, bounded robot motions.

| Scenario status | Gazebo behaviour |
|---|---|
| Ready, requested, complete | Stop |
| `capability_executed` | Move forward 0.4 m |
| `fallback_executed` | Turn left and right in place, then stop |
| Malformed or unknown status | Ignore it; do not move |

The red line in the world represents a private-space boundary. After five
granted stages, the robot is positioned immediately before it. Granting Stage
6 moves the robot across it. Refusing Stage 6 selects the useful fallback and
keeps all commanded linear velocity at zero, so the robot waits outside.

This is a visible study demonstration, not autonomous navigation or a claim
that Gazebo models actual collection of faces, speech, body pose, or streams.

## Ubuntu 24.04 / ROS 2 Jazzy setup

Gazebo Harmonic is the supported Gazebo release for ROS 2 Jazzy. Install its
ROS integration if it is not already present:

```bash
sudo apt update
sudo apt install ros-jazzy-ros-gz
```

From the workspace that contains the repository under `src`:

```bash
cd ~/dynamic_consent_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Launch the dynamic condition:

```bash
ros2 launch dynamic_consent_hri gazebo_dynamic_demo.launch.py
```

Or launch the static condition:

```bash
ros2 launch dynamic_consent_hri gazebo_static_demo.launch.py
```

Run one condition at a time and answer the terminal prompts. Gazebo starts
paused only during loading and then runs automatically. The coloured pads near
the north wall correspond, from west to east, to the seven scenario stages.

## UTM graphics options

The launch defaults to Ogre 1 (`render_engine:=ogre`) because the tested UTM
guest exposes an accelerated virgl renderer but only an OpenGL 2.1 desktop
context. To request Ogre 2 on a machine that supports it:

```bash
ros2 launch dynamic_consent_hri gazebo_dynamic_demo.launch.py \
  render_engine:=ogre2
```

If the Gazebo graphical client fails, first verify the complete ROS flow with
the server-only mode:

```bash
ros2 launch dynamic_consent_hri gazebo_dynamic_demo.launch.py headless:=true
```

`headless:=true` suppresses only the Gazebo GUI. The terminal consent UI still
runs, the robot still receives physics commands, and anonymous events are
still logged. Observe the integration from another sourced terminal:

```bash
ros2 topic echo /scenario/status
ros2 topic echo /gazebo_demo/status
```

## Safety and study constraints

- The adapter accepts only exact status strings derived from the frozen
  seven-stage scenario.
- Motion settings must be positive numeric values; an invalid runtime setting
  disables motion.
- Requests, pending decisions, completion, and shutdown publish a stop.
- A refusal never produces forward velocity, including at the private-space
  boundary.
- The world uses only repository assets, so it does not require Gazebo Fuel or
  another model download at launch.
- The two condition launches share the same world, motion configuration, and
  stages. Only consent timing differs.

The motion mapping has ROS-free unit tests. Full physics, bridge, GUI, and
terminal interaction must be validated on the Ubuntu VM because the macOS
development host does not contain ROS 2 Jazzy or Gazebo Harmonic.

Phase 7 extends this foundation with a visible visitor-assistance environment,
stage-specific actions, a participant-facing dashboard, and coordinated reset.
See `docs/phase7_embodied_interaction.md`.
