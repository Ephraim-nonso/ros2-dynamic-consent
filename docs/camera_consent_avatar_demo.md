# Camera-only consent avatar demonstration

This is an intentionally isolated demonstration of one privacy-sensitive
sensor. It does not launch the seven-stage study, microphone, speech
recognition, navigation, or the earlier sensor scenario.

The experiment tests this claim:

> The Mac camera remains closed until explicit consent is granted, then live
> frames and temporary expression measurements animate a Gazebo avatar, and
> refusal, revocation, expiry, or shutdown closes the camera and neutralises
> the avatar.

The avatar mirrors head direction, head tilt, probable blinking, smiling, and
lower-face movement while the participant talks. Talking is observed visually;
the microphone is not opened and speech content is not interpreted.

## Why a Mac relay is required

UTM cannot pass an Apple built-in camera to the Ubuntu guest as `/dev/video0`.
The macOS helper therefore owns the physical camera and exposes authenticated,
memory-only JPEG frames to the VM. Starting the helper does **not** open the
camera. The ROS gateway sends `/start` only after the privacy gate publishes an
authorization and sends `/stop` when access ends.

The transport is intended for an isolated local UTM network. It uses a bearer
token but not TLS; do not expose its port to an untrusted network.

## 1. Start the relay on macOS

Run these commands in macOS Terminal from a clone of this repository:

```bash
python3 -m venv .camera-relay-venv
source .camera-relay-venv/bin/activate
python -m pip install -r requirements-macos-camera.txt
python tools/mac_camera_relay.py
```

The helper prints a random relay token. Keep this terminal running and copy the
token. It should initially print `the camera is CLOSED`. The first authorized
request may cause macOS to ask whether Terminal or Python may use the camera.
Approve that operating-system prompt.

If macOS previously denied access, enable it under **System Settings → Privacy
& Security → Camera**.

## 2. Find the Mac address from Ubuntu

With UTM shared networking, the Mac host is commonly the guest's default
gateway. In Ubuntu:

```bash
ip route show default
```

Use the address after `via`. It is commonly `10.0.2.2`. Confirm authenticated
reachability, replacing the token and address:

```bash
curl -H "Authorization: Bearer RELAY_TOKEN" \
  http://10.0.2.2:8765/status
```

The expected initial response includes `"active": false`. If it cannot
connect, allow incoming Python connections in the macOS firewall and verify
that UTM is using shared networking.

## 3. Build and launch in Ubuntu

```bash
cd ~/dynamic_consent_ws
source /opt/ros/jazzy/setup.bash

rosdep install --from-paths src --ignore-src -r -y
sudo apt install -y opencv-data
colcon build --symlink-install
source install/setup.bash

ros2 launch dynamic_consent_hri camera_consent_avatar_demo.launch.py \
  relay_url:=http://10.0.2.2:8765 \
  relay_token:=RELAY_TOKEN
```

The camera viewer initially displays `CAMERA OFF - CONSENT REQUIRED`. Choose:

```text
[1] Allow
[2] Refuse
[3] View more information
```

After choosing Allow, the Mac camera indicator should turn on, the viewer
should show the live annotated face, and the Gazebo robot should mirror visible
facial actions. Access automatically ends after 60 seconds.

## Expected evidence

Observe the state and derived expression without viewing raw frames:

```bash
ros2 topic echo /camera_consent/status
ros2 topic echo /camera_consent/expression
```

Raw authorized frames exist only on:

```text
/camera_consent/live_image
```

The viewer uses `/camera_consent/annotated_image`, which displays a generated
privacy notice while the camera is inactive.

Expected behavior:

| Action | Mac camera | Image viewer | Gazebo avatar |
|---|---|---|---|
| Before decision | Closed | Privacy notice | Neutral |
| Refuse | Closed | Privacy notice | Neutral |
| Allow | Open for at most 60 s | Live face | Mirrors expressions |
| No face visible | Open within grant | Live scene | Neutral |
| Revoke / expiry | Closed | Privacy notice | Neutral |
| Stop ROS launch | Closed | Closes | Neutral before shutdown |

## Revocation test

Read the active anonymous session:

```bash
ros2 topic echo /consent/session \
  --qos-durability transient_local --once
```

Then revoke while the live view is active:

```bash
ros2 service call /consent/revoke \
  dynamic_consent_interfaces/srv/RevokeConsent \
  "{session_id: 'session_XXXXXXXX', capability_id: 'camera_expression_mirroring'}"
```

The Mac camera indicator should turn off, the last face must be replaced by the
privacy notice, and all avatar joints must return to neutral.

## Research limitations

OpenCV Haar cascades and frame-to-frame lower-face activity are used to keep
the demo offline and simple. Blink, smile, and talking labels are approximate,
not clinical or affective inferences. No face embedding, identity template,
emotion classification, recording, or participant profile is created.
