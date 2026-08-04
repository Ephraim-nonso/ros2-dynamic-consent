# Phase 8: automated integration and failure testing

## Objective

Phase 8 verifies that the ROS wrappers preserve the fail-closed guarantees
already tested in the ROS-free core. It adds launch-based tests that start real
ROS 2 processes, exchange the package's messages and services, and exercise the
headless Gazebo Harmonic server.

The integration files use `launch_pytest`, which starts the launch description
for the duration of each test and shuts its processes down afterward. They skip
cleanly on development hosts that do not have a sourced ROS installation.

## Automated suites

### Dynamic consent flow

The test starts a real consent manager and privacy gate and verifies:

1. an unknown capability is blocked;
2. a valid capability is not authorised while its prompt is unanswered;
3. an explicit grant allows that capability;
4. revocation succeeds through `/consent/revoke`; and
5. a later request for the revoked capability is blocked.

### Static consent and reset flow

The static test verifies that one explicit decision is atomically applied to
all seven capabilities. It then rotates the anonymous session, confirms a new
static prompt is required, refuses it, and observes a blocked capability.

### Fail-closed process failures

Two isolated gate tests verify that:

- a missing consent manager / check service never produces authorisation; and
- a missing policy produces an explicit blocked outcome.

### Headless Gazebo end-to-end smoke test

The Gazebo suite starts the complete dynamic study with `headless:=true`. A
test probe grants each frozen prompt and verifies:

- all seven capability-executed statuses arrive in order;
- every stage produces a distinct embodied-action status;
- bridged Gazebo odometry advances by more than 2 m;
- the participant-facing dashboard reaches `SESSION | COMPLETE`;
- `/study/reset` succeeds through the bridged world-control service; and
- a fresh anonymous session is published after `reset_complete`.

The new odometry bridge is observation-only. It does not participate in consent
or control the robot.

## Failure matrix

| Failure or boundary | Expected result | Automated coverage |
|---|---|---|
| Unknown capability | Explicit block | Live dynamic ROS test |
| Missing consent manager | No authorisation | Live gate-only ROS test |
| Missing policy | Explicit block | Live gate-only ROS test |
| Unanswered prompt | No authorisation | Live dynamic ROS test |
| Explicit refusal | Fallback / block | Static reset ROS test and unit tests |
| Revoked consent | Later request blocked | Live dynamic ROS test |
| Wrong or stale session | Rejected | Unit tests and manager reset contract |
| Malformed scenario status | Robot stops | Motion unit tests |
| Raw storage enabled | Logger disables itself | Logger unit tests |
| Cross-session event | Event rejected | Logger unit tests |
| Gazebo world reset unavailable | Consent session is not reset | Controller implementation boundary |
| Successful world reset | New session and restarted scenario | Headless Gazebo smoke test |

## Running on the Ubuntu VM

Stop any manually launched static or dynamic demonstration first. From the
workspace:

```bash
cd ~/dynamic_consent_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

Run the complete package suite, including headless Gazebo:

```bash
colcon test --packages-select dynamic_consent_hri \
  --event-handlers console_direct+
colcon test-result --verbose
```

For a faster ROS-only run that excludes Gazebo:

```bash
python3 -m pytest \
  src/ros2-dynamic-consent/dynamic_consent_hri/test \
  -m "not gazebo" -v
```

Run only the headless Gazebo test with:

```bash
python3 -m pytest src/ros2-dynamic-consent/dynamic_consent_hri/test/integration/test_gazebo_headless_smoke.py \
  -v
```

The Gazebo test must run without another Gazebo server or study launch using
the same default transport partition.

## Interpretation

A passing suite establishes repeatable communication and enforcement across
the package's ROS and Gazebo boundaries. It does not replace usability testing,
research-protocol review, security analysis of a deployed ROS network, or
validation with real sensors and robot hardware.
