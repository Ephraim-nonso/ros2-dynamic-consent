from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

from dynamic_consent_hri.scenario_logic import SCENARIO_STAGES


PACKAGE_DIR = Path(__file__).resolve().parents[1]
WORLD_PATH = PACKAGE_DIR / 'worlds' / 'dynamic_consent_building.sdf'


def _world():
    return ET.parse(WORLD_PATH).getroot().find("world")


def test_world_is_self_contained_and_has_a_privacy_boundary():
    text = WORLD_PATH.read_text(encoding='utf-8')
    world = _world()
    assert world is not None
    assert world.attrib['name'] == 'dynamic_consent_world'
    assert world.find("model[@name='privacy_boundary']") is not None
    assert world.find("model[@name='restricted_private_area']") is not None
    assert 'http://' not in text
    assert 'https://' not in text
    assert 'model://' not in text


def test_world_contains_every_privacy_scenario_marker():
    model_names = {model.attrib['name'] for model in _world().findall('model')}
    expected = {
        f'stage_{stage.number}_{stage.capability_id}'
        for stage in SCENARIO_STAGES
    }
    assert expected <= model_names


def test_world_makes_the_assistance_task_and_private_room_visible():
    model_names = {model.attrib['name'] for model in _world().findall('model')}
    assert {
        'visitor_requesting_assistance',
        'reception_start_point',
        'private_room_entrance',
        'assistance_destination',
        'authorised_staff_assistance_station',
        'status_indicator_legend',
    } <= model_names


def test_world_has_an_observer_camera_and_study_controls():
    world = _world()
    scene = world.find("gui/plugin[@filename='MinimalScene']")
    assert scene is not None
    assert scene.findtext('camera_pose')
    assert world.find("gui/plugin[@filename='WorldControl']") is not None
    assert world.find("gui/plugin[@filename='EntityTree']") is not None


def test_robot_uses_diff_drive_and_the_bridged_velocity_topic():
    robot = _world().find("model[@name='consent_robot']")
    assert robot is not None
    plugin = robot.find("plugin[@name='gz::sim::systems::DiffDrive']")
    assert plugin is not None
    assert plugin.attrib['filename'] == 'gz-sim-diff-drive-system'
    assert plugin.findtext('left_joint') == 'left_wheel_joint'
    assert plugin.findtext('right_joint') == 'right_wheel_joint'
    assert plugin.findtext('topic') == '/model/consent_robot/cmd_vel'


def test_robot_has_humanoid_body_and_non_rendering_logical_camera():
    world = _world()
    robot = world.find("model[@name='consent_robot']")
    assert robot.find("link[@name='torso_link']") is not None
    head = robot.find("link[@name='sensor_head']")
    assert head is not None
    sensor = head.find("sensor[@name='privacy_logical_camera']")
    assert sensor is not None
    assert sensor.attrib['type'] == 'logical_camera'
    assert sensor.findtext('topic') == '/sensors/logical_camera/raw'
    assert sensor.find('logical_camera') is not None
    plugin = world.find(
        "plugin[@name='gz::sim::systems::LogicalCamera']")
    assert plugin is not None
    assert plugin.attrib['filename'] == 'gz-sim-logical-camera-system'


def test_motion_configuration_matches_world_topic():
    config = yaml.safe_load(
        (PACKAGE_DIR / 'config' / 'gazebo_demo.yaml').read_text(
            encoding='utf-8'))
    params = config['gazebo_motion_adapter']['ros__parameters']
    assert params['cmd_vel_topic'] == '/model/consent_robot/cmd_vel'
    assert params['forward_speed'] * params['forward_duration_seconds'] == 0.4


def test_gazebo_launches_and_assets_are_installed():
    launch_dir = PACKAGE_DIR / 'launch'
    assert (launch_dir / 'gazebo_dynamic_demo.launch.py').is_file()
    assert (launch_dir / 'gazebo_static_demo.launch.py').is_file()
    assert (launch_dir / 'gazebo_sensor_dynamic_demo.launch.py').is_file()
    assert (launch_dir / 'gazebo_sensor_static_demo.launch.py').is_file()

    setup_text = (PACKAGE_DIR / 'setup.py').read_text(encoding='utf-8')
    assert "glob('worlds/*.sdf')" in setup_text
    assert 'gazebo_motion_adapter =' in setup_text
    assert 'study_dashboard =' in setup_text
    assert 'experiment_controller =' in setup_text
    assert 'microphone_guard =' in setup_text
    assert 'logical_camera_guard =' in setup_text
    assert 'offline_speech_recognizer =' in setup_text
    assert 'speech_feedback =' in setup_text


def test_manifest_declares_ros_gz_runtime_dependencies():
    root = ET.parse(PACKAGE_DIR / 'package.xml').getroot()
    dependencies = {
        element.text for element in root
        if element.tag in {'depend', 'exec_depend'}
    }
    assert {
        'geometry_msgs',
        'nav_msgs',
        'sensor_msgs',
        'std_srvs',
        'ros_gz_bridge',
        'ros_gz_interfaces',
        'ros_gz_sim',
    } <= dependencies


def test_manifest_declares_launch_integration_test_dependency():
    root = ET.parse(PACKAGE_DIR / 'package.xml').getroot()
    test_dependencies = {
        element.text for element in root if element.tag == 'test_depend'
    }
    assert {'python3-pytest', 'launch_pytest'} <= test_dependencies


def test_launch_includes_dashboard_and_coordinated_world_reset():
    source = (PACKAGE_DIR / 'dynamic_consent_hri'
              / 'gazebo_demo_launch.py').read_text(encoding='utf-8')
    assert 'study_dashboard' in source
    assert 'experiment_controller' in source
    assert '/world/dynamic_consent_world/control' in source
    assert 'ros_gz_interfaces/srv/ControlWorld' in source
    assert '/model/consent_robot/odometry' in source
    assert 'nav_msgs/msg/Odometry' in source
    assert 'ros_gz_interfaces/msg/LogicalCameraImage' in source
    assert 'logical_camera_guard' in source
    assert 'microphone_guard' in source
