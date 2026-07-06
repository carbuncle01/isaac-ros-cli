# Copyright (c) 2025-2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from collections.abc import Mapping, Sequence
import sys
from typing import Any

import click

from isaac_ros_cli.config import (
    InvalidConfigError,
    load_config,
    load_environment_mode,
    parse_config_override,
)
from isaac_ros_cli.platform import detect_platform

# Import mode-specific implementations
from .baremetal import activate_baremetal, is_baremetal_activated
from .docker import activate_docker
from .venv import activate_venv, is_venv_activated


def _docker_only_validator(_ctx, _param, value):
    """Validate that Docker-only arguments are only used in the Docker environment mode."""
    if value and load_environment_mode() != "docker":
        raise click.UsageError("This argument is only valid for the Docker environment mode.")
    return value


def _config_override_validator(_ctx, _param, value):
    """Validate command-line configuration overrides before activation starts."""
    try:
        return [parse_config_override(override) for override in value]
    except ValueError as e:
        raise click.BadParameter(str(e)) from e


@click.command()
@click.option('--verbose', is_flag=True, help='Enable verbose output.')
@click.option('-c', '--config', 'config_overrides', multiple=True, metavar='KEY=VALUE',
              callback=_config_override_validator,
              help='Override a config key for this invocation. Can be specified multiple times; '
                   'values are parsed as YAML.')
# Docker only options
@click.option('--build', is_flag=True,
              help='Docker only: Build the requested Docker image remotely if missing.',
              callback=_docker_only_validator)
@click.option('--build-local', is_flag=True,
              help='Docker only: Build the requested Docker image locally if missing.',
              callback=_docker_only_validator)
@click.option('--push', is_flag=True,
              help='Docker only: Push the image to the target registry when complete.',
              callback=_docker_only_validator)
@click.option('--use-cached-build-image', is_flag=True,
              help='Docker only: Use cached Docker image if available.',
              callback=_docker_only_validator)
@click.option('--no-cache', is_flag=True,
              help='Docker only: Do not use Docker layer cache.',
              callback=_docker_only_validator)
@click.option('--build-only', is_flag=True,
              help='Docker only: Build/pull the image and exit without starting a container. '
                   'Useful for Devcontainer initializeCommand or CI image preparation.',
              callback=_docker_only_validator)
@click.option('--start-only', is_flag=True,
              help='Docker only: Start or attach to a container using an already-available '
                   'image. Fails if the image is not found locally.',
              callback=_docker_only_validator)
def activate(
        build: bool,
        build_local: bool,
        push: bool,
        use_cached_build_image: bool,
        no_cache: bool,
        verbose: bool,
        build_only: bool,
        start_only: bool,
        config_overrides: Sequence[Mapping[str, Any]],
):
    """Activate Isaac ROS development environment based on saved configuration."""

    if build_only and start_only:
        raise click.UsageError("--build-only and --start-only are mutually exclusive.")

    mode = load_environment_mode()

    # Refuse to activate if not initialized
    if mode == "uninitialized":
        click.echo("Error: Environment mode is not set.", err=True)
        click.echo("Please run 'sudo isaac-ros init <environment>' first.", err=True)
        sys.exit(1)

    # Refuse to activate if already activated
    if mode == "docker-activated":
        click.echo("Isaac ROS Docker environment is already activated in this shell.", err=True)
        sys.exit(1)
    elif is_venv_activated():
        click.echo("Isaac ROS virtual environment is already activated in this shell.", err=True)
        sys.exit(1)
    elif is_baremetal_activated():
        click.echo("Isaac ROS baremetal environment is already activated in this shell.", err=True)
        sys.exit(1)

    # Detect platform to forward as ISAAC_ROS_PLATFORM environment variable
    platform = detect_platform()

    try:
        cfg = load_config(extra_overlays=config_overrides)
    except InvalidConfigError as exc:
        raise click.ClickException(str(exc)) from exc

    match mode:
        case 'docker':
            activate_docker(
                cfg=cfg,
                platform=platform,
                build=build,
                build_local=build_local,
                push=push,
                use_cached_build_image=use_cached_build_image,
                no_cache=no_cache,
                verbose=verbose,
                build_only=build_only,
                start_only=start_only,
            )
        case 'venv':
            activate_venv(cfg, platform)
        case 'baremetal':
            activate_baremetal(cfg, platform)
        case _:
            click.echo(f"Error: Invalid environment configuration: {mode}", err=True)
            sys.exit(1)
