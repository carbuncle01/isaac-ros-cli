# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import json

import click

from isaac_ros_cli.runtime_state import get_status_state


@click.command()
@click.option(
    "-o",
    "--output",
    "output_mode",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output mode.",
)
def status(output_mode):
    """Show the configured Isaac ROS CLI mode and current activation state."""
    try:
        state = get_status_state()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    payload = {
        "mode": state.mode.value,
        "activation": state.activation.value,
    }

    if output_mode == "json":
        click.echo(json.dumps(payload, sort_keys=True))
        return

    click.echo(f"mode: {payload['mode']}")
    click.echo(f"activation: {payload['activation']}")
