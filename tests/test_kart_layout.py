import os
from pathlib import Path
import shlex
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest import mock
from tests.test_run_dev_lifecycle import _import_run_dev, _silence_stdio


class TestKartLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _import_run_dev()

    def test_project_mounted_once_with_matching_environment_and_workdir(self):
        with TemporaryDirectory(prefix='kart space ') as temp:
            root = Path(temp).resolve()
            ws = root / 'ros2_ws'
            ws.mkdir()
            (root / 'packages.repos').write_text('repositories: {}\n')
            args = SimpleNamespace(platform='x86_64', isaac_ros_platform='amd64', verbose=False)
            with mock.patch.object(self.mod, 'load_docker_args_from_file', return_value=[]), \
                 mock.patch.object(self.mod, 'get_existing_bash_configs', return_value=[]), \
                 mock.patch.object(self.mod.subprocess, 'run') as run, _silence_stdio():
                self.mod.run_docker_container(args, 'kart_dev', 'image:test', str(ws))
            command = shlex.split(run.call_args.args[0])
            mounts = [command[i+1] for i, arg in enumerate(command) if arg == '-v']
            self.assertEqual([m for m in mounts if ':/workspaces' in m], [f'{root}:/workspaces'])
            self.assertEqual(command[command.index('--workdir')+1], '/workspaces/ros2_ws')
            self.assertIn('ISAAC_ROS_WS=/workspaces/ros2_ws', command)
            self.assertIn('ISAAC_DIR=/workspaces/ros2_ws', command)
            self.assertNotIn('/workspaces/isaac_ros-dev', run.call_args.args[0])

    def test_invalid_workspace_fails_before_docker(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            ws = root / 'ros2_ws'
            ws.mkdir()
            with self.assertRaises(ValueError):
                self.mod.get_workspace_mount_args(str(ws))
            (root / 'packages.repos').touch()
            wrong = root / 'other'
            wrong.mkdir()
            with self.assertRaises(ValueError):
                self.mod.get_workspace_mount_args(str(wrong))

    def test_host_shell_profiles_not_inherited(self):
        with mock.patch.object(self.mod.os.path, 'isfile', return_value=True):
            self.assertEqual(self.mod.get_existing_bash_configs(), ['.dircolors'])

    def test_dockerargs_accept_comments_and_blank_lines(self):
        with TemporaryDirectory() as temp:
            args_file = Path(temp) / 'args'
            args_file.write_text('# extra mounts\n\n-e KART_TEST=1\n')
            with mock.patch.dict(os.environ, {'DOCKER_ARGS_FILE':str(args_file), 'HOME':temp}, clear=True), \
                 mock.patch.object(self.mod.os.path, 'isfile', side_effect=lambda p: str(p)==str(args_file)), \
                 _silence_stdio():
                self.assertEqual(self.mod.load_docker_args_from_file(), ['-e KART_TEST=1'])
