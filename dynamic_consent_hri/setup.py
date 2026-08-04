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
            'consent_manager = dynamic_consent_hri.consent_manager:main',
            'privacy_gate = dynamic_consent_hri.privacy_gate:main',
            'consent_ui = dynamic_consent_hri.consent_ui:main',
            'consent_logger = dynamic_consent_hri.consent_logger:main',
            'scenario_simulator = dynamic_consent_hri.scenario_simulator:main',
            'gazebo_motion_adapter = '
            'dynamic_consent_hri.gazebo_motion_adapter:main',
            'study_dashboard = dynamic_consent_hri.study_dashboard:main',
            'experiment_controller = '
            'dynamic_consent_hri.experiment_controller:main',
        ],
    },
)
