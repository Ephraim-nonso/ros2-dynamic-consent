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
| `INVALID_CAPABILITY` | Not defined by policy | DENY, no prompt |

`GRANTED` is the **only** state that allows a capability. Closing or crashing
the UI never grants; an undecided prompt stays `PENDING` and is denied.

Allowed transitions are enforced by the consent manager:

- `UNKNOWN → PENDING` (prompt created)
- `PENDING → GRANTED | REFUSED` (participant decision)
- `GRANTED → REVOKED` (participant withdrawal)
- `GRANTED → EXPIRED` (expiry timer lapsed)
- `EXPIRED | REFUSED | REVOKED → PENDING` (re-prompt, dynamic mode only)
- any state `→ UNKNOWN` (session reset)

## Privacy-dimension capabilities

The policy unit is a purpose-specific capability, not a hardware permission.
For example, `person_recognition` and `body_pose_tracking` may both use camera
data but receive separate decisions because their processing and privacy
effects differ.

| Capability id | Dimensions | Purpose | Retention / recipient |
|---|---|---|---|
| `person_recognition` | informational, social | Recognise a returning user | Identity template on robot for 30 days |
| `speech_input` | informational | Understand a destination | Not stored; robot assistance system only |
| `interaction_memory` | informational, psychological | Remember destinations and preferences | Profile on robot for 30 days |
| `body_pose_tracking` | informational, physical | Detect pointing, mobility difficulty, or a possible fall | Not stored; on-robot processing |
| `route_guidance` | informational, physical | Provide indoor navigation | Current interaction only |
| `proximity_or_private_space_access` | physical, social | Follow a user or cross a private boundary | Current interaction only |
| `remote_assistance_stream` | informational, social | Connect remote assistance | Unrecorded live stream to authorised building assistance staff |

The static condition presents one combined disclosure containing all seven
purposes. The dynamic condition presents the policy entry at the moment its
scenario stage begins. In particular, remote assistance explicitly identifies
the human recipient instead of describing the operation as generic camera
access.

## Refusal behaviour

Refusal is never a dead end. Each capability has a functionally equivalent
fallback so the task always completes:

| Capability | Fallback id | Behaviour |
|---|---|---|
| `person_recognition` | `start_anonymous_temporary_session` | Continue without recognising or enrolling the participant |
| `speech_input` | `show_destination_menu` | List of destinations to choose from |
| `interaction_memory` | `use_session_only_memory` | Forget preferences when the session ends |
| `body_pose_tracking` | `show_direction_and_assistance_controls` | Explicit direction and help controls |
| `route_guidance` | `show_written_route` | Static written directions |
| `proximity_or_private_space_access` | `wait_at_boundary_and_show_instructions` | Remain outside and provide instructions |
| `remote_assistance_stream` | `show_local_help_or_request_in_person_staff` | Keep data local or request an in-person staff member |

## Revocation

At any time the participant can revoke a granted permission. Revocation takes
effect immediately: the next capability request is denied and the fallback is
used. Revocation is visible in the UI and logged as a `consent_revoked` event.

## Terminal decision semantics

The Phase 3 UI publishes only explicit allow or refuse decisions. Viewing
more information returns to the same choice, while invalid input asks again.
EOF, terminal closure and UI failure publish nothing. The manager therefore
keeps the request `PENDING`, and the gate cannot forward the capability.

## Condition semantics

In the dynamic condition, `UNKNOWN` and `EXPIRED` consent trigger a
capability-specific prompt. Refused or revoked consent runs the configured
fallback.

In the static condition, the manager creates pending records for every policy
capability and presents one combined prompt at session start. The single
decision is validated for every record before any record is changed, avoiding
a partially granted session. A static grant lasts for the session; refusal or
later revocation causes the relevant fallback and never triggers a dynamic
prompt.
