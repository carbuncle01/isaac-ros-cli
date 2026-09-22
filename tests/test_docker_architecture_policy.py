"""Check selected Docker stage ancestry without Docker or third-party packages."""

from pathlib import Path
import re
import shlex
import subprocess
import unittest

DOCKER = Path(__file__).resolve().parents[1] / 'docker'


def instructions(path):
    source = re.sub(r'\\\n', ' ', path.read_text())
    return [line.strip() for line in source.splitlines()
            if line.strip() and not line.lstrip().startswith('#')]


def selected_runtime(path, architecture):
    """Expand only FROM ancestors, excluding disposable COPY-from builders."""
    stages = {}
    current = None
    for line in instructions(path):
        if line.startswith('FROM '):
            fields = line.replace('${PLATFORM}', architecture).split()
            current = fields[-1]
            stages[current] = (fields[1], [])
        elif current:
            stages[current][1].append(line)
    result = []
    while current in stages:
        parent, body = stages[current]
        result.extend(body)
        current = parent
    return '\n'.join(result)


class TestDockerArchitecturePolicy(unittest.TestCase):
    def test_jetson_has_no_training_calibration_gui_or_packaging_tools(self):
        source = selected_runtime(DOCKER / 'Dockerfile.additional_setting', 'arm64')
        for forbidden in ('/opt/env', 'requirements-training',
                          'multi_sensor_calibration_env', 'terminator',
                          'cartographer-rviz', 'rqt-tf-tree', 'python3-bloom',
                          'devscripts', 'ros-jazzy-isaac-mapping-ros',
                          'ros-jazzy-isaac-ros-visual-mapping'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn('ros-jazzy-isaac-ros-jetson-stats', source)
        self.assertIn('ros-jazzy-isaac-ros-visual-slam', source)
        self.assertIn('ros-jazzy-foxglove-bridge', source)

    def test_x86_keeps_offline_environments_and_excludes_jtop(self):
        source = selected_runtime(DOCKER / 'Dockerfile.additional_setting', 'amd64')
        for required in ('/opt/env', 'multi_sensor_calibration_env',
                         'ros-jazzy-isaac-ros-visual-mapping'):
            self.assertIn(required, source)
        self.assertNotIn('jetson-stats', source)
        self.assertNotIn('python3-bloom', source)

    def test_camera_recording_and_reconstruction_are_separated(self):
        path = DOCKER / 'Dockerfile.silky_evcam'
        arm = selected_runtime(path, 'arm64')
        x86 = selected_runtime(path, 'amd64')
        self.assertNotIn('uv pip install', arm)
        self.assertNotIn('/opt/event_camera_env', arm)
        self.assertIn('ros-jazzy-event-camera-py', arm)
        self.assertIn('cmake --install', arm)
        self.assertIn('"torch==${E2V_TORCH_VERSION}"', x86)
        self.assertIn('/opt/event_camera_env', x86)

    def test_local_copy_inputs_resolve_from_cli_docker_context(self):
        for name in ('additional_setting', 'silky_evcam'):
            for line in instructions(DOCKER / f'Dockerfile.{name}'):
                if not line.startswith('COPY ') or '--from=' in line:
                    continue
                for source in shlex.split(line)[1:-1]:
                    with self.subTest(source=source):
                        self.assertTrue(list(DOCKER.glob(source)))

    def test_run_commands_have_valid_bash_syntax(self):
        for name in ('additional_setting', 'silky_evcam'):
            for line in instructions(DOCKER / f'Dockerfile.{name}'):
                if not line.startswith('RUN '):
                    continue
                command = re.sub(r'^(?:--mount=\S+\s+)+', '', line[4:])
                with self.subTest(dockerfile=name, command=command[:75]):
                    result = subprocess.run(['bash', '-n'], input=command,
                                            text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
