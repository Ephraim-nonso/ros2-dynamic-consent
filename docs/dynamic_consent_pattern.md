# Dynamic consent pattern

## Consent state machine

```
UNKNOWN → PENDING → GRANTED
                  └→ REFUSED

GRANTED → REVOKED
GRANTED → EXPIRED
```

| State | Meaning | Gate behaviour |
|---|---|---|
| `UNKNOWN` | Never asked in this session | DENY, trigger prompt |
| `PENDING` | Prompt shown, no decision yet | DENY, wait |
| `GRANTED` | Valid consent exists | **ALLOW** |
| `REFUSED` | Participant declined | DENY, run fallback |
| `REVOKED` | Participant withdrew consent | DENY, run fallback |
| `EXPIRED` | Time-limited consent lapsed | DENY, re-prompt |

`GRANTED` is the **only** state that allows a capability. Closing or crashing
the UI never grants; an undecided prompt stays `PENDING` and is denied.

Allowed transitions are enforced by the consent manager:

- `UNKNOWN → PENDING` (prompt created)
- `PENDING → GRANTED | REFUSED` (participant decision)
- `GRANTED → REVOKED` (participant withdrawal)
- `GRANTED → EXPIRED` (expiry timer lapsed)
- `EXPIRED | REFUSED | REVOKED → PENDING` (re-prompt, dynamic mode only)
- any state `→ UNKNOWN` (session reset)

## Frozen capabilities (Phase 0)

| Capability id | Sensor | Purpose | Refusal fallback |
|---|---|---|---|
| `speech_input` | microphone | Understand the user's destination | Text destination menu |
| `gesture_recognition` | camera | Detect where the user is pointing | On-screen direction buttons |
| `route_guidance` | location | Guide the user through the building | Display written directions |

## Static disclosure wording (frozen)

> This robot may use its microphone, camera and location information to
> provide assistance during this session. Audio, images and location data are
> processed only for the current interaction and are not stored. You may
> accept or refuse this once at the start; refusing means the robot will use
> on-screen alternatives instead.

## Dynamic prompts (frozen)

**speech_input**
> To understand your destination, may I use the microphone? Audio will be
> processed for this interaction and will not be stored.

**gesture_recognition**
> To see where you are pointing, may I temporarily use the camera? Images
> will be processed for this interaction and will not be stored.

**route_guidance**
> To guide you there, may I use your current location inside the building?
> Your location history will not be stored.

## Refusal behaviour

Refusal is never a dead end. Each capability has a functionally equivalent
fallback so the task always completes:

| Capability | Fallback id | Behaviour |
|---|---|---|
| `speech_input` | `show_destination_menu` | List of destinations to choose from |
| `gesture_recognition` | `show_direction_buttons` | Left/right/ahead buttons |
| `route_guidance` | `show_written_route` | Static written directions |

## Revocation

At any time the participant can revoke a granted permission. Revocation takes
effect immediately: the next capability request is denied and the fallback is
used. Revocation is visible in the UI and logged as a `consent_revoked` event.
