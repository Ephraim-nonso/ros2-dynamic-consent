# Evaluation scenario

## Design

Between-participants comparison of two consent designs. Robot behaviour, task
sequence and capabilities are **identical** in both conditions; only the
consent design differs.

| | Static condition | Dynamic condition |
|---|---|---|
| Disclosure timing | Once, at session start | At the moment each capability is needed |
| Prompt content | One combined disclosure | Per-capability purpose, processing, recipient, and retention |
| Revocation | Available on request | Available on request, surfaced in UI |
| Parameter | `consent_mode: static` | `consent_mode: dynamic` |

The Phase 4 implementation enforces this comparison through separate
condition files and a shared launch constructor. Both conditions start the
same manager, gate, terminal UI and scenario simulator. Only the manager and
gate consent timing changes.

## Seven-stage task scenario (deterministic)

Every session runs the same sequence:

1. **Stage 1 — Returning user**: the robot offers to recognise the participant
   for personalised assistance. Capability: `person_recognition`. Fallback:
   anonymous temporary session.
2. **Stage 2 — Destination**: the robot needs the participant's destination.
   Capability: `speech_input` (microphone). Fallback: destination menu.
3. **Stage 3 — Personalisation**: the robot offers to remember destinations
   and preferences for 30 days. Capability: `interaction_memory`. Fallback:
   session-only memory.
4. **Stage 4 — Direction and assistance**: the robot offers to derive body
   pose for pointing, mobility difficulty, or a possible fall. Capability:
   `body_pose_tracking`. Fallback: direction and assistance controls.
5. **Stage 5 — Guidance**: the robot guides the participant to the
   destination. Capability: `route_guidance` (location). Fallback: written
   directions.
6. **Stage 6 — Private-space boundary**: the robot offers to follow the user
   across a declared boundary. Capability: `proximity_or_private_space_access`.
   Fallback: wait outside and provide instructions.
7. **Stage 7 — Remote assistance**: the robot offers an unrecorded live stream
   to authorised building assistance staff. Capability:
   `remote_assistance_stream`. Fallback: local help or in-person staff.

The simulator publishes each capability request in this fixed order and does
not advance until the gate publishes either authorization or blocking. It
then reports the simulated capability or fallback action on
`/scenario/status` before advancing.

## Running Phase 4

```bash
ros2 launch dynamic_consent_hri static_demo.launch.py
ros2 launch dynamic_consent_hri dynamic_demo.launch.py
```

Run only one condition at a time. The terminal UI reads explicit choices from
the controlling terminal. Observe the deterministic flow with:

```bash
ros2 topic echo /scenario/status
```

## Anonymous logging schema (implemented)

One CSV file per session, named by the validated random session id. By default,
files are written to `~/.ros/dynamic_consent/logs`.

```
session_id,condition,event_type,capability,decision,timestamp,response_ms,task_outcome
```

| Field | Content |
|---|---|
| `session_id` | Random code, e.g. `session_04f82c7a` |
| `condition` | `static` or `dynamic` |
| `event_type` | `session_started`, `consent_requested`, `consent_decided`, `consent_revoked`, `consent_expired`, `capability_authorized`, `capability_blocked`, `capability_executed`, `fallback_executed`, `session_reset` |
| `capability` | Capability id, empty for session-level events |
| `decision` | `granted`, `refused`, `revoked`, empty otherwise |
| `timestamp` | ISO 8601 UTC |
| `response_ms` | Prompt-to-decision latency, `consent_decided` only |
| `task_outcome` | `success` / `fallback` / `abandoned`, execution events only |

**Never logged**: raw audio, images, faces, transcriptions, names, email
addresses, exact location histories, free-text answers. Questionnaire
demographics live in a separate dataset joined only via the anonymous
participant code.

The Phase 5 logger enforces this structurally: `ConsentEvent` has no raw-data
field, the CSV writer accepts exactly the eight fields above, and all string
values are closed tokens rather than participant-entered text. A malformed
event, wrong session, wrong condition, invalid existing CSV, logging timeout,
or I/O failure is rejected and cannot be silently converted into an
authorised capability outcome.

Inspect a completed session on Ubuntu with:

```bash
ls -l ~/.ros/dynamic_consent/logs
column -s, -t < ~/.ros/dynamic_consent/logs/session_XXXXXXXX.csv
```

Session logs are research data and remain outside the Git repository. Do not
commit or copy them into `dynamic_consent_hri/logs`.

## Phase 6 Gazebo visualisation

The Gazebo launch variants run this same deterministic scenario in the same
self-contained building world:

```bash
ros2 launch dynamic_consent_hri gazebo_static_demo.launch.py
ros2 launch dynamic_consent_hri gazebo_dynamic_demo.launch.py
```

Only a scenario outcome produced after the gate responds causes visible motion.
An authorised stage advances the robot 0.4 m; a blocked stage performs a
stationary left/right acknowledgement. If Stages 1–5 were granted, the red
private-space line makes Stage 6 concrete: approval crosses the line, while
refusal leaves the robot outside and presents the declared fallback. See
`docs/phase6_gazebo_demo.md` for setup, UTM rendering, headless testing, and
safety constraints.
