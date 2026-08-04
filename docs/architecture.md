# System architecture

## Overview

```
                     ┌─────────────────────┐
                     │ privacy_policy.yaml │
                     │ purpose, dimensions,│
                     │ processing, sharing,│
                     │ retention, fallback │
                     └──────────┬──────────┘
                                │
                         Policy Loader
                                │
                                ▼
Capability Request ──► Privacy Gate ──► Consent Manager
                             │                 │
                             │                 ├──► Consent Prompt
                             │                 │          │
                             │                 │          ▼
                             │                 │     Consent UI
                             │                 │          │
                             │                 ◄── Consent Decision
                             │
                     Granted │ Refused/Revoked
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
             Run capability       Run fallback

                                Consent Events
                                      │
                                      ▼
                               Anonymous Logger
```

## Core invariant

> A privacy-sensitive capability must not operate unless valid consent exists
> for that capability and session.

Every failure mode — malformed policy, unknown capability, missing UI, expired
consent, wrong session — resolves to **deny** (fail closed).

## Components

| Component | Node | Responsibility |
|---|---|---|
| Policy loader | (library) | Parse and validate `privacy_policy.yaml`; reject malformed policies |
| Consent manager | `consent_manager` | Own consent state; create requests, store decisions, expire, revoke, reset; publish anonymous events |
| Privacy gate | `privacy_gate` | Enforce consent before forwarding capability requests; trigger prompts and fallbacks |
| Consent UI | `consent_ui` | Present prompts to the participant; publish decisions |
| Consent logger | `consent_logger` | Append anonymous consent events to a CSV session log |
| Scenario simulator | `scenario_simulator` | Drive the deterministic seven-stage privacy-dimension scenario |
| Gazebo motion adapter | `gazebo_motion_adapter` | Convert validated scenario outcomes into bounded visual motion; never decide consent |
| Gazebo bridge | `parameter_bridge` | Carry ROS `Twist` commands to the Harmonic `DiffDrive` system |

The manager, gate and terminal UI were implemented in Phase 3. Phase 4 adds
the deterministic scenario simulator, purpose-centred policy, and condition
launch files. Phase 5 adds the strict anonymous event logger to both study
conditions. Phase 6 adds a shared Gazebo world and outcome visualisation while
leaving all consent decisions in the existing manager and gate.

The policy loader and consent state machine are plain Python modules with no
`rclpy` dependency; nodes wrap them. This keeps the security-critical logic
unit-testable without a ROS installation.

## Interfaces

### Messages (`dynamic_consent_interfaces/msg`)

| Message | Purpose |
|---|---|
| `ConsentPrompt` | Manager → UI: ask the participant for permission |
| `ConsentDecision` | UI → Manager: the participant's decision |
| `ConsentEvent` | Manager/Gate → Logger: anonymous audit event |

### Services (`dynamic_consent_interfaces/srv`)

| Service | Purpose |
|---|---|
| `CheckConsent` | Gate → Manager: is consent valid for (session, capability)? |
| `RevokeConsent` | UI/CLI → Manager: withdraw a previously granted permission |
| `ResetSession` | Experimenter → Manager: clear all consent at end of session |

### Topics

| Topic | Type | Flow |
|---|---|---|
| `/consent/prompt` | `ConsentPrompt` | manager → UI |
| `/consent/decision` | `ConsentDecision` | UI → manager |
| `/consent/event` | `ConsentEvent` | manager, gate → logger |
| `/consent/session` | `std_msgs/String` | manager → gate (transient local) |
| `/consent/request` | `std_msgs/String` (capability id) | gate → manager |
| `/capability/requested` | `std_msgs/String` (capability id) | simulator → gate |
| `/capability/authorized` | `std_msgs/String` | gate → simulator |
| `/capability/blocked` | `std_msgs/String` | gate → simulator |
| `/scenario/status` | `std_msgs/String` | simulator → observer |
| `/gazebo_demo/status` | `std_msgs/String` | motion adapter → observer |
| `/model/consent_robot/cmd_vel` | `geometry_msgs/Twist` | motion adapter → Gazebo bridge |

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `consent_mode` | `dynamic` | `static` or `dynamic` prompting |
| `policy_file` | `privacy_policy.yaml` | Policy to load |
| `log_directory` | `~/.ros/dynamic_consent/logs` | Private per-session CSV directory |
| `session_timeout_seconds` | `900` | Stop accepting events after this session duration |
| `enable_raw_sensor_storage` | `false` | Must be false or the logger disables itself |
| `static_disclosure` | frozen combined notice | Opening static notice |
| `startup_delay_seconds` | `2.0` | Delay before scenario stage 1 |
| `stage_delay_seconds` | `1.0` | Delay between scenario stages |
| `cmd_vel_topic` | `/model/consent_robot/cmd_vel` | Gazebo robot velocity topic |
| `forward_speed` | `0.5` | Allowed-outcome linear speed in m/s |
| `forward_duration_seconds` | `0.8` | Allowed-outcome motion duration |
| `turn_speed` | `0.8` | Fallback acknowledgement angular speed in rad/s |
| `turn_duration_seconds` | `0.3` | Duration of each acknowledgement turn |

## Purpose-centred policy contract

A capability is not authorised merely by naming a sensor. Each policy entry
declares the complete processing context shown to the participant:

| Field | Meaning |
|---|---|
| `privacy_dimensions` | One or more of informational, physical, psychological, social |
| `data_inputs` | Raw or derived data needed by the capability |
| `purpose` | The concrete assistance the capability provides |
| `processing` | What the robot does with the inputs, including inference or disclosure |
| `processing_location` | `on_robot`, `local_network`, or `external_service` |
| `recipients` | Systems or people that can receive the data |
| `retention` | `not_stored`, `interaction_only`, `session_only`, or `declared_period` |
| `retention_seconds` | Positive duration required for `declared_period`; zero otherwise |
| `refusal_fallback` | Functionally useful action selected when consent is absent |

The policy loader rejects missing fields, unknown dimensions or processing
locations, invalid retention combinations, duplicate list values, and malformed
types. An invalid policy leaves both manager and gate in the fail-closed state.

`ConsentPrompt` carries the same context to the terminal UI. The first view
shows purpose, privacy dimensions, recipients, and retention. “View more
information” adds inputs, processing operation, and processing location.

## Phase 3 gate sequence

1. A simulated capability id arrives on `/capability/requested`.
2. The gate rejects an empty or policy-unknown id immediately.
3. The gate calls `/consent/check` using the manager-owned anonymous session.
4. `GRANTED` is forwarded on `/capability/authorized`.
5. `UNKNOWN` or `EXPIRED` publishes `/consent/request` and waits.
6. `PENDING` remains blocked while the UI waits for explicit input.
7. `REFUSED` or `REVOKED` publishes `/capability/blocked` and selects the
   policy fallback.

The gate queues requests until the manager session and check service are
available, but never authorizes while either is unavailable.

## Phase 4 condition boundary

Both launch files construct the same four nodes and use the same seven
scenario stages. The condition configuration changes only consent timing:

- `static`: one combined decision is atomically applied to all capabilities
  at session start and remains valid for that session.
- `dynamic`: each capability is requested when its scenario stage begins and
  retains the expiry configured in `privacy_policy.yaml`.

The condition files use identical startup and inter-stage delays. Scenario
outcomes are published as `capability_executed` or `fallback_executed` events,
which the Phase 5 logger validates before writing.

## Phase 5 anonymous logging boundary

The logger subscribes to the manager-owned transient session id and accepts
events only for that active anonymous session and configured condition. Its
ROS-free core enforces the frozen eight-column schema and event-specific
relationships—for example, only `consent_decided` may contain response time,
and only execution events may contain task outcomes.

The logger provides the following safeguards:

- session ids must match `session_[0-9a-f]{8}` and cannot select a path;
- capability ids are restricted tokens, never participant-entered text;
- conditions, event types, decisions, and outcomes use closed allow-lists;
- timestamps are normalised to ISO 8601 UTC;
- one CSV is created per session with directory mode `0700` and file mode
  `0600`;
- every row is flushed and synchronised to disk;
- existing files with another header and symbolic-link targets are rejected;
- malformed or cross-session events are never written;
- enabling raw sensor storage disables the node rather than weakening the
  study protocol.

The logger owns the `session_started` row. This avoids losing it if the
manager's event is published before the logger subscription is ready; a later
duplicate manager event is ignored.

## Phase 6 Gazebo boundary

The Phase 6 adapter subscribes only to `/scenario/status`; it cannot call the
consent service or manufacture an authorised outcome. Its ROS-free parser
accepts exact statuses for the frozen seven stages. An authorised capability
moves the robot forward for a bounded time, while a fallback turns left and
right with zero linear velocity. Ready, requested, and complete states stop.

Both Gazebo condition launches reuse the same world, adapter parameters, ROS–
Gazebo bridge, and scenario constructor. The world contains a red private-space
boundary positioned so Stage 6 crosses it only after an authorised outcome.
When the preceding five stages were granted, refusal executes the existing
policy fallback and keeps the robot immediately outside.

The world is self-contained and uses Gazebo Harmonic's `DiffDrive` system.
GUI launches default to the Ogre 1 render engine for the UTM graphics context;
server-only mode is available without changing the consent experiment.
