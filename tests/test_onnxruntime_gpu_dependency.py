# Copyright (c) 2026, NVIDIA CORPORATION. All rights reserved.

"""Tests for the GPU-enabled ONNX Runtime in the x86 development image."""

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPO_ROOT / 'docker' / 'Dockerfile.additional_setting'


class TestOnnxRuntimeGpuDependency(unittest.TestCase):
    """Prevent the CPU-only wheel from replacing the CUDA provider."""

    def test_gpu_wheel_is_pinned_and_cpu_wheel_is_absent(self):
        source = DOCKERFILE.read_text(encoding='utf-8')

        self.assertIn('onnxruntime-gpu==1.27.0', source)
        self.assertNotIn('onnxruntime==', source)


if __name__ == '__main__':
    unittest.main()
