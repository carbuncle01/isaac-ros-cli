# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.

"""Tests for the pinned and patched jetson-stats Docker dependency."""

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / 'docker' / 'Dockerfile.additional_setting'
JETPACK_DOCKERFILE = REPO_ROOT / 'docker' / 'Dockerfile.jp72_orin'
PATCH_FILE = REPO_ROOT / 'docker' / 'patches' / 'jetson-stats-7.2.0-library-probe.patch'
APT_PREFERENCES = REPO_ROOT / 'docker' / 'packaging' / 'jetpilot-jp72-orin.pref'


class TestJetsonStatsDependency(unittest.TestCase):
    """Keep the host-service client dependency reproducible."""

    def test_dependency_is_pinned_to_an_immutable_commit(self):
        source = DOCKERFILE.read_text(encoding='utf-8')

        version = re.search(r'^ARG JETSON_STATS_VERSION=([^\s]+)$', source, re.MULTILINE)
        revision = re.search(r'^ARG JETSON_STATS_REF=([0-9a-f]{40})$', source, re.MULTILINE)

        self.assertIsNotNone(version)
        self.assertEqual(version.group(1), '7.2.0')
        self.assertIsNotNone(revision)
        self.assertEqual(revision.group(1), '3c1ba9ac49a1307c9d7c53646bb70ba8c16b8759')
        self.assertNotIn(
            '"git+https://github.com/rbonghi/jetson_stats.git"',
            source,
        )

    def test_library_probe_patch_is_applied(self):
        dockerfile = DOCKERFILE.read_text(encoding='utf-8')
        patch = PATCH_FILE.read_text(encoding='utf-8')

        self.assertIn(PATCH_FILE.name, dockerfile)
        self.assertIn(
            'COPY patches/jetson-stats-7.2.0-library-probe.patch',
            dockerfile,
        )
        self.assertNotIn(
            'COPY docker/patches/jetson-stats-7.2.0-library-probe.patch',
            dockerfile,
        )
        self.assertIn('git -C /tmp/jetson_stats apply', dockerfile)
        self.assertIn('except OSError:', patch)
        self.assertIn("if vpi := load_library('nvvpi'):", patch)

    def test_vpi_l4t_runtime_matches_the_host_release(self):
        source = JETPACK_DOCKERFILE.read_text(encoding='utf-8')
        preferences = APT_PREFERENCES.read_text(encoding='utf-8')

        self.assertIn('ARG L4T_VERSION=39.2.0-20260601141651', source)
        self.assertIn('ARG VPI_VERSION=4.1.3', source)
        self.assertIn('jetson/som r39.2 main', source)
        self.assertIn('"libnvvpi4=${VPI_VERSION}"', source)
        self.assertIn('"nvidia-l4t-multimedia-utils=${L4T_VERSION}"', source)
        self.assertIn('libnvbufsurface_nvsci.so.1.0.0', source)
        self.assertIn('Package: nvidia-l4t-*', preferences)
        self.assertIn('Pin: version 39.2.0-20260601141651', preferences)
        self.assertIn('Package: libnvvpi4 vpi4-*', preferences)
        self.assertIn('Pin: version 4.1.3', preferences)


if __name__ == '__main__':
    unittest.main()
