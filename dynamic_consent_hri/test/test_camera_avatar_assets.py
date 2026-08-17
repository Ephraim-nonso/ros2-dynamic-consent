from pathlib import Path
import xml.etree.ElementTree as ET

from dynamic_consent_hri.policy_loader import load_policy


PACKAGE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = PACKAGE_DIR.parent
WORLD_PATH = PACKAGE_DIR / 'worlds' / 'camera_consent_avatar.sdf'


def test_camera_avatar_policy_has_exactly_one_non_identifying_capability():
    policy = load_policy(PACKAGE_DIR / 'config' / 'camera_avatar_policy.yaml')
    assert set(policy.capabilities) == {'camera_expression_mirroring'}
    capability = policy.get('camera_expression_mirroring')
    assert capability.retention == 'not_stored'
    assert capability.recipients == ('local_gazebo_avatar',)
    assert 'not used to identify you' in capability.prompt
    assert capability.refusal_fallback == (
        'keep_camera_closed_and_avatar_neutral')


def test_avatar_world_has_four_controlled_expression_joints():
    world = ET.parse(WORLD_PATH).getroot().find('world')
    assert world is not None
    avatar = world.find("model[@name='consent_avatar']")
    assert avatar is not None
    assert avatar.find("joint[@name='head_yaw_joint']") is not None
    assert avatar.find("joint[@name='head_roll_joint']") is not None
    assert avatar.find("joint[@name='eyelid_joint']") is not None
    assert avatar.find("joint[@name='jaw_joint']") is not None
    topics = {
        plugin.findtext('topic') for plugin in avatar.findall('plugin')
    }
    assert topics == {
        '/avatar/head_yaw',
        '/avatar/head_roll',
        '/avatar/eyelid',
        '/avatar/jaw',
    }


def test_dedicated_launch_contains_only_camera_capability_components():
    launch = (PACKAGE_DIR / 'launch'
              / 'camera_consent_avatar_demo.launch.py').read_text(
                  encoding='utf-8')
    assert 'camera_avatar_gateway' in launch
    assert 'camera_avatar_policy.yaml' in launch
    assert 'rqt_image_view' in launch
    assert '/avatar/head_yaw' in launch
    assert 'microphone_guard' not in launch
    assert 'scenario_simulator' not in launch


def test_mac_relay_requires_bearer_token_and_explicit_start():
    source = (REPO_DIR / 'tools' / 'mac_camera_relay.py').read_text(
        encoding='utf-8')
    assert "self.path == '/start'" in source
    assert "self.path == '/stop'" in source
    assert "f'Bearer {token}'" in source
    assert 'cv2.VideoCapture' in source
    assert 'CameraRelay(' in source


def test_gateway_never_publishes_raw_frames_while_inactive_by_design():
    source = (PACKAGE_DIR / 'dynamic_consent_hri'
              / 'camera_avatar_gateway.py').read_text(encoding='utf-8')
    process = source.index('def _process_authorized_frame')
    publish_raw = source.index('self._publish_image(frame, self._raw_pub)')
    assert publish_raw > process
    assert "_stop_camera('refused')" in source
    assert 'authorization_window_expired' in source
