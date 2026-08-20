#!/usr/bin/env python3
# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

"""Validate Isaac ROS CLI apt preference activation and resolver behavior."""

from __future__ import annotations

import argparse
import filecmp
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlparse


ISAAC_DEBIAN_REPOSITORY = "http://isaac-debian-repo.nvidia.com:8080"
ISAAC_DEBIAN_COMPONENTS = "main external-main"
ISAAC_DEBIAN_ORIGIN = "isaac-debian-repo.nvidia.com"
JETSON_ORIGIN = "repo.download.nvidia.com"
JETSON_RELEASE = "r39.2"
CUDA_TOOLKIT = "cuda-toolkit"
CUDA_TOOLKIT_13_3 = "cuda-toolkit-13-3"
TENSORRT_PACKAGES = ("tensorrt", "python3-libnvinfer")
DGX_SPARK_REPO_PACKAGES = ("vpi4-dev", "libnvvpi4", "deepstream-spark")
DGX_SPARK_PREF = "/etc/apt/preferences.d/20-isaac-ros-dgx-spark.pref"
JETSON_PREF = "/etc/apt/preferences.d/20-isaac-ros-jetson.pref"
LEGACY_DGX_SPARK_PREF = "/etc/apt/preferences.d/isaac-ros-dgx-spark.pref"
PACKAGED_DGX_SPARK_PREF = (
    "/etc/isaac-ros-cli/docker/packaging/20-isaac-ros-dgx-spark.pref"
)
PACKAGED_JETSON_PREF = "/etc/isaac-ros-cli/docker/packaging/20-isaac-ros-jetson.pref"

ARCH_REPOS = {
    "amd64": {
        "ubuntu_mirror_env": "UBUNTU_MIRROR_AMD64",
        "ubuntu_mirror": "http://archive.ubuntu.com/ubuntu",
        "security_mirror_env": "UBUNTU_SECURITY_MIRROR_AMD64",
        "security_mirror": "http://security.ubuntu.com/ubuntu",
        "cuda_repo_arch": "x86_64",
    },
    "arm64": {
        "ubuntu_mirror_env": "UBUNTU_MIRROR_ARM64",
        "ubuntu_mirror": "http://ports.ubuntu.com/ubuntu-ports",
        "security_mirror_env": "UBUNTU_SECURITY_MIRROR_ARM64",
        "security_mirror": "http://ports.ubuntu.com/ubuntu-ports",
        "cuda_repo_arch": "sbsa",
    },
}

PLATFORM_CONFIG = {
    "amd64": {
        "target_arch": "amd64",
        "debian_dist": "noble",
        "cuda_prefix": "13.2.",
    },
    "arm64-fastos": {
        "target_arch": "arm64",
        "debian_dist": "noble-fastos",
        "cuda_prefix": "13.0.",
        "active_pref": (PACKAGED_DGX_SPARK_PREF, DGX_SPARK_PREF),
        "origin_uri_packages": DGX_SPARK_REPO_PACKAGES,
        "required_origin": ISAAC_DEBIAN_ORIGIN,
    },
    "arm64-jetpack": {
        "target_arch": "arm64",
        "debian_dist": "noble-jetpack",
        "cuda_prefix": "13.2.",
        "active_pref": (PACKAGED_JETSON_PREF, JETSON_PREF),
        "jetson_repo_paths": ("common",),
        "package_version_prefixes": {
            package: "10.16." for package in TENSORRT_PACKAGES
        },
        "origin_uri_packages": (CUDA_TOOLKIT, *TENSORRT_PACKAGES),
        "required_origin": JETSON_ORIGIN,
    },
}

DEB_SEARCH_DIRS = (
    Path("scripts"),
    Path("bazel-bin/scripts/isaac-ros-cli/isaac_ros_cli_deb"),
)

PREF_CLEANUP_PATTERNS = (
    DGX_SPARK_PREF,
    f"{DGX_SPARK_PREF}.dpkg-*",
    JETSON_PREF,
    f"{JETSON_PREF}.dpkg-*",
    LEGACY_DGX_SPARK_PREF,
    f"{LEGACY_DGX_SPARK_PREF}.dpkg-*",
)


def log(message: str) -> None:
    print(f"==> {message}", flush=True)


def command_to_string(command: list[str]) -> str:
    return shlex.join(command)


def run_command(
    command: list[str],
    *,
    label: str,
    env: dict[str, str] | None = None,
    stdout: int | None = None,
    stderr: int | None = None,
    capture_output: bool = False,
) -> str:
    if capture_output:
        stdout = subprocess.PIPE
        stderr = subprocess.STDOUT

    result = subprocess.run(
        command,
        env=env,
        stdout=stdout,
        stderr=stderr,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        captured_stdout = result.stdout if isinstance(result.stdout, str) else ""
        captured_stderr = result.stderr if isinstance(result.stderr, str) else ""
        if captured_stdout:
            print(captured_stdout, file=sys.stderr, end="")
        if captured_stderr:
            print(captured_stderr, file=sys.stderr, end="")
        raise AssertionError(
            f"{label} failed with exit code {result.returncode}: "
            f"{command_to_string(command)}"
        )
    return result.stdout if isinstance(result.stdout, str) else ""


def remove_matching_paths(pattern: str) -> None:
    path = Path(pattern)
    if "*" in path.name:
        paths = path.parent.glob(path.name)
    else:
        paths = (path,)

    for matched_path in paths:
        if matched_path.exists() or matched_path.is_symlink():
            matched_path.unlink()


def tail_text(path: Path, line_count: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return ""
    return "\n".join(lines[-line_count:]) + "\n"


def candidate_for(policy: str) -> str:
    for line in policy.splitlines():
        if line.startswith("  Candidate: "):
            return line.removeprefix("  Candidate: ")
    raise AssertionError("apt policy output did not include a Candidate line")


def find_isaac_ros_cli_deb() -> Path:
    explicit_deb = os.environ.get("ISAAC_ROS_CLI_DEB")
    if explicit_deb:
        deb_path = Path(explicit_deb)
        if not deb_path.is_file():
            raise AssertionError(f"ISAAC_ROS_CLI_DEB does not exist: {deb_path}")
        return deb_path.resolve()

    candidates: list[Path] = []
    for search_dir in DEB_SEARCH_DIRS:
        if not search_dir.is_dir():
            continue
        candidates.extend(sorted(search_dir.glob("isaac-ros-cli_*.deb")))

    if len(candidates) != 1:
        print("Found deb candidates:", file=sys.stderr)
        if candidates:
            for candidate in candidates:
                print(f"  {candidate}", file=sys.stderr)
        else:
            print("  <none>", file=sys.stderr)
        raise AssertionError(
            "expected exactly one isaac-ros-cli deb; "
            "set ISAAC_ROS_CLI_DEB to choose explicitly"
        )

    return candidates[0].resolve()


class AptResolverHarness:
    def __init__(self, platform: str) -> None:
        self.platform = platform
        self.target_arch = PLATFORM_CONFIG[platform]["target_arch"]
        self.apt_root_context: tempfile.TemporaryDirectory[str] | None = None
        self.apt_root: Path | None = None
        self.apt_options: list[str] = []

    def cleanup(self) -> None:
        if self.apt_root_context is not None:
            self.apt_root_context.cleanup()
            self.apt_root_context = None
            self.apt_root = None

    def apt_get_command(self, *args: str) -> list[str]:
        return ["apt-get", *self.apt_options, *args]

    def apt_cache_command(self, *args: str) -> list[str]:
        return ["apt-cache", *self.apt_options, *args]

    def apt_policy(self, package: str) -> str:
        return run_command(
            self.apt_cache_command("policy", package),
            label=f"apt-cache policy {package}",
            capture_output=True,
        )

    def apt_sim_install(self, package: str) -> str:
        return run_command(
            self.apt_get_command("-s", "--no-install-recommends", "install", package),
            label=f"apt-get simulated install {package}",
            capture_output=True,
        )

    def apt_print_uris(self, package: str) -> str:
        return run_command(
            self.apt_get_command(
                "--print-uris",
                "--download-only",
                "--no-install-recommends",
                "install",
                package,
            ),
            label=f"apt-get print URIs {package}",
            capture_output=True,
        )

    def configure_apt_resolver(self) -> None:
        self.apt_root_context = tempfile.TemporaryDirectory(prefix="isaac-ros-cli-apt-")
        self.apt_root = Path(self.apt_root_context.name)

        (self.apt_root / "etc/apt/sources.list.d").mkdir(parents=True)
        (self.apt_root / "state/lists/partial").mkdir(parents=True)
        (self.apt_root / "cache/archives/partial").mkdir(parents=True)
        (self.apt_root / "status").write_text("", encoding="utf-8")

        isaac_debian_repository = os.environ.get(
            "ISAAC_DEBIAN_REPOSITORY",
            ISAAC_DEBIAN_REPOSITORY,
        )
        isaac_debian_components = os.environ.get(
            "ISAAC_DEBIAN_COMPONENTS",
            ISAAC_DEBIAN_COMPONENTS,
        )
        jetson_release = os.environ.get("JETSON_RELEASE", JETSON_RELEASE)

        arch_config = ARCH_REPOS.get(self.target_arch)
        platform_config = PLATFORM_CONFIG.get(self.platform)
        if arch_config is None:
            raise AssertionError(f"unsupported target architecture: {self.target_arch}")
        if platform_config is None:
            raise AssertionError(f"unsupported platform: {self.platform}")

        ubuntu_mirror = os.environ.get(
            arch_config["ubuntu_mirror_env"],
            arch_config["ubuntu_mirror"],
        )
        ubuntu_security_mirror = os.environ.get(
            arch_config["security_mirror_env"],
            arch_config["security_mirror"],
        )
        debian_dist = platform_config["debian_dist"]
        cuda_repo_arch = arch_config["cuda_repo_arch"]

        sources = [
            (
                f"deb [arch={self.target_arch} trusted=yes] "
                f"{ubuntu_mirror} noble main restricted universe multiverse"
            ),
            (
                f"deb [arch={self.target_arch} trusted=yes] "
                f"{ubuntu_mirror} noble-updates main restricted universe multiverse"
            ),
            (
                f"deb [arch={self.target_arch} trusted=yes] "
                f"{ubuntu_security_mirror} noble-security main restricted universe multiverse"
            ),
            (
                f"deb [arch={self.target_arch} trusted=yes] "
                f"https://developer.download.nvidia.com/compute/cuda/repos/"
                f"ubuntu2404/{cuda_repo_arch} /"
            ),
            (
                f"deb [arch={self.target_arch} trusted=yes] "
                f"{isaac_debian_repository} {debian_dist} {isaac_debian_components}"
            ),
        ]
        for jetson_repo_path in platform_config.get("jetson_repo_paths", ()):
            sources.append(
                (
                    f"deb [arch={self.target_arch} trusted=yes] "
                    f"http://{JETSON_ORIGIN}/jetson/{jetson_repo_path} "
                    f"{jetson_release} main"
                )
            )

        sources_list = self.apt_root / "etc/apt/sources.list"
        sources_list.write_text("\n".join(sources) + "\n", encoding="utf-8")

        self.apt_options = [
            "-o",
            f"APT::Architecture={self.target_arch}",
            "-o",
            f"Dir::Etc::sourcelist={sources_list}",
            "-o",
            f"Dir::Etc::sourceparts={self.apt_root}/etc/apt/sources.list.d",
            "-o",
            "Dir::Etc::preferencesparts=/etc/apt/preferences.d",
            "-o",
            f"Dir::State::status={self.apt_root}/status",
            "-o",
            f"Dir::State::lists={self.apt_root}/state/lists",
            "-o",
            f"Dir::Cache::archives={self.apt_root}/cache/archives",
            "-o",
            f"Dir::Cache::pkgcache={self.apt_root}/cache/pkgcache.bin",
            "-o",
            f"Dir::Cache::srcpkgcache={self.apt_root}/cache/srcpkgcache.bin",
            "-o",
            "Acquire::AllowInsecureRepositories=true",
            "-o",
            "Acquire::AllowDowngradeToInsecureRepositories=true",
            "-o",
            "Debug::NoLocking=1",
        ]

        log(f"apt resolver sources for {self.platform}/{self.target_arch}:")
        for source in sources:
            print(f"  {source}")

        update_log = self.apt_root / "update.log"
        with update_log.open("w", encoding="utf-8") as update_output:
            result = subprocess.run(
                self.apt_get_command("update"),
                stdout=update_output,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if result.returncode != 0:
            print(tail_text(update_log, 120), file=sys.stderr, end="")
            raise AssertionError(
                f"apt-get update failed for {self.platform}/{self.target_arch}"
            )


class IsaacRosCliPlatformTest(unittest.TestCase):
    platform = ""
    apt_harness: AptResolverHarness | None = None

    @classmethod
    def setUpClass(cls) -> None:
        if not cls.platform:
            raise RuntimeError("test platform was not configured")
        if os.geteuid() != 0:
            raise RuntimeError("run inside a root CI/container environment")

        os.environ["DEBIAN_FRONTEND"] = "noninteractive"
        install_deb(cls.platform)
        cls.apt_harness = AptResolverHarness(cls.platform)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.apt_harness is not None:
            cls.apt_harness.cleanup()
            cls.apt_harness = None

    @property
    def apt(self) -> AptResolverHarness:
        if self.__class__.apt_harness is None:
            self.fail("apt resolver harness was not initialized")
        return self.__class__.apt_harness

    def assert_candidate_prefix(self, package: str, prefix: str) -> None:
        policy = self.apt.apt_policy(package)
        candidate = candidate_for(policy)
        self.assertTrue(
            candidate.startswith(prefix),
            f"{package} candidate '{candidate}' does not start with '{prefix}'\n{policy}",
        )

    def assert_no_candidate(self, package: str) -> None:
        policy = self.apt.apt_policy(package)
        candidate = candidate_for(policy)
        self.assertEqual(
            candidate,
            "(none)",
            f"{package} unexpectedly has candidate '{candidate}'\n{policy}",
        )

    def assert_package_origin(self, package: str, expected_origin: str) -> None:
        print_uris = self.apt.apt_print_uris(package)
        package_uris = []
        for line in print_uris.splitlines():
            fields = shlex.split(line)
            if len(fields) >= 2 and fields[1].startswith(f"{package}_"):
                package_uris.append(fields[0])

        self.assertTrue(
            package_uris,
            f"apt-get did not print a URI for {package}\n{print_uris}",
        )
        for uri in package_uris:
            self.assertEqual(
                urlparse(uri).hostname,
                expected_origin,
                f"{package} would be downloaded from {uri}",
            )

    def assert_file_absent(self, path: str) -> None:
        self.assertFalse(Path(path).exists(), f"unexpected file exists: {path}")

    def assert_file_matches_source(
        self,
        source: str,
        destination: str,
    ) -> None:
        source_path = Path(source)
        destination_path = Path(destination)
        self.assertTrue(source_path.is_file(), f"missing source file: {source}")
        self.assertTrue(
            destination_path.is_file(),
            f"missing destination file: {destination}",
        )
        self.assertTrue(
            filecmp.cmp(source_path, destination_path, shallow=False),
            f"{destination} differs from {source}",
        )

    def test_active_platform_preference_files(self) -> None:
        active_pref = PLATFORM_CONFIG[self.platform].get("active_pref")
        if active_pref is not None:
            self.assert_file_matches_source(*active_pref)

        active_pref_destination = active_pref[1] if active_pref is not None else None
        for pref in (DGX_SPARK_PREF, JETSON_PREF):
            if pref != active_pref_destination:
                self.assert_file_absent(pref)
        self.assert_file_absent(LEGACY_DGX_SPARK_PREF)

    def test_apt_policy_resolves_expected_packages(self) -> None:
        self.apt.configure_apt_resolver()

        platform_config = PLATFORM_CONFIG[self.platform]
        cuda_prefix = platform_config["cuda_prefix"]
        cuda_toolkit_install = self.apt.apt_sim_install(CUDA_TOOLKIT)
        self.assert_candidate_prefix(CUDA_TOOLKIT, cuda_prefix)
        self.assert_no_candidate(CUDA_TOOLKIT_13_3)
        self.assertIn(f"Inst {CUDA_TOOLKIT} ({cuda_prefix}", cuda_toolkit_install)

        for package, prefix in platform_config.get(
            "package_version_prefixes", {}
        ).items():
            self.assert_candidate_prefix(package, prefix)
            self.apt.apt_sim_install(package)

        required_origin = platform_config.get("required_origin")
        for package in platform_config.get("origin_uri_packages", ()):
            self.assert_package_origin(package, required_origin)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Install a built isaac-ros-cli Debian package, verify activated apt "
            "preference files, and validate resolver behavior for a target platform."
        )
    )
    parser.add_argument(
        "platform",
        nargs="?",
        help="Target platform: amd64, arm64-fastos, or arm64-jetpack.",
    )
    return parser.parse_args()


def resolve_platform(argument_platform: str | None) -> str:
    platform = (
        argument_platform
        or os.environ.get("ISAAC_ROS_PLATFORM_UNDER_TEST")
        or os.environ.get("ISAAC_ROS_PLATFORM")
        or ""
    )
    if not platform:
        raise ValueError(
            "usage: isaac_ros_cli_platforms.py <amd64|arm64-fastos|arm64-jetpack>"
        )
    if platform not in PLATFORM_CONFIG:
        raise ValueError(f"unsupported platform: {platform}")
    return platform


def install_deb(platform: str) -> None:
    deb_path = find_isaac_ros_cli_deb()
    log(f"Installing {deb_path} with ISAAC_ROS_PLATFORM={platform}")

    for pattern in PREF_CLEANUP_PATTERNS:
        remove_matching_paths(pattern)

    run_command(
        ["apt-get", "update"],
        label="apt-get update",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    run_command(
        ["apt-get", "install", "-y", "--no-install-recommends", "adduser"],
        label="apt-get install adduser",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    env = os.environ.copy()
    env["ISAAC_ROS_PLATFORM"] = platform
    run_command(
        [
            "apt-get",
            "install",
            "-y",
            "--allow-downgrades",
            "--no-install-recommends",
            str(deb_path),
        ],
        label=f"apt-get install {deb_path}",
        env=env,
    )


def main() -> int:
    args = parse_args()
    try:
        platform = resolve_platform(args.platform)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    IsaacRosCliPlatformTest.platform = platform

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(IsaacRosCliPlatformTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
