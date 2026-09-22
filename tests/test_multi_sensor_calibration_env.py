# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.

"""Tests for the offline RGB/EVS calibration Python environment."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile.additional_setting"
REQUIREMENTS = REPO_ROOT / "docker" / "requirements-multi-sensor-calibration.txt"


class TestMultiSensorCalibrationEnvironment(unittest.TestCase):
    def test_environment_uses_system_ros_packages(self):
        source = DOCKERFILE.read_text(encoding="utf-8")

        self.assertIn("--system-site-packages", source)
        self.assertIn("/opt/multi_sensor_calibration_env", source)
        self.assertIn("import cv2, numpy, rosbags, yaml", source)

    def test_requirements_keep_numpy_one_x_and_rosbags_pinned(self):
        requirements = REQUIREMENTS.read_text(encoding="utf-8")

        self.assertIn("numpy==1.26.4", requirements)
        self.assertIn("rosbags==0.11.3", requirements)
        self.assertNotIn("opencv-python", requirements)


if __name__ == "__main__":
    unittest.main()
