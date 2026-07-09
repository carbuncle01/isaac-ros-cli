#!/bin/bash
#
# Copyright (c) 2021-2024, NVIDIA CORPORATION.  All rights reserved.

set -e

USER_NAME="${USERNAME:-admin}"
USER_HOME="/home/${USER_NAME}"

HOST_USER_UID="${HOST_USER_UID:=1000}"
HOST_USER_GID="${HOST_USER_GID:=1000}"

print_info() {
    echo "workspace-entrypoint: $1"
}

# Enable multicast on loopback for CycloneDDS localhost communication.
/usr/sbin/ip link set lo multicast on

# Tune socket and IP fragment buffers for large ROS messages.
sysctl -w net.core.rmem_max=2147483647
sysctl -w net.ipv4.ipfrag_time=3
sysctl -w net.ipv4.ipfrag_high_thresh=134217728

print_info "Custom network settings applied."

export HOME=${USER_HOME}

# Bind-mounted dotfiles keep the host uid/gid. Avoid recursive chown because
# read-only mounts such as .ssh, .aws, and .profile will reject it.
chown ${HOST_USER_UID}:${HOST_USER_GID} ${USER_HOME} || true

IMAGE_MODEL_ASSETS="/opt/isaac_ros_model_ws/isaac_ros_assets"
if [ -n "${ISAAC_ROS_WS:-}" ] && [ -d "${IMAGE_MODEL_ASSETS}" ]; then
    WORKSPACE_ASSETS="${ISAAC_ROS_WS}/isaac_ros_assets"
    if [ ! -e "${WORKSPACE_ASSETS}" ] && [ ! -L "${WORKSPACE_ASSETS}" ]; then
        ln -s "${IMAGE_MODEL_ASSETS}" "${WORKSPACE_ASSETS}" || true
        print_info "Linked image model assets to ${WORKSPACE_ASSETS}"
    fi
fi

# Joystick devices.
if [ -e /dev/input/js0 ]; then
    HOST_INPUT_GID=$(stat -c '%g' /dev/input/js0)
    print_info "Detected input device GID: ${HOST_INPUT_GID}"
else
    HOST_INPUT_GID=101
fi
EXISTING_GROUP=$(getent group ${HOST_INPUT_GID} | cut -d: -f1)
if [ -n "${EXISTING_GROUP}" ]; then
    usermod -aG ${EXISTING_GROUP} ${USER_NAME}
else
    groupadd -g ${HOST_INPUT_GID} input_host
    usermod -aG input_host ${USER_NAME}
fi

# USB serial devices: VESC and 2D LiDAR.
# Ubuntu normally assigns ttyACM*/ttyUSB* to dialout. Add it even when the
# hardware is connected after container startup, then also mirror any custom
# host GIDs used by udev rules.
if getent group dialout > /dev/null; then
    usermod -aG dialout ${USER_NAME}
fi

for SERIAL_DEVICE in /dev/ttyACM* /dev/ttyUSB*; do
    if [ ! -c "${SERIAL_DEVICE}" ]; then
        continue
    fi

    HOST_SERIAL_GID=$(stat -c '%g' "${SERIAL_DEVICE}")
    EXISTING_SERIAL_GROUP=$(getent group "${HOST_SERIAL_GID}" | cut -d: -f1)
    if [ -n "${EXISTING_SERIAL_GROUP}" ]; then
        usermod -aG "${EXISTING_SERIAL_GROUP}" ${USER_NAME}
    else
        SERIAL_GROUP_NAME="serial_host_${HOST_SERIAL_GID}"
        groupadd -g "${HOST_SERIAL_GID}" "${SERIAL_GROUP_NAME}"
        usermod -aG "${SERIAL_GROUP_NAME}" ${USER_NAME}
    fi
done

# JetRacer GPIO.
if [ -c /dev/gpiochip0 ]; then
    HOST_GPIO_GID=999
    EXISTING_GPIO_GROUP=$(getent group ${HOST_GPIO_GID} | cut -d: -f1)
    if [ -n "${EXISTING_GPIO_GROUP}" ]; then
        usermod -aG ${EXISTING_GPIO_GROUP} ${USER_NAME}
    else
        groupadd -g ${HOST_GPIO_GID} gpio
        usermod -aG gpio ${USER_NAME}
    fi
fi

# JetRacer I2C.
if [ -c /dev/i2c-7 ]; then
    HOST_I2C_GID=$(stat -c '%g' /dev/i2c-7)
    EXISTING_I2C_GROUP=$(getent group ${HOST_I2C_GID} | cut -d: -f1)
    if [ -n "${EXISTING_I2C_GROUP}" ]; then
        usermod -aG ${EXISTING_I2C_GROUP} ${USER_NAME}
    else
        groupadd -g ${HOST_I2C_GID} i2c_host
        usermod -aG i2c_host ${USER_NAME}
    fi
fi

export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:=0}"
print_info "Using ROS_DOMAIN_ID=${ROS_DOMAIN_ID}"
