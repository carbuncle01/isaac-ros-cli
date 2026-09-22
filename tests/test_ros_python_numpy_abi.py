# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.

"""Tests for the NumPy ABI used by system ROS Python extensions."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / 'docker' / 'Dockerfile.additional_setting'


class TestRosPythonNumpyAbi(unittest.TestCase):
    """Keep ROS/OpenCV separate from the NumPy 2.x ML environment."""

    def test_system_numpy_is_pinned_to_the_ros_abi(self):
        source = DOCKERFILE.read_text(encoding='utf-8')

        self.assertIn('ARG ROS_SYSTEM_NUMPY_VERSION=1.26.4', source)
        self.assertIn('--reinstall --no-deps', source)
        self.assertIn('"numpy==${ROS_SYSTEM_NUMPY_VERSION}"', source)

    def test_image_build_validates_opencv_import(self):
        source = DOCKERFILE.read_text(encoding='utf-8')

        self.assertIn('import cv2, numpy', source)
        self.assertIn("numpy.__version__ == '${ROS_SYSTEM_NUMPY_VERSION}'", source)

    def test_ml_numpy_remains_inside_opt_env(self):
        source = DOCKERFILE.read_text(encoding='utf-8')

        self.assertIn('uv pip install --python /opt/env/bin/python', source)
        source = (REPO_ROOT / 'docker' / 'requirements-training-amd64.txt').read_text()
        self.assertIn('numpy==2.4.6', source)


if __name__ == '__main__':
    unittest.main()
