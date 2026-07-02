# Isaac ROS CLI

A command-line interface for managing Isaac ROS development environments.

## Installation

```bash
sudo apt-get install isaac-ros-cli
```

## Usage

```bash
# Show help
isaac-ros --help

# Initialize environment (pick a mode)
sudo isaac-ros init <docker|venv|baremetal>

# Activate environment
isaac-ros activate
```

## Hardware devices

The Docker development environment bind-mounts the host `/dev` tree into the
container and runs with `--privileged`. This makes USB serial devices such as
`/dev/ttyACM*` and `/dev/ttyUSB*`, libusb devices, input devices, and stable
udev symlinks visible inside the container, including devices reconnected after
the container starts.

For a vehicle deployment, configure stable host udev symlinks such as
`/dev/vesc` and `/dev/lidar` instead of relying on enumeration-dependent names
such as `/dev/ttyACM0`.

The `additional_setting` image clones
[Hokuyo-aut/urg_node2](https://github.com/Hokuyo-aut/urg_node2) recursively at
a pinned revision, generates a ROS Debian package with Bloom, and installs it
with `apt-get`. Verify the installed package inside the rebuilt container with:

```bash
ros2 pkg prefix urg_node2
dpkg -s ros-jazzy-urg-node2
```

## Rebuilding Debian Package

To build a new local copy:
```bash
make build
```
