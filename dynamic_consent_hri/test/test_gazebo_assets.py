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


def test_robot_uses_diff_drive_and_the_bridged_velocity_topic():
    robot = _world().find("model[@name='consent_robot']")
    assert robot is not None
    plugin = robot.find("plugin[@name='gz::sim::systems::DiffDrive']")
    assert plugin is not None
    assert plugin.attrib['filename'] == 'gz-sim-diff-drive-system'
    assert plugin.findtext('left_joint') == 'left_wheel_joint'
    assert plugin.findtext('right_joint') == 'right_wheel_joint'
    assert plugin.findtext('topic') == '/model/consent_robot/cmd_vel'


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

    setup_text = (PACKAGE_DIR / 'setup.py').read_text(encoding='utf-8')
    assert "glob('worlds/*.sdf')" in setup_text
    assert 'gazebo_motion_adapter =' in setup_text


def test_manifest_declares_ros_gz_runtime_dependencies():
    root = ET.parse(PACKAGE_DIR / 'package.xml').getroot()
    dependencies = {
        element.text for element in root
        if element.tag in {'depend', 'exec_depend'}
    }
    assert {'geometry_msgs', 'ros_gz_bridge', 'ros_gz_sim'} <= dependencies
