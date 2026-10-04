# kart branch

Isaac ROS 5.0 / ROS 2 Lyrical base, targeting JetPack 7.2.

- Host `ISAAC_ROS_WS=<project>/ros2_ws`; parent must contain `packages.repos`.
- Mount the project once at `/workspaces`, work in `/workspaces/ros2_ws`.
- Container `ISAAC_ROS_WS` and `ISAAC_DIR` are `/workspaces/ros2_ws`.
- Host shell profiles and SSH/AWS credentials are not automatically mounted.
- Extra Docker arguments use upstream `DOCKER_ARGS_FILE`; comments are accepted.
- Upstream device access and privileged mode are unchanged.

Project Dockerfiles, requirements, sensor selection and entrypoint additions live
in the parent kart repository. No JetPilot sensor, CUDA workaround, or model
package is enabled by default. Upstream image hash/build/cache behavior is retained.

Build with `make build`, install with `sudo make install`, then initialize with
`sudo isaac-ros init docker`. Parent scripts provide setup. Build the `.deb` on
Ubuntu, not macOS. Reinitializing an existing installation should be reviewed
against other projects that use the system-wide CLI.

---

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
isaac-ros activate -c docker.image.push=true

# Override the configured image push default for one invocation
isaac-ros activate --push
isaac-ros activate --no-push
```

## Rebuilding Debian Package

To build a new local copy:
```bash
make build
```
