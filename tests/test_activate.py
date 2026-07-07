# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

import unittest
from unittest.mock import patch

from click.testing import CliRunner

from isaac_ros_cli.commands.activate import activate
from isaac_ros_cli.config import InvalidConfigError, IsaacRosCliConfig, SUPPORTED_CONFIG_VERSION
from isaac_ros_cli.platform import Platform


class ActivateCommandTests(unittest.TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def _common_patches(self):
        return patch.multiple(
            "isaac_ros_cli.commands.activate",
            load_config=unittest.mock.DEFAULT,
            load_environment_mode=unittest.mock.DEFAULT,
            is_venv_activated=unittest.mock.DEFAULT,
            is_baremetal_activated=unittest.mock.DEFAULT,
            detect_platform=unittest.mock.DEFAULT,
            activate_docker=unittest.mock.DEFAULT,
            activate_venv=unittest.mock.DEFAULT,
            activate_baremetal=unittest.mock.DEFAULT,
        )

    def _cfg(self):
        return IsaacRosCliConfig.parse_obj(
            {
                "version": SUPPORTED_CONFIG_VERSION,
                "docker": {
                    "image": {
                        "base_image_keys": ["base"],
                        "additional_image_keys": [],
                    },
                    "run": {
                        "container_name": "container",
                        "entrypoint": "/entrypoint.sh",
                        "workdir": "/workspace",
                        "platform": "auto",
                        "use_cached_build_image": False,
                    },
                },
            }
        )

    def test_activate_rejects_uninitialized_environment(self):
        """Fail before platform detection so an uninitialized install stays recoverable."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "uninitialized"
            mocks["is_venv_activated"].return_value = False
            mocks["is_baremetal_activated"].return_value = False

            result = self.runner.invoke(activate, [])

        self.assertEqual(result.exit_code, 1)
        mocks["detect_platform"].assert_not_called()
        mocks["activate_docker"].assert_not_called()
        mocks["activate_venv"].assert_not_called()
        mocks["activate_baremetal"].assert_not_called()

    def test_activate_dispatches_docker_mode_with_flags(self):
        """Verify the CLI forwards the full user intent unchanged on the Docker path."""
        for platform in Platform:
            with self.subTest(platform=platform):
                with self._common_patches() as mocks:
                    cfg = self._cfg()
                    mocks["load_environment_mode"].return_value = "docker"
                    mocks["load_config"].return_value = cfg
                    mocks["is_venv_activated"].return_value = False
                    mocks["is_baremetal_activated"].return_value = False
                    mocks["detect_platform"].return_value = platform

                    result = self.runner.invoke(
                        activate,
                        ["--build", "--build-local", "--push", "--use-cached-build-image",
                         "--no-cache", "--verbose"],
                    )

                self.assertEqual(result.exit_code, 0)
                mocks["load_config"].assert_called_once_with(extra_overlays=[])
                mocks["activate_docker"].assert_called_once_with(
                    cfg=cfg,
                    platform=platform,
                    build=True,
                    build_local=True,
                    push=True,
                    use_cached_build_image=True,
                    no_cache=True,
                    verbose=True,
                    build_only=False,
                    start_only=False,
                )
                mocks["activate_venv"].assert_not_called()
                mocks["activate_baremetal"].assert_not_called()

    def test_activate_dispatches_docker_mode_with_config_overrides(self):
        """Keep non-persistent command-line config overrides attached to Docker activation."""
        with self._common_patches() as mocks:
            cfg = self._cfg()
            mocks["load_environment_mode"].return_value = "docker"
            mocks["load_config"].return_value = cfg
            mocks["is_venv_activated"].return_value = False
            mocks["is_baremetal_activated"].return_value = False
            mocks["detect_platform"].return_value = Platform.AMD64

            result = self.runner.invoke(
                activate,
                [
                    "--config", "docker.run.container_name=ci_container",
                    "-c", "docker.run.platform=x86_64",
                ],
            )

        self.assertEqual(result.exit_code, 0)
        mocks["load_config"].assert_called_once_with(
            extra_overlays=[
                {
                    "docker": {
                        "run": {
                            "container_name": "ci_container",
                        },
                    },
                },
                {
                    "docker": {
                        "run": {
                            "platform": "x86_64",
                        },
                    },
                },
            ]
        )
        mocks["activate_docker"].assert_called_once_with(
            cfg=cfg,
            platform=Platform.AMD64,
            build=False,
            build_local=False,
            push=False,
            use_cached_build_image=False,
            no_cache=False,
            verbose=False,
            build_only=False,
            start_only=False,
        )
        mocks["activate_venv"].assert_not_called()
        mocks["activate_baremetal"].assert_not_called()

    def test_activate_rejects_malformed_config_override(self):
        """Invalid KEY=VALUE overrides should fail as CLI usage errors."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "docker"

            result = self.runner.invoke(activate, ["--config", "docker.run.platform"])

        self.assertEqual(result.exit_code, 2)
        mocks["activate_docker"].assert_not_called()

    def test_activate_docker_with_build_only_flag(self):
        """Ensure --build-only reaches activate_docker and skips container start."""
        for platform in Platform:
            with self.subTest(platform=platform):
                with self._common_patches() as mocks:
                    cfg = self._cfg()
                    mocks["load_environment_mode"].return_value = "docker"
                    mocks["load_config"].return_value = cfg
                    mocks["is_venv_activated"].return_value = False
                    mocks["is_baremetal_activated"].return_value = False
                    mocks["detect_platform"].return_value = platform

                    result = self.runner.invoke(activate, ["--build-only"])

                self.assertEqual(result.exit_code, 0)
                mocks["load_config"].assert_called_once_with(extra_overlays=[])
                mocks["activate_docker"].assert_called_once_with(
                    cfg=cfg,
                    platform=platform,
                    build=False,
                    build_local=False,
                    push=False,
                    use_cached_build_image=False,
                    no_cache=False,
                    verbose=False,
                    build_only=True,
                    start_only=False,
                )
                mocks["activate_venv"].assert_not_called()
                mocks["activate_baremetal"].assert_not_called()

    def test_activate_docker_with_start_only_flag(self):
        """Ensure --start-only reaches activate_docker and skips image build."""
        for platform in Platform:
            with self.subTest(platform=platform):
                with self._common_patches() as mocks:
                    cfg = self._cfg()
                    mocks["load_environment_mode"].return_value = "docker"
                    mocks["load_config"].return_value = cfg
                    mocks["is_venv_activated"].return_value = False
                    mocks["is_baremetal_activated"].return_value = False
                    mocks["detect_platform"].return_value = platform

                    result = self.runner.invoke(activate, ["--start-only"])

                self.assertEqual(result.exit_code, 0)
                mocks["load_config"].assert_called_once_with(extra_overlays=[])
                mocks["activate_docker"].assert_called_once_with(
                    cfg=cfg,
                    platform=platform,
                    build=False,
                    build_local=False,
                    push=False,
                    use_cached_build_image=False,
                    no_cache=False,
                    verbose=False,
                    build_only=False,
                    start_only=True,
                )
                mocks["activate_venv"].assert_not_called()
                mocks["activate_baremetal"].assert_not_called()

    def test_activate_rejects_conflicting_build_and_start_only_flags(self):
        """Mutually exclusive flags must be caught before any real work begins."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "docker"
            mocks["is_venv_activated"].return_value = False
            mocks["is_baremetal_activated"].return_value = False

            result = self.runner.invoke(activate, ["--build-only", "--start-only"])

        self.assertEqual(result.exit_code, 2)
        mocks["detect_platform"].assert_not_called()
        mocks["activate_docker"].assert_not_called()

    def test_activate_rejects_build_only_flag_in_non_docker_modes(self):
        """--build-only is meaningless outside Docker; reject early with a clear error."""
        for mode in ("venv", "baremetal"):
            with self.subTest(mode=mode):
                with self._common_patches() as mocks:
                    mocks["load_environment_mode"].return_value = mode
                    mocks["is_venv_activated"].return_value = False
                    mocks["is_baremetal_activated"].return_value = False

                    result = self.runner.invoke(activate, ["--build-only"])

                self.assertEqual(result.exit_code, 2)
                mocks["activate_docker"].assert_not_called()
                mocks["activate_venv"].assert_not_called()
                mocks["activate_baremetal"].assert_not_called()

    def test_activate_rejects_start_only_flag_in_non_docker_modes(self):
        """--start-only is meaningless outside Docker; reject early with a clear error."""
        for mode in ("venv", "baremetal"):
            with self.subTest(mode=mode):
                with self._common_patches() as mocks:
                    mocks["load_environment_mode"].return_value = mode
                    mocks["is_venv_activated"].return_value = False
                    mocks["is_baremetal_activated"].return_value = False

                    result = self.runner.invoke(activate, ["--start-only"])

                self.assertEqual(result.exit_code, 2)
                mocks["activate_docker"].assert_not_called()
                mocks["activate_venv"].assert_not_called()
                mocks["activate_baremetal"].assert_not_called()

    def test_activate_dispatches_venv_mode(self):
        """Check that non-Docker modes still receive platform context from the CLI layer."""
        for platform in Platform:
            with self.subTest(platform=platform):
                with self._common_patches() as mocks:
                    cfg = self._cfg()
                    mocks["load_environment_mode"].return_value = "venv"
                    mocks["load_config"].return_value = cfg
                    mocks["is_venv_activated"].return_value = False
                    mocks["is_baremetal_activated"].return_value = False
                    mocks["detect_platform"].return_value = platform

                    result = self.runner.invoke(activate, [])

                self.assertEqual(result.exit_code, 0)
                mocks["load_config"].assert_called_once_with(extra_overlays=[])
                mocks["activate_venv"].assert_called_once_with(cfg, platform)
                mocks["activate_docker"].assert_not_called()
                mocks["activate_baremetal"].assert_not_called()

    def test_activate_dispatches_baremetal_mode(self):
        """Guard the baremetal dispatch path so mode selection never falls through silently."""
        for platform in Platform:
            with self.subTest(platform=platform):
                with self._common_patches() as mocks:
                    cfg = self._cfg()
                    mocks["load_environment_mode"].return_value = "baremetal"
                    mocks["load_config"].return_value = cfg
                    mocks["is_venv_activated"].return_value = False
                    mocks["is_baremetal_activated"].return_value = False
                    mocks["detect_platform"].return_value = platform

                    result = self.runner.invoke(activate, [])

                self.assertEqual(result.exit_code, 0)
                mocks["load_config"].assert_called_once_with(extra_overlays=[])
                mocks["activate_baremetal"].assert_called_once_with(cfg, platform)
                mocks["activate_docker"].assert_not_called()
                mocks["activate_venv"].assert_not_called()

    def test_activate_blocks_when_docker_environment_is_already_active(self):
        """Prevent nested Docker activation from spawning confusing recursive shells."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "docker-activated"
            mocks["is_venv_activated"].return_value = False
            mocks["is_baremetal_activated"].return_value = False

            result = self.runner.invoke(activate, [])

        self.assertEqual(result.exit_code, 1)
        mocks["detect_platform"].assert_not_called()
        mocks["activate_docker"].assert_not_called()
        mocks["activate_venv"].assert_not_called()
        mocks["activate_baremetal"].assert_not_called()

    def test_activate_blocks_when_venv_is_already_active(self):
        """Avoid re-entering the managed venv, which would hide genuine user state mistakes."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "docker"
            mocks["is_venv_activated"].return_value = True
            mocks["is_baremetal_activated"].return_value = False

            result = self.runner.invoke(activate, [])

        self.assertEqual(result.exit_code, 1)
        mocks["detect_platform"].assert_not_called()
        mocks["activate_docker"].assert_not_called()
        mocks["activate_venv"].assert_not_called()
        mocks["activate_baremetal"].assert_not_called()

    def test_activate_blocks_when_baremetal_is_already_active(self):
        """Mirror the other activation guards so host-shell state is treated consistently."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "docker"
            mocks["is_venv_activated"].return_value = False
            mocks["is_baremetal_activated"].return_value = True

            result = self.runner.invoke(activate, [])

        self.assertEqual(result.exit_code, 1)
        mocks["detect_platform"].assert_not_called()
        mocks["activate_docker"].assert_not_called()
        mocks["activate_venv"].assert_not_called()
        mocks["activate_baremetal"].assert_not_called()

    def test_activate_rejects_docker_only_flags_in_non_docker_modes(self):
        """Catch mode-specific flag misuse at parse time instead of ignoring the request later."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "venv"
            mocks["is_venv_activated"].return_value = False
            mocks["is_baremetal_activated"].return_value = False

            result = self.runner.invoke(activate, ["--build"])

        self.assertEqual(result.exit_code, 2)
        mocks["load_config"].assert_not_called()
        mocks["detect_platform"].assert_not_called()
        mocks["activate_docker"].assert_not_called()
        mocks["activate_venv"].assert_not_called()
        mocks["activate_baremetal"].assert_not_called()

    def test_activate_reports_invalid_mode_strings(self):
        """Surface corrupted mode files as a clear CLI error rather than an accidental default."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "mystery"
            mocks["load_config"].return_value = self._cfg()
            mocks["is_venv_activated"].return_value = False
            mocks["is_baremetal_activated"].return_value = False
            mocks["detect_platform"].return_value = Platform.AMD64

            result = self.runner.invoke(activate, [])

        self.assertEqual(result.exit_code, 1)
        mocks["load_config"].assert_called_once_with(extra_overlays=[])
        mocks["activate_docker"].assert_not_called()
        mocks["activate_venv"].assert_not_called()
        mocks["activate_baremetal"].assert_not_called()

    def test_activate_surfaces_config_validation_errors_as_cli_errors(self):
        """Invalid merged config should produce a normal CLI failure, not an uncaught traceback."""
        with self._common_patches() as mocks:
            mocks["load_environment_mode"].return_value = "docker"
            mocks["is_venv_activated"].return_value = False
            mocks["is_baremetal_activated"].return_value = False
            mocks["detect_platform"].return_value = Platform.AMD64
            mocks["load_config"].side_effect = InvalidConfigError("bad config")

            result = self.runner.invoke(activate, [])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("bad config", result.output)
        mocks["activate_docker"].assert_not_called()
        mocks["activate_venv"].assert_not_called()
        mocks["activate_baremetal"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
