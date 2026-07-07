# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from dataclasses import dataclass
from enum import StrEnum

from isaac_ros_cli.commands.activate.baremetal import is_baremetal_activated
from isaac_ros_cli.commands.activate.venv import is_venv_activated
from isaac_ros_cli.config import load_environment_mode


class ConfiguredMode(StrEnum):
    UNINITIALIZED = "uninitialized"
    DOCKER = "docker"
    DOCKER_ACTIVATED = "docker-activated"
    VENV = "venv"
    BAREMETAL = "baremetal"


class PublicMode(StrEnum):
    UNINITIALIZED = "uninitialized"
    DOCKER = "docker"
    VENV = "venv"
    BAREMETAL = "baremetal"


class ActivationState(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class ActiveContext(StrEnum):
    DOCKER = "docker"
    VENV = "venv"
    BAREMETAL = "baremetal"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StatusState:
    mode: PublicMode
    activation: ActivationState


def load_configured_mode() -> ConfiguredMode:
    """Load and validate the configured Isaac ROS CLI mode."""
    mode = load_environment_mode()
    try:
        return ConfiguredMode(mode)
    except ValueError as exc:
        raise ValueError(f"Invalid environment configuration: {mode}") from exc


def probe_activation(probe) -> ActivationState:
    """Convert activation probes into a stable enum."""
    try:
        return ActivationState.ACTIVE if probe() else ActivationState.INACTIVE
    except Exception:
        return ActivationState.UNKNOWN


def get_active_context(mode: ConfiguredMode | None = None) -> ActiveContext | None:
    """Infer which Isaac ROS environment is active in the current shell, if any."""
    if mode is None:
        try:
            mode = load_configured_mode()
        except (FileNotFoundError, KeyError, ValueError):
            mode = None

    if mode == ConfiguredMode.DOCKER_ACTIVATED:
        return ActiveContext.DOCKER

    baremetal_activation = probe_activation(is_baremetal_activated)
    if baremetal_activation == ActivationState.ACTIVE:
        return ActiveContext.BAREMETAL
    if baremetal_activation == ActivationState.UNKNOWN:
        return ActiveContext.UNKNOWN

    venv_activation = probe_activation(is_venv_activated)
    if venv_activation == ActivationState.ACTIVE:
        return ActiveContext.VENV
    if venv_activation == ActivationState.UNKNOWN:
        return ActiveContext.UNKNOWN

    return None


def _public_mode_for(configured_mode: ConfiguredMode) -> PublicMode:
    if configured_mode == ConfiguredMode.UNINITIALIZED:
        return PublicMode.UNINITIALIZED
    if configured_mode in {ConfiguredMode.DOCKER, ConfiguredMode.DOCKER_ACTIVATED}:
        return PublicMode.DOCKER
    if configured_mode == ConfiguredMode.VENV:
        return PublicMode.VENV
    return PublicMode.BAREMETAL


def _activation_for_mode(
    public_mode: PublicMode,
    active_context: ActiveContext | None,
) -> ActivationState:
    if active_context is None:
        return ActivationState.INACTIVE
    if active_context == ActiveContext.UNKNOWN:
        return ActivationState.UNKNOWN
    if active_context.value == public_mode.value:
        return ActivationState.ACTIVE
    return ActivationState.UNKNOWN


def get_status_state() -> StatusState:
    """Return the public Isaac ROS CLI mode and activation state."""
    configured_mode = load_configured_mode()
    if configured_mode == ConfiguredMode.UNINITIALIZED:
        return StatusState(
            mode=PublicMode.UNINITIALIZED,
            activation=ActivationState.INACTIVE,
        )

    public_mode = _public_mode_for(configured_mode)
    active_context = get_active_context(configured_mode)
    return StatusState(
        mode=public_mode,
        activation=_activation_for_mode(public_mode, active_context),
    )
