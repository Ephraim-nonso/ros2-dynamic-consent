from pathlib import Path
from types import SimpleNamespace

import pytest

from dynamic_consent_hri.opencv_assets import (
    REQUIRED_HAAR_CASCADES,
    resolve_haar_cascade_directory,
)


def _write_cascades(directory: Path) -> None:
    directory.mkdir(parents=True)
    for filename in REQUIRED_HAAR_CASCADES:
        (directory / filename).write_text('<cascade/>', encoding='utf-8')


def test_resolves_pypi_cv2_data_layout(tmp_path):
    cascade_dir = tmp_path / 'cv2' / 'data'
    _write_cascades(cascade_dir)
    cv2_module = SimpleNamespace(
        data=SimpleNamespace(haarcascades=str(cascade_dir)))
    result = resolve_haar_cascade_directory(
        cv2_module, environment={}, system_paths=())
    assert result == cascade_dir


def test_resolves_ubuntu_system_layout_when_cv2_data_is_absent(tmp_path):
    cascade_dir = tmp_path / 'usr' / 'share' / 'opencv4' / 'haarcascades'
    _write_cascades(cascade_dir)
    cv2_module = SimpleNamespace(__file__='/usr/lib/python3/dist-packages/cv2.so')
    result = resolve_haar_cascade_directory(
        cv2_module, environment={}, system_paths=(cascade_dir,))
    assert result == cascade_dir


def test_environment_override_has_priority(tmp_path):
    override = tmp_path / 'custom-cascades'
    fallback = tmp_path / 'fallback-cascades'
    _write_cascades(override)
    _write_cascades(fallback)
    result = resolve_haar_cascade_directory(
        SimpleNamespace(),
        environment={'OPENCV_HAAR_CASCADES': str(override)},
        system_paths=(fallback,),
    )
    assert result == override


def test_missing_or_incomplete_assets_fail_closed(tmp_path):
    incomplete = tmp_path / 'incomplete'
    incomplete.mkdir()
    (incomplete / REQUIRED_HAAR_CASCADES[0]).write_text(
        '<cascade/>', encoding='utf-8')
    with pytest.raises(FileNotFoundError, match='install opencv-data'):
        resolve_haar_cascade_directory(
            SimpleNamespace(), environment={}, system_paths=(incomplete,))
