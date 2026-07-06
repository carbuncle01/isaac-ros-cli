# Copyright (c) 2025-2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import os
import subprocess

from isaac_ros_cli.config import IsaacRosCliConfig
from isaac_ros_cli.platform import Platform

RUN_DEV_SCRIPT = '/usr/lib/isaac-ros-cli/run_dev.py'


def _get_isaac_ros_ws_from_environment():
    if "ISAAC_ROS_WS" in os.environ:
        return os.environ['ISAAC_ROS_WS']
    if "ISAAC_DIR" in os.environ:
        return os.environ['ISAAC_DIR']
    raise ValueError("ISAAC_ROS_WS or ISAAC_DIR environment variable is not set")


def _get_isaac_debian_build_args(cfg: IsaacRosCliConfig):
    apt_config = getattr(cfg, "apt", None)
    if apt_config is None:
        return []

    build_args = [
        f"ISAAC_DEBIAN_KEY_URL={apt_config.key_url}",
        f"ISAAC_DEBIAN_REPOSITORY={apt_config.repository}",
        "ISAAC_DEBIAN_COMPONENTS=" + " ".join(apt_config.components),
    ]

    if apt_config.distro != "auto":
        build_args.append(f"ISAAC_DEBIAN_DIST={apt_config.distro}")

    return build_args


def _build_run_dev_command(
    cfg: IsaacRosCliConfig,
    build: bool,
    build_local: bool,
    push: bool,
    use_cached_build_image: bool,
    no_cache: bool,
    verbose: bool,
    isaac_ros_platform: Platform,
    build_only: bool = False,
    start_only: bool = False,
):
    cmd = [
        RUN_DEV_SCRIPT,
    ]

    if build_only:
        cmd.extend(["--mode", "build"])
    elif start_only:
        cmd.extend(["--mode", "start"])

    env_keys = cfg.docker.image.base_image_keys + cfg.docker.image.additional_image_keys

    for key in env_keys:
        cmd.extend(["--env", key])

    container_name = cfg.docker.run.container_name
    cmd.extend(["--container-name", container_name])

    platform = cfg.docker.run.platform
    if platform == 'auto':
        platform = os.uname().machine
    cmd.extend(["--platform", platform])

    # Pass the Isaac ROS platform for setting inside the container (convert to string)
    cmd.extend(["--isaac-ros-platform", str(isaac_ros_platform)])

    isaac_dir = _get_isaac_ros_ws_from_environment()
    cmd.extend(["--isaac-dir", isaac_dir])

    for build_arg in _get_isaac_debian_build_args(cfg):
        cmd.extend(["--build-arg", build_arg])

    # Forward runtime flags
    if build:
        cmd.append("--build")
    if build_local:
        cmd.append("--build-local")
    if push:
        cmd.append("--push")
    if use_cached_build_image:
        cmd.append("--use-cached-build-image")
    if no_cache:
        cmd.append("--no-cache")
    if verbose:
        cmd.append("--verbose")
    return cmd


def activate_docker(
    cfg: IsaacRosCliConfig,
    platform: Platform,
    build: bool,
    build_local: bool,
    push: bool,
    use_cached_build_image: bool,
    no_cache: bool,
    verbose: bool,
    build_only: bool = False,
    start_only: bool = False,
):
    """Activate Docker-based Isaac ROS environment by delegating to run_dev.py."""
    cmd = _build_run_dev_command(
        cfg, build, build_local, push, use_cached_build_image, no_cache, verbose,
        platform, build_only=build_only, start_only=start_only)

    # run run_dev.py
    subprocess.run(cmd, check=False)
