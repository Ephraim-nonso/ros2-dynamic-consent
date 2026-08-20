import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'dynamic_consent_hri'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'),
         glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'worlds'),
         glob('worlds/*.sdf')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Chukwu Chinonso Ephraim',
    maintainer_email='chukwuchinonsoephraim@gmail.com',
    description=(
        'Dynamic consent management for privacy-sensitive HRI capabilities.'),
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'consent_manager = '
            'dynamic_consent_hri.nodes.consent_manager_node:main',
            'privacy_gate = '
            'dynamic_consent_hri.nodes.privacy_gate_node:main',
            'consent_ui = '
            'dynamic_consent_hri.nodes.consent_ui_node:main',
            'consent_logger = '
            'dynamic_consent_hri.nodes.consent_logger_node:main',
            'scenario_simulator = '
            'dynamic_consent_hri.nodes.scenario_simulator_node:main',
            'gazebo_motion_adapter = '
            'dynamic_consent_hri.nodes.gazebo_motion_adapter_node:main',
            'study_dashboard = '
            'dynamic_consent_hri.nodes.study_dashboard_node:main',
            'experiment_controller = '
            'dynamic_consent_hri.nodes.experiment_controller_node:main',
            'microphone_guard = '
            'dynamic_consent_hri.nodes.microphone_guard_node:main',
            'logical_camera_guard = '
            'dynamic_consent_hri.nodes.logical_camera_guard_node:main',
            'offline_speech_recognizer = '
            'dynamic_consent_hri.nodes.offline_speech_recognizer_node:main',
            'speech_feedback = '
            'dynamic_consent_hri.nodes.speech_feedback_node:main',
            'research_driver = '
            'dynamic_consent_hri.research.trial_driver_node:main',
            'research_analysis = '
            'dynamic_consent_hri.research.analyze_trials:main',
        ],
    },
)
