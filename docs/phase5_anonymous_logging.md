# Phase 5: anonymous consent-event logging

## Outcome

Phase 5 turns the previously frozen logging schema into an executable,
fail-closed component. Both static and dynamic launches now start
`consent_logger`, but the log schema and security settings are identical
between conditions.

## Data flow

```text
Consent manager ─┐
Privacy gate ─────┼── /consent/event ──► validation ──► session CSV
Simulator ────────┘                            ▲
                                               │
Consent manager ─── /consent/session ──────────┘
```

The transient `/consent/session` topic is authoritative. Until the logger has
a valid active session, it writes nothing. An event carrying another session
or experimental condition is rejected.

## CSV contract

```text
session_id,condition,event_type,capability,decision,timestamp,response_ms,task_outcome
```

Only state transitions and simulated task outcomes are recorded. The contract
cannot represent audio, images, biometric templates, transcripts, location
histories, questionnaire answers, or arbitrary metadata.

## Failure behaviour

| Failure | Behaviour |
|---|---|
| Invalid logger configuration | Node stays disabled and reports an error |
| `enable_raw_sensor_storage: true` | Node disables itself |
| Missing or malformed active session | Event is not written |
| Wrong session or condition | Event is not written |
| Malformed event semantics | Event is not written |
| Session exceeds 900 seconds | File closes; later events are ignored |
| Existing CSV has another schema | File is not opened |
| Symbolic-link session file | Target is not followed |
| Disk or CSV write failure | Logging for that session stops |

Logging failure never grants a robot capability. Capability authorisation
continues to depend exclusively on the consent manager and privacy gate.

## Running

After rebuilding the ROS 2 Jazzy workspace, launch either condition:

```bash
ros2 launch dynamic_consent_hri static_demo.launch.py
ros2 launch dynamic_consent_hri dynamic_demo.launch.py
```

The logger prints the selected session file. The default location is:

```text
~/.ros/dynamic_consent/logs/session_XXXXXXXX.csv
```

The directory is owner-only (`0700`) and each CSV is owner-only (`0600`).

## Verification

The ROS-free tests cover schema validation, all emitted event shapes, unsafe
identifiers, event-field consistency, file separation, header integrity,
permissions, reopening, and closed-log behaviour:

```bash
cd dynamic_consent_hri
python3 -m pytest test/test_event_log.py -v
```
