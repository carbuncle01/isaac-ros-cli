# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.

"""Tests for the pinned and patched jetson-stats Docker dependency."""

from pathlib import Path
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / 'docker' / 'Dockerfile.additional_setting'
PATCH_FILE = REPO_ROOT / 'docker' / 'patches' / 'jetson-stats-7.2.0-library-probe.patch'


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

if __name__ == '__main__':
    unittest.main()
