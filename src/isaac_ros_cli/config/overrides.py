# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from typing import Any, Dict

import yaml


def parse_config_override(override: str) -> Dict[str, Any]:
    """Parse one command-line KEY=VALUE config override into a config overlay."""
    if "=" not in override:
        raise ValueError(
            f"Configuration override {override!r} must use KEY=VALUE syntax."
        )

    key, value = override.split("=", 1)
    key_path = [part.strip() for part in key.strip().split(".")]
    if not key_path or any(not part for part in key_path):
        raise ValueError(
            f"Configuration override {override!r} must include a dotted key path."
        )

    if value == "":
        parsed_value = ""
    else:
        try:
            parsed_value = yaml.safe_load(value)
        except yaml.YAMLError as e:
            raise ValueError(
                f"Configuration override {override!r} contains invalid YAML: {e}"
            ) from e

    result: Dict[str, Any] = {}
    cursor = result
    for part in key_path[:-1]:
        cursor[part] = {}
        cursor = cursor[part]
    cursor[key_path[-1]] = parsed_value
    return result
