# System architecture

## Overview

```
                     ┌─────────────────────┐
                     │ privacy_policy.yaml │
                     │ sensors, purposes,  │
                     │ prompts, retention  │
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
| Scenario simulator | `scenario_simulator` | Drive the deterministic three-stage task scenario |

The manager, gate and terminal UI are implemented in Phase 3. The logger and
scenario simulator remain planned components.

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

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `consent_mode` | `dynamic` | `static` or `dynamic` prompting |
| `policy_file` | `privacy_policy.yaml` | Policy to load |
| `log_directory` | `logs` | Where anonymous CSV logs are written |
| `session_timeout_seconds` | `900` | Hard limit on a participant session |
| `enable_raw_sensor_storage` | `false` | Must remain false in the study |

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
