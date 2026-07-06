# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import json
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from isaac_ros_cli.commands.status import status
from isaac_ros_cli.runtime_state import (
    ActivationState,
    ActiveContext,
    ConfiguredMode,
    get_status_state,
    PublicMode,
    StatusState,
)


class StatusStateTests(unittest.TestCase):

    def _common_patches(self):
        return patch.multiple(
            "isaac_ros_cli.runtime_state",
            load_configured_mode=unittest.mock.DEFAULT,
            get_active_context=unittest.mock.DEFAULT,
        )

    def test_status_state_reports_uninitialized_mode(self):
        """Report uninitialized explicitly so automation can distinguish setup
        from runtime state."""
        with self._common_patches() as mocks:
            mocks["load_configured_mode"].return_value = ConfiguredMode.UNINITIALIZED

            state = get_status_state()

        self.assertEqual(
            state,
            StatusState(
                mode=PublicMode.UNINITIALIZED,
                activation=ActivationState.INACTIVE,
            ),
        )
        mocks["get_active_context"].assert_not_called()

    def test_status_state_reports_docker_mode_on_host(self):
        """Keep configured Docker mode distinct from an already-activated container shell."""
        with self._common_patches() as mocks:
            mocks["load_configured_mode"].return_value = ConfiguredMode.DOCKER
            mocks["get_active_context"].return_value = None

            state = get_status_state()

        self.assertEqual(
            state,
            StatusState(
                mode=PublicMode.DOCKER,
                activation=ActivationState.INACTIVE,
            ),
        )
        mocks["get_active_context"].assert_called_once_with(ConfiguredMode.DOCKER)

    def test_status_state_treats_docker_activated_as_active_docker(self):
        """Treat docker-activated as docker mode with active activation."""
        with self._common_patches() as mocks:
            mocks["load_configured_mode"].return_value = ConfiguredMode.DOCKER_ACTIVATED
            mocks["get_active_context"].return_value = ActiveContext.DOCKER

            state = get_status_state()

        self.assertEqual(
            state,
            StatusState(
                mode=PublicMode.DOCKER,
                activation=ActivationState.ACTIVE,
            ),
        )
        mocks["get_active_context"].assert_called_once_with(
            ConfiguredMode.DOCKER_ACTIVATED
        )

    def test_status_state_reports_unknown_for_docker_mode_in_baremetal_shell(self):
        """Treat a mismatched active shell as unknown instead of pretending Docker is inactive."""
        with self._common_patches() as mocks:
            mocks["load_configured_mode"].return_value = ConfiguredMode.DOCKER
            mocks["get_active_context"].return_value = ActiveContext.BAREMETAL

            state = get_status_state()

        self.assertEqual(
            state,
            StatusState(
                mode=PublicMode.DOCKER,
                activation=ActivationState.UNKNOWN,
            ),
        )
        mocks["get_active_context"].assert_called_once_with(ConfiguredMode.DOCKER)

    def test_status_state_reports_venv_activation(self):
        """Surface managed-venv activation as a machine-readable state for host-side tooling."""
        with self._common_patches() as mocks:
            mocks["load_configured_mode"].return_value = ConfiguredMode.VENV
            mocks["get_active_context"].return_value = ActiveContext.VENV

            state = get_status_state()

        self.assertEqual(
            state,
            StatusState(
                mode=PublicMode.VENV,
                activation=ActivationState.ACTIVE,
            ),
        )
        mocks["get_active_context"].assert_called_once_with(ConfiguredMode.VENV)

    def test_status_state_reports_unknown_for_venv_mode_in_baremetal_shell(self):
        """Treat a mismatched active shell as unknown instead of pretending
        the venv is inactive."""
        with self._common_patches() as mocks:
            mocks["load_configured_mode"].return_value = ConfiguredMode.VENV
            mocks["get_active_context"].return_value = ActiveContext.BAREMETAL

            state = get_status_state()

        self.assertEqual(
            state,
            StatusState(
                mode=PublicMode.VENV,
                activation=ActivationState.UNKNOWN,
            ),
        )
        mocks["get_active_context"].assert_called_once_with(ConfiguredMode.VENV)

    def test_status_state_reports_baremetal_inactive(self):
        """Preserve the inactive baremetal case so callers do not assume the
        shell is already primed."""
        with self._common_patches() as mocks:
            mocks["load_configured_mode"].return_value = ConfiguredMode.BAREMETAL
            mocks["get_active_context"].return_value = None

            state = get_status_state()

        self.assertEqual(
            state,
            StatusState(
                mode=PublicMode.BAREMETAL,
                activation=ActivationState.INACTIVE,
            ),
        )
        mocks["get_active_context"].assert_called_once_with(ConfiguredMode.BAREMETAL)

    def test_status_state_surfaces_unknown_activation_when_probe_fails(self):
        """Return unknown when activation probes fail so the CLI does not
        silently lie to automation."""
        with self._common_patches() as mocks:
            mocks["load_configured_mode"].return_value = ConfiguredMode.VENV
            mocks["get_active_context"].return_value = ActiveContext.UNKNOWN

            state = get_status_state()

        self.assertEqual(
            state,
            StatusState(
                mode=PublicMode.VENV,
                activation=ActivationState.UNKNOWN,
            ),
        )
        mocks["get_active_context"].assert_called_once_with(ConfiguredMode.VENV)


class StatusCommandTests(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_status_rejects_invalid_mode_strings(self):
        """Turn corrupted mode files into a hard CLI error instead of guessing
        at a fallback state."""
        with patch(
            "isaac_ros_cli.commands.status.get_status_state",
            side_effect=ValueError("Invalid environment configuration: mystery"),
        ):
            result = self.runner.invoke(status, [])

        self.assertEqual(result.exit_code, 1)

    def test_status_text_output_stays_human_readable(self):
        """Keep the default text mode concise for users inspecting state interactively."""
        with patch(
            "isaac_ros_cli.commands.status.get_status_state",
            return_value=StatusState(
                mode=PublicMode.BAREMETAL,
                activation=ActivationState.ACTIVE,
            ),
        ):
            result = self.runner.invoke(status, [])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            result.output,
            "mode: baremetal\nactivation: active\n",
        )

    def test_status_short_output_flag_selects_json(self):
        """Support the shorthand output flag so scripts can request JSON with minimal CLI noise."""
        with patch(
            "isaac_ros_cli.commands.status.get_status_state",
            return_value=StatusState(
                mode=PublicMode.DOCKER,
                activation=ActivationState.INACTIVE,
            ),
        ):
            result = self.runner.invoke(status, ["-o", "json"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(
            json.loads(result.output),
            {
                "activation": "inactive",
                "mode": "docker",
            },
        )


if __name__ == "__main__":
    unittest.main()
