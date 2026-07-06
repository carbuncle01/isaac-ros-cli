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

# Show configured mode and current activation state
isaac-ros status
isaac-ros status --output json

# Activate environment
isaac-ros activate

# Override config keys for one invocation (see config/config.yaml for available keys)
isaac-ros activate --config docker.run.container_name=foo
isaac-ros activate --config docker.run.container_name=foo -c docker.run.platform=x86_64
```

## Rebuilding Debian Package

To build a new local copy:
```bash
make build
```
