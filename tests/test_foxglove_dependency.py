# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.

"""Tests for the explicit JetPilot Foxglove bridge dependency."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / 'docker' / 'Dockerfile.additional_setting'


class TestFoxgloveDependency(unittest.TestCase):
    """Keep Foxglove available independently of transitive dependencies."""

    def test_bridge_is_explicitly_installed_by_the_jetpilot_layer(self):
        source = DOCKERFILE.read_text(encoding='utf-8')

        self.assertIn('ros-jazzy-foxglove-bridge', source)
        self.assertEqual(source.count('ros-jazzy-foxglove-bridge'), 1)


if __name__ == '__main__':
    unittest.main()
