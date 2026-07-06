#!/usr/bin/python3
# Copyright (c) 2025, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import click

from isaac_ros_cli.commands.activate import activate
from isaac_ros_cli.commands.init import init
from isaac_ros_cli.commands.status import status


@click.group()
def cli():
    """Isaac ROS CLI - Manage your Isaac ROS development environment."""
    pass


# Register commands
cli.add_command(activate)
cli.add_command(init)
cli.add_command(status)


def main():
    """Main entry point for console script."""
    cli()


if __name__ == '__main__':
    main()
