# Phase 7: study-ready embodied interaction

## Purpose

Phase 7 turns the Gazebo motion proof into an understandable indoor-assistance
task. The robot begins at reception beside a stylised visitor, progresses
toward a destination, encounters a red private-room boundary, and can signal a
connection to the named staff station.

The world remains a privacy-safe simulation. It does not capture a real face,
microphone stream, body pose, location history, or staff video. The consent
manager and privacy gate still make every authorization decision; Gazebo only
visualises the validated outcome.

## Visible task environment

The self-contained world now provides:

- a blue visitor figure pointing toward the assistance route;
- a reception desk and blue start beacon;
- seven coloured stage pads;
- a red private-room floor, boundary line, partitions, and doorway;
- a green destination arch;
- a purple authorised-staff assistance station;
- a fixed blue/yellow/green/orange status-colour key; and
- an elevated observer camera configured for the UTM-compatible Ogre engine.

Gazebo's Entity Tree uses descriptive model names so an experimenter can
identify each study object without downloading external models.

## Embodied actions

Every allowed stage still advances the same nominal 0.4 m, preserving the
Phase 6 spatial comparison. A short stage-specific gesture makes the simulated
capability easier to interpret.

| Stage | Granted behaviour | Refusal behaviour |
|---|---|---|
| Returning-user recognition | Scan, return to heading, approach | Stationary fallback acknowledgement |
| Spoken destination | Listening pause, approach | Stationary fallback acknowledgement |
| Interaction memory | Short confirmation gesture, approach | Stationary fallback acknowledgement |
| Body-pose assistance | Orient, return to heading, approach | Stationary fallback acknowledgement |
| Route guidance | Lead forward | Stationary fallback acknowledgement |
| Private-space boundary | Cross the red line when positioned outside | Wait outside with zero linear velocity |
| Remote staff assistance | Advance, then signal the staff connection | Stationary fallback acknowledgement |

All gestures are bounded and return to the original heading. A request or
malformed status stops the robot. No fallback plan contains forward velocity.

## Participant-facing dashboard

The `study_dashboard` node converts only exact frozen scenario statuses into
fixed, privacy-safe text. It explains the current stage and shows one of five
states:

- blue: session ready;
- yellow: waiting for explicit consent;
- green: permission granted and capability action running;
- orange: refusal fallback running; or
- purple: study task complete.

The dashboard is printed in the launch terminal and published with transient
local durability:

```bash
ros2 topic echo /study/status \
  --qos-durability transient_local \
  --qos-reliability reliable
```

The display text is closed study copy. It never includes participant-entered
text or sensor content.

## Repeatable experiment reset

Phase 7 adds `/study/reset`, an experimenter-facing `std_srvs/srv/Trigger`
service. It performs the reset in a safe order:

1. Gazebo resets simulation time and every model to the original world state.
2. The active consent session is ended and its records are cleared.
3. The manager creates a fresh anonymous session id.
4. The logger opens a new restricted CSV file.
5. The gate discards pending work and adopts the new session.
6. The scenario returns to reception and starts again.
7. Static mode presents a fresh combined notice; dynamic mode prompts at each
   stage as before.

Call it from a second sourced terminal:

```bash
ros2 service call /study/reset std_srvs/srv/Trigger "{}"
```

The service acknowledges that the asynchronous reset was accepted. Confirm
completion with:

```bash
ros2 topic echo /study/control_status
```

Do not begin the next participant trial until `reset_complete` appears.

## Launching

Build and source the workspace, then run one condition:

```bash
ros2 launch dynamic_consent_hri gazebo_dynamic_demo.launch.py
ros2 launch dynamic_consent_hri gazebo_static_demo.launch.py
```

The same `headless:=true` and `render_engine:=ogre2` overrides from Phase 6
remain available. Both consent conditions use the same environment, robot,
stage order, status copy, motion parameters, and reset procedure.
