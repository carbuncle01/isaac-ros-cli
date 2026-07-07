# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import unittest

from isaac_ros_cli.config import parse_config_override


class ConfigOverrideParserTests(unittest.TestCase):

    def test_rejects_malformed_entries(self):
        """Surface typoed override syntax before command execution."""
        for override in ("docker.run.container_name", ".docker.run.name=value",
                         "docker..run.name=value"):
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    parse_config_override(override)

    def test_parses_nested_overlay(self):
        """Convert one dotted override into one nested overlay."""
        overlay = parse_config_override("docker.run.platform=x86_64")

        self.assertEqual(
            overlay,
            {"docker": {"run": {"platform": "x86_64"}}},
        )

    def test_parses_yaml_values(self):
        """Keep command-line value semantics aligned with YAML config files."""
        bool_overlay = parse_config_override("docker.run.use_cached_build_image=true")
        list_overlay = parse_config_override(
            "docker.image.additional_image_keys=[zed, realsense]"
        )

        self.assertTrue(bool_overlay["docker"]["run"]["use_cached_build_image"])
        self.assertEqual(
            list_overlay["docker"]["image"]["additional_image_keys"],
            ["zed", "realsense"],
        )

    def test_parses_empty_numeric_and_single_level_overrides(self):
        """Cover scalar edge cases without involving config schema validation."""
        self.assertEqual(parse_config_override("field="), {"field": ""})
        self.assertEqual(parse_config_override("port=8080"), {"port": 8080})
        self.assertEqual(parse_config_override("field=value"), {"field": "value"})


if __name__ == "__main__":
    unittest.main()
