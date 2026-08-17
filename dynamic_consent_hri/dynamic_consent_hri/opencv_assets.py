"""Portable discovery of OpenCV Haar cascade data files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


REQUIRED_HAAR_CASCADES = (
    'haarcascade_frontalface_default.xml',
    'haarcascade_eye_tree_eyeglasses.xml',
    'haarcascade_smile.xml',
)


def resolve_haar_cascade_directory(
        cv2_module, *, environment: Mapping[str, str] | None = None,
        system_paths: tuple[Path, ...] | None = None) -> Path:
    """Return a directory containing every cascade required by the demo.

    PyPI OpenCV wheels expose ``cv2.data.haarcascades``. Debian and Ubuntu's
    Python binding may omit ``cv2.data`` and install the same XML assets under
    ``/usr/share/opencv4/haarcascades`` via the ``opencv-data`` package.
    """
    environment = os.environ if environment is None else environment
    if system_paths is None:
        system_paths = (
            Path('/usr/share/opencv4/haarcascades'),
            Path('/usr/local/share/opencv4/haarcascades'),
            Path('/usr/share/opencv/haarcascades'),
        )

    candidates: list[Path] = []
    override = environment.get('OPENCV_HAAR_CASCADES', '').strip()
    if override:
        candidates.append(Path(override).expanduser())

    data_module = getattr(cv2_module, 'data', None)
    wheel_path = getattr(data_module, 'haarcascades', '')
    if wheel_path:
        candidates.append(Path(wheel_path))

    module_file = getattr(cv2_module, '__file__', '')
    if module_file:
        module_dir = Path(module_file).resolve().parent
        candidates.extend((
            module_dir / 'data',
            module_dir / 'data' / 'haarcascades',
        ))
    candidates.extend(system_paths)

    checked: list[Path] = []
    for candidate in candidates:
        normalized = candidate.resolve(strict=False)
        if normalized in checked:
            continue
        checked.append(normalized)
        if all((normalized / filename).is_file()
               for filename in REQUIRED_HAAR_CASCADES):
            return normalized

    locations = ', '.join(str(path) for path in checked) or '<none>'
    raise FileNotFoundError(
        'required OpenCV Haar cascades were not found; install opencv-data '
        'or set OPENCV_HAAR_CASCADES. Checked: ' + locations)
