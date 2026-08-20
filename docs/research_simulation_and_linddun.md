# No-participant simulation and LINDDUN analysis

## Purpose

This workflow evaluates the consent protocol, fallback behaviour, Gazebo
motion, logging boundary, and failure handling without claiming to measure
participant understanding or acceptance. The `research_driver` makes explicit
synthetic decisions; it is not a substitute for user responses.

## Build

From a sourced ROS 2 Jazzy workspace:

```bash
colcon build --packages-select dynamic_consent_hri --symlink-install
source install/setup.bash
```

## Run one dynamic trial

```bash
ros2 launch dynamic_consent_hri research_dynamic_simulation.launch.py \
  headless:=true \
  decision_strategy:=grant_all \
  trial_label:=dynamic_grant
```

The driver automatically answers prompts and writes one JSON summary beneath
`~/.ros/dynamic_consent/research`. The simulated robot still runs through the
same seven stages, gate, manager, Gazebo world, motion adapter, dashboard, and
anonymous logger used by the normal study launch.

Available synthetic strategies are:

| Strategy | Purpose |
|---|---|
| `grant_all` | Exercise the fully authorised path and robot progress |
| `refuse_all` | Exercise all configured fallbacks |
| `alternate` | Exercise mixed grant/refusal ordering in dynamic mode; static mode refuses the combined disclosure because static consent is atomic |
| `risk_weighted` | Refuse the explicitly high-privacy capabilities and grant the remainder in dynamic mode; static mode refuses the combined disclosure |

Run the static condition with the equivalent launch file:

```bash
ros2 launch dynamic_consent_hri research_static_simulation.launch.py \
  headless:=true \
  decision_strategy:=grant_all \
  trial_label:=static_grant
```

For a small matrix, run separate processes with different labels and output
directories. Keep one Gazebo launch active at a time because all trials use the
same ROS/Gazebo topic names.

The driver records only closed telemetry: condition, synthetic strategy,
capability decisions, stage outcomes, event counts, completion, duration, and
odometry delta. It does not record audio, images, transcripts, names, or free
text.

## Analyse the trial set

```bash
ros2 run dynamic_consent_hri research_analysis \
  --input ~/.ros/dynamic_consent/research \
  --output ~/.ros/dynamic_consent/research/analysis
```

Outputs:

```text
research_summary.csv       grouped completion, fallback, grant, duration, and motion metrics
linddun_assessment.json     machine-readable threat assessment
linddun_assessment.md       report suitable for research notes
```

The seven LINDDUN categories are mapped to this implementation as follows:

| Category | Main question for this package |
|---|---|
| Linkability | Can events or sensor activity be linked across sessions? |
| Identifiability | Can sensor data identify a person? |
| Non-repudiation | Can the system prove which consent/outcome event occurred? |
| Detectability | Can an observer detect that a sensor or capability is active? |
| Disclosure of Information | Can raw audio, images, poses, or transcripts escape? |
| Unawareness | Does the prompt explain purpose, inputs, processing, recipients, and retention? |
| Non-compliance | Can implementation or deployment bypass the declared policy? |

The generated report deliberately marks Unawareness as
`high_without_users`: a simulation can verify prompt contents, but cannot
establish that a person understood them. Similarly, residual risk for raw ROS
topics remains until DDS/SROS permissions and the deployment network are
assessed.

## What the simulation establishes

It can provide evidence for:

- deterministic static/dynamic consent timing;
- explicit grant/refusal enforcement;
- fallback selection and stage ordering;
- bounded robot motion and private-boundary behaviour;
- session reset and anonymous log rotation;
- fail-closed handling of malformed or unavailable dependencies;
- absence of raw sensor content in generated study artifacts.

It cannot provide evidence for:

- user comprehension, trust, comfort, workload, or perceived intrusiveness;
- whether users would grant or refuse in a real interaction;
- real microphone/camera recognition quality;
- security of a deployed ROS network without a separate DDS/SROS review.

Use the existing ROS/Gazebo integration suite as a second check:

```bash
colcon test --packages-select dynamic_consent_hri \
  --event-handlers console_direct+
colcon test-result --verbose
```
