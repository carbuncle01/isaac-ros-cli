# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

from contextlib import ExitStack
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from click.testing import CliRunner

from isaac_ros_cli.commands.init import init
from isaac_ros_cli.config import loader as config_loader
from isaac_ros_cli.runtime_state import ActiveContext


_DEFAULT = object()


class InitCommandTests(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self._tmpdir = TemporaryDirectory()
        self.environment_mode_path = Path(self._tmpdir.name) / "environment.conf"
        self.environment_mode_path.write_text(
            "ISAAC_ROS_ENVIRONMENT=uninitialized\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmpdir.cleanup()

    def _current_mode(self):
        return self.environment_mode_path.read_text(encoding="utf-8").strip()

    def _invoke_init(
        self,
        args,
        *,
        geteuid=0,
        env=_DEFAULT,
        active_context=_DEFAULT,
        confirm=_DEFAULT,
        subprocess_run=_DEFAULT,
        update_environment_mode=_DEFAULT,
    ):
        """Run init with only the scenario-specific collaborators patched.

        This keeps each test focused on the single branch it cares about while
        centralizing the boilerplate required to route config writes into a
        temporary file.
        """
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    config_loader,
                    "ENVIRONMENT_MODE_CONFIG_PATH",
                    self.environment_mode_path,
                )
            )

            if isinstance(geteuid, BaseException):
                stack.enter_context(
                    patch(
                        "isaac_ros_cli.commands.init.os.geteuid",
                        side_effect=geteuid,
                    )
                )
            else:
                stack.enter_context(
                    patch(
                        "isaac_ros_cli.commands.init.os.geteuid",
                        return_value=geteuid,
                    )
                )

            if env is not _DEFAULT:
                stack.enter_context(
                    patch.dict("isaac_ros_cli.commands.init.os.environ", env, clear=True)
                )

            if confirm is not _DEFAULT:
                confirm_mock = stack.enter_context(
                    patch("isaac_ros_cli.commands.init.click.confirm", return_value=confirm)
                )
            else:
                confirm_mock = None

            if active_context is _DEFAULT:
                active_context_mock = stack.enter_context(
                    patch(
                        "isaac_ros_cli.commands.init.get_active_context",
                        return_value=None,
                    )
                )
            else:
                active_context_mock = stack.enter_context(
                    patch(
                        "isaac_ros_cli.commands.init.get_active_context",
                        return_value=active_context,
                    )
                )

            if subprocess_run is not _DEFAULT:
                subprocess_mock = stack.enter_context(
                    patch(
                        "isaac_ros_cli.commands.init.subprocess.run",
                        **subprocess_run,
                    )
                )
            else:
                subprocess_mock = None

            if update_environment_mode is _DEFAULT:
                update_patch = patch(
                    "isaac_ros_cli.commands.init.update_environment_mode",
                    new=config_loader.update_environment_mode,
                )
            else:
                update_patch = patch(
                    "isaac_ros_cli.commands.init.update_environment_mode",
                    **update_environment_mode,
                )
            update_mock = stack.enter_context(update_patch)

            result = self.runner.invoke(init, args)

        return result, confirm_mock, subprocess_mock, update_mock, active_context_mock

    def test_init_requires_root(self):
        """Keep system-mode changes behind an explicit privilege boundary."""
        result, _confirm, _subprocess, _update, _active_context = self._invoke_init(
            ["docker"],
            geteuid=1000,
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")

    def test_init_handles_missing_geteuid(self):
        """Treat unsupported host environments as a CLI error instead of misconfiguring state."""
        result, _confirm, _subprocess, _update, _active_context = self._invoke_init(
            ["docker"],
            geteuid=AttributeError(),
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")

    def test_init_baremetal_requires_confirmation(self):
        """Require an explicit acknowledgement before enabling the riskiest installation mode."""
        result, _confirm, _subprocess, _update, _active_context = self._invoke_init(
            ["baremetal"],
            confirm=False,
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")

    def test_init_baremetal_yes_skips_confirmation(self):
        """Allow automation to opt in cleanly without hanging on an interactive prompt."""
        result, confirm, _subprocess, _update, _active_context = self._invoke_init(
            ["baremetal", "--yes"]
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIsNone(confirm)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=baremetal")

    def test_init_refuses_to_run_in_active_docker_shell(self):
        """Force users to exit an active Docker shell before changing persisted mode."""
        result, confirm, run_usermod, update_mode, _active_context = self._invoke_init(
            ["docker"],
            active_context=ActiveContext.DOCKER,
            update_environment_mode={},
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")
        self.assertIsNone(confirm)
        self.assertIsNone(run_usermod)
        update_mode.assert_not_called()
        _active_context.assert_called_once_with()

    def test_init_refuses_to_run_in_active_venv_shell(self):
        """Prevent reconfiguration from a managed venv shell whose state still affects commands."""
        result, confirm, run_usermod, update_mode, _active_context = self._invoke_init(
            ["docker"],
            active_context=ActiveContext.VENV,
            update_environment_mode={},
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")
        self.assertIsNone(confirm)
        self.assertIsNone(run_usermod)
        update_mode.assert_not_called()
        _active_context.assert_called_once_with()

    def test_init_refuses_to_run_in_active_baremetal_shell(self):
        """Prevent contradictory config changes while the current host shell
        is still marked active."""
        result, confirm, run_usermod, update_mode, _active_context = self._invoke_init(
            ["docker"],
            active_context=ActiveContext.BAREMETAL,
            update_environment_mode={},
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")
        self.assertIsNone(confirm)
        self.assertIsNone(run_usermod)
        update_mode.assert_not_called()
        _active_context.assert_called_once_with()

    def test_init_venv_requires_sudo_user(self):
        """Fail loudly when we cannot determine who should receive venv group membership."""
        result, _confirm, _subprocess, _update, _active_context = self._invoke_init(
            ["venv"],
            env={},
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")

    def test_init_venv_surfaces_group_add_failures(self):
        """Preserve the real group-management error instead of masking it as a later config bug."""
        result, _confirm, _subprocess, _update, _active_context = self._invoke_init(
            ["venv"],
            env={"SUDO_USER": "alice"},
            subprocess_run={"side_effect": subprocess.CalledProcessError(1, ["usermod"])},
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")

    def test_init_venv_updates_mode_after_group_setup(self):
        """Ensure init commits mode only after the prerequisite access grant succeeds."""
        result, _confirm, run_usermod, _update, _active_context = self._invoke_init(
            ["venv"],
            env={"SUDO_USER": "alice"},
            subprocess_run={},
        )

        self.assertEqual(result.exit_code, 0)
        run_usermod.assert_called_once_with(
            ["usermod", "--append", "--groups", "isaac-ros-cli", "alice"],
            check=True,
        )
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=venv")

    def test_init_surfaces_configuration_write_errors(self):
        """Verify the final persistence step reports its own failure path clearly."""
        result, _confirm, _subprocess, _update, _active_context = self._invoke_init(
            ["docker"],
            update_environment_mode={"side_effect": RuntimeError("boom")},
        )

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(self._current_mode(), "ISAAC_ROS_ENVIRONMENT=uninitialized")


if __name__ == "__main__":
    unittest.main()
