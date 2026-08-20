"""Resolve files installed with the ROS package."""

import os


def resolve_policy_path(policy_file: str) -> str:
    if os.path.isabs(policy_file):
        return policy_file
    from ament_index_python.packages import get_package_share_directory
    share = get_package_share_directory('dynamic_consent_hri')
    return os.path.join(share, 'config', policy_file)
