from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.server.startup_reset import RESET_ENTRIES, _assert_no_mounted_targets, assert_home_unused, clean_claude_startup


class StartupResetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name)
        self.home = self.project / 'container/home/evaluator/.claude'
        self.home.mkdir(parents=True)
        project = patch('src.server.startup_reset.PROJECT_ROOT', self.project)
        project.start()
        self.addCleanup(project.stop)
        self.output = StringIO()

    def file(self, relative, text='fixture'):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    @patch('src.server.startup_reset.assert_home_unused')
    def test_reset_allowlist_preserves_config_and_does_not_archive(self, unused):
        for entry in RESET_ENTRIES:
            self.file(entry if entry.endswith('.jsonl') else entry + '/fixture.txt')
        self.file('projects/-workspace/memory/MEMORY.md')
        keep = ['settings.json', '.credentials.json', 'CLAUDE.md', 'plugins/plugin.json',
                'skills/example/SKILL.md', 'rules/example.md', 'unknown/state.json']
        for name in keep:
            self.file(name)
        sibling = self.home.parent / '.claude.json'
        sibling.write_text('preserved')
        workspace = self.project / 'container/workspace'
        workspace.mkdir()
        (workspace / 'CLAUDE.md').write_text('preserved')
        with redirect_stdout(self.output), clean_claude_startup():
            self.assertTrue(all(not (self.home / entry).exists() for entry in RESET_ENTRIES))
            self.assertTrue(all((self.home / name).read_text() == 'fixture' for name in keep))
            self.assertEqual(sibling.read_text(), 'preserved')
            self.assertEqual((workspace / 'CLAUDE.md').read_text(), 'preserved')
            self.assertFalse((self.project / 'container/.claude-startup-archives').exists())
        self.assertIn('permanent; no backup', self.output.getvalue())
        self.assertEqual([call.args[0] for call in unused.call_args_list],
                         [self.home, self.project / 'container/strace'])

    @patch('src.server.startup_reset.assert_home_unused')
    def test_strace_reset_all_contents_without_following_links(self, unused):
        trace = self.project / 'container/strace'
        (trace / '.nested').mkdir(parents=True)
        (trace / '.nested/pid.1').write_text('old trace')
        (trace / 'pid.2').write_text('old trace')
        outside = self.file('settings.json', 'preserved')
        (trace / 'link').symlink_to(outside)
        with redirect_stdout(self.output), clean_claude_startup():
            self.assertEqual(list(trace.iterdir()), [])
            self.assertEqual(trace.stat().st_mode & 0o777, 0o700)
            self.assertEqual(outside.read_text(), 'preserved')
            (trace / 'pid.3').write_text('current trace')
            with self.assertRaisesRegex(RuntimeError, 'Another stack'), clean_claude_startup():
                pass
            self.assertTrue((trace / 'pid.3').exists())
        self.assertIn('Strace startup reset', self.output.getvalue())

    @patch('src.server.startup_reset.assert_home_unused')
    def test_strace_guards_run_before_any_cleanup(self, unused):
        trace = self.project / 'container/strace'
        trace.mkdir()
        history = self.file('history.jsonl')
        unused.side_effect = [None, RuntimeError('active trace mount')]
        with self.assertRaisesRegex(RuntimeError, 'active trace'), clean_claude_startup():
            pass
        self.assertTrue(history.exists())
        unused.side_effect = None
        trace.rmdir()
        trace.symlink_to(self.home, target_is_directory=True)
        with self.assertRaises(OSError), clean_claude_startup():
            pass
        self.assertTrue(history.exists())

    def test_strace_mount_guard_rejects_nested_mount(self):
        trace = self.project / 'container/strace'
        with patch('pathlib.Path.read_text', return_value=f'1 2 0:1 / {trace}/nested rw - tmpfs tmpfs rw'):
            with self.assertRaisesRegex(RuntimeError, 'mounted filesystem'):
                _assert_no_mounted_targets(trace, entire_root=True)

    @patch('src.server.startup_reset.assert_home_unused')
    def test_reset_does_not_follow_top_level_or_nested_symlinks(self, unused):
        outside = self.project / 'outside'
        outside.mkdir()
        (outside / 'keep').write_text('untouched')
        (self.home / 'projects').symlink_to(outside, target_is_directory=True)
        (self.home / 'file-history').mkdir()
        (self.home / 'file-history/link').symlink_to(outside, target_is_directory=True)
        with redirect_stdout(self.output), clean_claude_startup():
            self.assertFalse((self.home / 'projects').is_symlink())
            self.assertFalse((self.home / 'file-history').exists())
        self.assertEqual((outside / 'keep').read_text(), 'untouched')

    @patch('src.server.startup_reset.assert_home_unused')
    def test_symlinked_home_is_rejected(self, unused):
        self.home.rmdir()
        outside = self.project / 'outside'
        outside.mkdir()
        (outside / 'history.jsonl').write_text('untouched')
        self.home.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError), clean_claude_startup():
            self.fail('symlinked root accepted')
        self.assertEqual((outside / 'history.jsonl').read_text(), 'untouched')
        unused.assert_not_called()

    @patch('src.server.startup_reset.assert_home_unused')
    def test_stack_lock_prevents_reset_of_new_session(self, unused):
        with redirect_stdout(self.output), clean_claude_startup():
            history = self.file('history.jsonl', 'current session')
            with self.assertRaisesRegex(RuntimeError, 'Another stack'), clean_claude_startup():
                self.fail('concurrent startup accepted')
            self.assertEqual(history.read_text(), 'current session')
        with redirect_stdout(self.output), clean_claude_startup():
            self.assertFalse(history.exists())

    @patch('src.server.startup_reset.assert_home_unused', side_effect=RuntimeError('active container'))
    def test_active_container_failure_prevents_any_deletion(self, unused):
        history = self.file('history.jsonl')
        with self.assertRaisesRegex(RuntimeError, 'active container'), clean_claude_startup():
            self.fail('active home reset')
        self.assertTrue(history.exists())

    @patch('src.server.startup_reset.assert_home_unused')
    @patch('src.server.startup_reset._assert_no_mounted_targets', side_effect=RuntimeError('mounted filesystem'))
    def test_mount_guard_failure_prevents_deletion(self, mounted, unused):
        history = self.file('history.jsonl')
        with self.assertRaisesRegex(RuntimeError, 'mounted filesystem'), clean_claude_startup():
            pass
        self.assertTrue(history.exists())

    def test_mountinfo_rejects_nested_and_home_mounts_but_not_workspace(self):
        for path, reject in [(self.home, True), (self.home.parent, True),
                             (self.home / 'projects/nested mount', True),
                             (self.project / 'container/workspace', False)]:
            encoded = str(path).replace(' ', r'\040')
            with self.subTest(path=path), patch('pathlib.Path.read_text', return_value=f'1 2 0:1 / {encoded} rw - tmpfs tmpfs rw'):
                if reject:
                    with self.assertRaisesRegex(RuntimeError, 'mounted filesystem'):
                        _assert_no_mounted_targets(self.home)
                else:
                    _assert_no_mounted_targets(self.home)

    @patch('src.server.startup_reset.assert_home_unused')
    def test_disabled_reset_does_not_inspect_or_change_home(self, unused):
        history = self.file('history.jsonl')
        with clean_claude_startup(enabled=False):
            pass
        unused.assert_not_called()
        self.assertTrue(history.exists())
        self.assertFalse((self.project / 'container/.claude-startup.lock').exists())

    @patch('src.server.startup_reset.subprocess.run')
    def test_live_mount_guard_checks_overlap_and_paused_containers(self, run):
        for state, source, reject in [('running', self.home, True),
                                     ('paused', self.home.parent, True),
                                     ('running', self.home / 'projects', True),
                                     ('running', self.project / 'container/workspace', False),
                                     ('exited', self.home, False)]:
            with self.subTest(state=state, source=source):
                run.side_effect = [Mock(stdout='abc123\n'),
                                   Mock(stdout=json.dumps(state) + ' ' + json.dumps([{'Source': str(source)}]))]
                if reject:
                    with self.assertRaisesRegex(RuntimeError, 'still uses the home'):
                        assert_home_unused(self.home)
                else:
                    assert_home_unused(self.home)

    @patch('src.server.startup_reset.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'podman'))
    def test_podman_errors_fail_closed(self, run):
        history = self.file('history.jsonl')
        with self.assertRaises(subprocess.CalledProcessError), clean_claude_startup():
            pass
        self.assertTrue(history.exists())


if __name__ == '__main__':
    unittest.main()
