import unittest
from unittest.mock import Mock, patch
from src.runtime.harness_image import prepare_image


class HarnessImageTests(unittest.TestCase):
    @patch('src.runtime.harness_image.subprocess.run')
    def test_cached_image_does_not_reinstall(self, run):
        run.side_effect = [Mock(stdout='image-id'), Mock(returncode=0)]
        self.assertTrue(prepare_image('base').startswith('localhost/context-inspector-harnesses:'))
        self.assertEqual(run.call_count, 2)

    @patch('src.runtime.harness_image.subprocess.run')
    def test_refresh_invalidates_install_layer(self, run):
        run.return_value = Mock(stdout='image-id', returncode=0)
        prepare_image('base', refresh=True)
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ['podman', 'build'])
        self.assertTrue(any(arg.startswith('HARNESS_REFRESH=') for arg in command))
        self.assertIn('BASE_IMAGE=base', command)

    @patch('src.runtime.harness_image.subprocess.run')
    def test_uncached_image_builds(self, run):
        run.side_effect = [Mock(stdout='image-id'), Mock(returncode=1), Mock(returncode=0)]
        prepare_image('base')
        self.assertEqual(run.call_args.args[0][:2], ['podman', 'build'])
