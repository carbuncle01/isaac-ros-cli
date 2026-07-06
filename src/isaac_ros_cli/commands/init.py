# Copyright (c) 2025-2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import os
import subprocess
import sys

import click

from isaac_ros_cli.config import update_environment_mode
from isaac_ros_cli.runtime_state import get_active_context

ISAAC_ROS_GROUP_NAME = "isaac-ros-cli"


def _is_interactive_terminal() -> bool:
    """Return True when stdin and stderr are connected to a TTY."""
    return bool(getattr(sys.stdin, "isatty", lambda: False)()) and bool(
        getattr(sys.stderr, "isatty", lambda: False)()
    )


@click.command()
@click.argument('environment', type=click.Choice(['docker', 'venv', 'baremetal']))
@click.option('--yes', is_flag=True, help='Do not prompt for confirmation (non-interactive).')
def init(environment, yes):
    """
    Initialize Isaac ROS development environment mode.

    Requires sudo to modify system configuration.
    """
    # Require root privileges
    try:
        is_root = os.geteuid() == 0
    except AttributeError:
        click.echo("Error: os.geteuid() failed -- are you in a UNIX environment?", err=True)
        sys.exit(1)

    if not is_root:
        click.echo("Error: This command requires administrator (sudo) privileges.", err=True)
        click.echo("Please rerun with sudo.", err=True)
        sys.exit(1)

    active_context = get_active_context()
    if active_context is not None:
        click.echo(
            "Error: Isaac ROS CLI cannot be reconfigured from an activated environment.",
            err=True,
        )
        click.echo(
            "Exit the current Isaac ROS shell and rerun 'isaac-ros init' from a clean host shell.",
            err=True,
        )
        sys.exit(1)

    # Baremetal requires explicit acknowledgment due to system package risks
    if environment == 'baremetal' and not yes:
        if not _is_interactive_terminal():
            click.echo(
                "Error: Non-interactive session detected for baremetal mode. "
                "Re-run with --yes to acknowledge risks.",
                err=True,
            )
            sys.exit(1)

        if not click.confirm(
            """
            You selected 'baremetal' mode.

            In this mode, pip installs will run against the system Python with the flag:
            \t\t--break-system-packages

            This can overwrite or remove distro-managed files and may break your system.

            Proceed and configure Isaac ROS CLI to use 'baremetal' mode?
            """,
            default=False,
            err=True
        ):
            click.echo("Aborted. No changes made.", err=True)
            sys.exit(1)

    # Add user to venv-owning group if in venv mode
    if environment == 'venv':

        user = os.environ.get("SUDO_USER")
        if not user:
            click.echo("Error: Unable to determine invoking user -- are you sudo?", err=True)
            sys.exit(1)

        try:
            subprocess.run(
                ["usermod", "--append", "--groups", ISAAC_ROS_GROUP_NAME, user],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            click.echo(
                f"Error: Failed to add user '{user}' to group '{ISAAC_ROS_GROUP_NAME}': {e}",
                err=True,
            )
            sys.exit(1)

        click.echo(
            f"""
            You selected 'venv' mode.

            In this mode, pip installs will run in the Isaac ROS CLI-managed virtual environment.

            Your user '{user}' has been automatically added to group '{ISAAC_ROS_GROUP_NAME}'.
            Only members of '{ISAAC_ROS_GROUP_NAME}' can modify the virtual environment.
            """
        )
        click.secho(
            f"""
            Open a new shell or run the following command for membership to take effect:
            \t\tnewgrp {ISAAC_ROS_GROUP_NAME}

            Add other users who need write access with:
            \t\tsudo usermod -aG {ISAAC_ROS_GROUP_NAME} <username>
            """,
            fg="yellow",
            bold=True
        )

    try:
        update_environment_mode(environment)

        click.echo(f"Set environment mode to {environment}.")

    except Exception as e:
        click.echo(f"Error: Failed to write configuration: {e}", err=True)
        sys.exit(1)
