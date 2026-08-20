from pathlib import Path

import pytest
import yaml

from dynamic_consent_hri.core.conditions import validate_consent_mode


PACKAGE_DIR = Path(__file__).resolve().parents[2]
CONFIG_DIR = PACKAGE_DIR / 'config'
LAUNCH_DIR = PACKAGE_DIR / 'launch'


def _load_condition(name):
    return yaml.safe_load((CONFIG_DIR / name).read_text(encoding='utf-8'))


@pytest.mark.parametrize('mode', ['static', 'dynamic'])
def test_valid_condition(mode):
    assert validate_consent_mode(mode) == mode


@pytest.mark.parametrize('mode', ['', 'STATIC', 'unknown', None, 1])
def test_invalid_condition_is_rejected(mode):
    with pytest.raises(ValueError, match='consent_mode'):
        validate_consent_mode(mode)


def test_condition_configs_start_identical_parameterized_nodes():
    static = _load_condition('static_condition.yaml')
    dynamic = _load_condition('dynamic_condition.yaml')
    expected_nodes = {
        'consent_manager', 'privacy_gate', 'consent_logger',
        'scenario_simulator'}
    assert set(static) == expected_nodes
    assert set(dynamic) == expected_nodes

    for node_name in expected_nodes:
        assert (static[node_name]['ros__parameters']['consent_mode']
                == 'static')
        assert (dynamic[node_name]['ros__parameters']['consent_mode']
                == 'dynamic')


def test_scenario_parameters_are_identical_between_conditions():
    static = _load_condition('static_condition.yaml')
    dynamic = _load_condition('dynamic_condition.yaml')
    static_params = dict(
        static['scenario_simulator']['ros__parameters'])
    dynamic_params = dict(
        dynamic['scenario_simulator']['ros__parameters'])
    static_params.pop('consent_mode')
    dynamic_params.pop('consent_mode')
    assert static_params == dynamic_params


def test_logger_is_anonymous_and_identical_between_conditions():
    static = _load_condition('static_condition.yaml')
    dynamic = _load_condition('dynamic_condition.yaml')
    static_params = dict(static['consent_logger']['ros__parameters'])
    dynamic_params = dict(dynamic['consent_logger']['ros__parameters'])
    static_params.pop('consent_mode')
    dynamic_params.pop('consent_mode')
    assert static_params == dynamic_params
    assert static_params['enable_raw_sensor_storage'] is False
    assert static_params['session_timeout_seconds'] == 900.0
    assert static_params['log_directory'].endswith(
        '/dynamic_consent/logs')


def test_only_declared_consent_design_parameters_differ():
    static = _load_condition('static_condition.yaml')
    dynamic = _load_condition('dynamic_condition.yaml')
    for node_name in ('privacy_gate', 'consent_logger',
                      'scenario_simulator'):
        static_params = dict(static[node_name]['ros__parameters'])
        dynamic_params = dict(dynamic[node_name]['ros__parameters'])
        static_params.pop('consent_mode')
        dynamic_params.pop('consent_mode')
        assert static_params == dynamic_params

    static_manager = dict(
        static['consent_manager']['ros__parameters'])
    dynamic_manager = dict(
        dynamic['consent_manager']['ros__parameters'])
    disclosure = static_manager.pop('static_disclosure')
    static_manager.pop('consent_mode')
    dynamic_manager.pop('consent_mode')
    assert static_manager == dynamic_manager
    assert 'recognise returning users' in disclosure
    assert 'remember preferences for 30 days' in disclosure
    assert 'authorised building assistance staff' in disclosure
    assert 'private-space boundary' in disclosure


def test_condition_launch_files_exist():
    assert (LAUNCH_DIR / 'static_demo.launch.py').is_file()
    assert (LAUNCH_DIR / 'dynamic_demo.launch.py').is_file()
