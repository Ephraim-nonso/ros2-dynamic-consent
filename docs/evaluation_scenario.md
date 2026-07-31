# Evaluation scenario

## Design

Between-participants comparison of two consent designs. Robot behaviour, task
sequence and capabilities are **identical** in both conditions; only the
consent design differs.

| | Static condition | Dynamic condition |
|---|---|---|
| Disclosure timing | Once, at session start | At the moment each capability is needed |
| Prompt content | One combined disclosure | Per-capability purpose + retention |
| Revocation | Available on request | Available on request, surfaced in UI |
| Parameter | `consent_mode: static` | `consent_mode: dynamic` |

The Phase 4 implementation enforces this comparison through separate
condition files and a shared launch constructor. Both conditions start the
same manager, gate, terminal UI and scenario simulator. Only the manager and
gate consent timing changes.

## Three-stage task scenario (deterministic)

Every session runs the same sequence:

1. **Stage 1 — Destination**: the robot needs the participant's destination.
   Capability: `speech_input` (microphone). Fallback: destination menu.
2. **Stage 2 — Direction**: the robot asks the participant to point where
   they want to go first. Capability: `gesture_recognition` (camera).
   Fallback: direction buttons.
3. **Stage 3 — Guidance**: the robot guides the participant to the
   destination. Capability: `route_guidance` (location). Fallback: written
   directions.

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

## Anonymous logging schema (frozen)

One CSV file per session, named by the random session id.

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
