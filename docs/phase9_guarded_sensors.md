# Phase 9: Guarded real audio and simulated vision

Phase 9 connects the policy demonstration to observable sensor nodes while
remaining usable in an OpenGL-limited UTM virtual machine.

## Sensor boundary

```text
Gazebo logical camera -> /sensors/logical_camera/raw -> logical_camera_guard
                                                      -> /perception/person_present

ALSA microphone -> microphone_guard -> /privacy/speech_input/audio
                                   -> offline_speech_recognizer
                                   -> /perception/speech/transcript
                                   -> speech_feedback
```

The microphone process does not exist before `speech_input` authorization. It
runs for at most eight seconds, streams raw PCM through memory, and is stopped
on revocation, expiry, session replacement, shutdown, or timeout. No audio file
is created.

The Gazebo logical camera is a non-rendering simulated sensor. It reports the
models in its frustum without invoking Ogre 2. The guard consumes that raw
simulation topic continuously but publishes the derived person-presence result
only during a bounded `person_recognition` or `body_pose_tracking` grant. This
tests the policy integration and is not a biometric recognition implementation.

Transcripts are personal data. They are published on a dedicated runtime topic
for the assistant but are deliberately excluded from the anonymous CSV logger.
Applications integrating this demonstration must protect the raw and derived
topics with DDS/SROS 2 permissions before deployment.

## Offline speech dependency

Install the local recognizer and speech output packages in Ubuntu:

```bash
sudo apt update
sudo apt install -y python3-pocketsphinx pocketsphinx-en-us espeak-ng
```

PocketSphinx is intentionally optional at build time. If it is absent, the
recognizer reports `unavailable:pocketsphinx_not_installed`; the microphone
guard remains fail-closed and never redirects audio to an online service.

## Run

```bash
ros2 launch dynamic_consent_hri gazebo_sensor_dynamic_demo.launch.py
```

The static comparison is:

```bash
ros2 launch dynamic_consent_hri gazebo_sensor_static_demo.launch.py
```

The scenario waits for an explicit sensor-completion result at the camera and
microphone stages. A device error, missing camera observation, revocation, or
unrecognized speech invokes the policy fallback instead of being logged as a
successful capability execution.

Inspect the evidence:

```bash
rqt_graph
ros2 topic echo /sensors/logical_camera/status
ros2 topic echo /perception/person_present
ros2 topic echo /sensors/microphone/status
ros2 topic echo /perception/speech/status
ros2 topic echo /assistant/transcript
```

Do not echo `/privacy/speech_input/audio` during participant studies. It is a
raw sensitive stream and exists only as an integration boundary.
