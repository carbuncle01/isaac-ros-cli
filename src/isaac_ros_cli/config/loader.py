# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from collections.abc import Mapping, Sequence
from enum import auto, Enum
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .validator import (
    InvalidConfigError,
    IsaacRosCliConfig,
    validate_config,
    validate_config_overlay,
)

ENVIRONMENT_MODE_CONFIG_PATH = Path("/etc/isaac-ros-cli/environment.conf")


class ConfigScope(Enum):
    # In order of precedence
    READ_ONLY = auto()
    SYSTEM = auto()
    USER = auto()
    WORKSPACE = auto()


_CONFIG_SOURCE_CANDIDATES: Dict[ConfigScope, Optional[Path]] = {
    # Read-only default config, shipped with the package
    ConfigScope.READ_ONLY: Path("/usr/share/isaac-ros-cli/config.yaml"),

    # System-level overrides, written to by the CLI
    ConfigScope.SYSTEM: Path("/etc/isaac-ros-cli/config.yaml"),

    # User-level overrides, written to by the user and mentioned in the documentation
    ConfigScope.USER: Path.home() / ".config" / "isaac-ros-cli" / "config.yaml",

    # Workspace-level overrides, for power users
    ConfigScope.WORKSPACE: (
        Path(os.getenv("ISAAC_ROS_WS", "")) / ".isaac-ros-cli" / "config.yaml"
    ) if os.getenv("ISAAC_ROS_WS") else None,
}


def load_environment_mode() -> str:
    """Load the environment mode from the environment mode configuration file."""
    if not ENVIRONMENT_MODE_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Environment mode configuration file not found at {ENVIRONMENT_MODE_CONFIG_PATH}.")
    with open(ENVIRONMENT_MODE_CONFIG_PATH, "r") as f:
        for line in f:
            key, _, value = line.strip().partition("=")
            if key == "ISAAC_ROS_ENVIRONMENT":
                return value
    raise KeyError("ISAAC_ROS_ENVIRONMENT not found in environment mode configuration file.")


def update_environment_mode(mode: str) -> None:
    """Update the environment mode in the environment mode configuration file."""
    if not ENVIRONMENT_MODE_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Environment mode configuration file not found at {ENVIRONMENT_MODE_CONFIG_PATH}.")
    with open(ENVIRONMENT_MODE_CONFIG_PATH, "w") as f:
        f.write(f"ISAAC_ROS_ENVIRONMENT={mode}\n")


def load_config(
    extra_overlays: Optional[Sequence[Mapping[str, Any]]] = None,
) -> IsaacRosCliConfig:
    """Load the merged Isaac ROS CLI configuration."""
    sources: List[Path] = []
    for path in _CONFIG_SOURCE_CANDIDATES.values():
        # Skip unavailable paths
        if path is None:
            continue

        if path.exists():
            sources.append(path)

    if not sources:
        raise FileNotFoundError(
            "No Isaac ROS CLI configuration files found. Tried: "
            + ", ".join(
                str(path)
                for path in _CONFIG_SOURCE_CANDIDATES.values()
                if path is not None
            )
        )

    merged: Dict[str, Any] = {}
    for path in sources:
        overlay = _load_config_mapping(path)
        merged = _deep_merge(
            merged,
            validate_config_overlay(
                overlay,
                source=path,
            ).dict(exclude_unset=True, exclude_none=True),
        )

    for overlay in extra_overlays or ():
        merged = _deep_merge(
            merged,
            validate_config_overlay(
                overlay,
                source="extra config overlay",
            ).dict(exclude_unset=True, exclude_none=True),
        )

    return validate_config(merged)


def update_config(overlay: Mapping[str, Any], scope: ConfigScope) -> Path:
    """Update requested scope configuration with the given overlay.

    Parameters
    ----------
    overlay
        Mapping to update the configuration with.
    scope
        Scope to write the configuration to.

    Returns
    -------
    target
        Path to the updated configuration file.
    """

    if scope == ConfigScope.READ_ONLY:
        raise ValueError("Cannot write to read-only config.")

    target = _CONFIG_SOURCE_CANDIDATES[scope]
    if target is None:
        raise ValueError("Cannot write workspace config: ISAAC_ROS_WS is not set.")
    target.parent.mkdir(parents=True, exist_ok=True)

    # Load the existing configuration if it exists
    config = {}
    original_permissions = None
    if target.exists():
        original_permissions = target.stat().st_mode
        config = validate_config_overlay(
            _load_config_mapping(target),
            source=target,
        ).dict(exclude_unset=True, exclude_none=True)

    # Merge the overlay with the existing configuration
    config = _deep_merge(
        config,
        validate_config_overlay(
            overlay,
            source=f"{scope.name.lower()} config overlay",
        ).dict(exclude_unset=True, exclude_none=True),
    )
    validated_overlay = validate_config_overlay(config, source=target)

    # Write the updated configuration to the target
    with target.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            validated_overlay.dict(exclude_unset=True, exclude_none=True),
            f,
            sort_keys=False,
        )

    if original_permissions is not None:
        target.chmod(original_permissions)

    return target


def _deep_merge(base: Dict[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result: Dict[str, Any] = dict(base)

    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def _load_config_mapping(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        loaded = yaml.safe_load(file_handle)

    if not isinstance(loaded, Mapping):
        raise InvalidConfigError(
            f"Configuration file {path} must contain a YAML mapping at the top level."
        )

    return dict(loaded)
