import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/runtime"


class StraceTests(unittest.TestCase):
    def test_wiring_and_opt_out(self):
        script = '''
runtime_dir=$1; project_dir=$2; agent_command=$3; agent_image=fixture; mounts=()
podman() { case "$1 $2" in "image inspect") echo fixture-digest;; "image exists") return 0;; *) return 99;; esac; }
source "$runtime_dir/strace-env.sh"
configure_strace
printf '%s\\0' "${mounts[@]}" "${strace_options[@]}" "$agent_image"
'''
        for enabled, command in [("1", "claude"), ("0", "claude"), ("1", "codex"), ("0", "codex"), ("1", "/usr/local/bin/codex"), ("1", "bash")]:
            with self.subTest(enabled=enabled, command=command), tempfile.TemporaryDirectory() as directory:
                result = subprocess.run(["bash", "-euc", script, "test", str(RUNTIME), directory, command],
                    env={**os.environ, "CONTEXT_INSPECTOR_STRACE_ENABLED": enabled}, check=True, capture_output=True, text=True)
                tracing = enabled == "1" and Path(command).name in {"claude", "codex"}
                self.assertEqual("SYS_PTRACE" in result.stdout, tracing)
                self.assertEqual(":/strace:rw,Z" in result.stdout, tracing)
                self.assertEqual((Path(directory) / "container/strace").exists(), tracing)
                self.assertNotIn("unconfined", result.stdout)
                self.assertNotIn("--privileged", result.stdout)
                if tracing:
                    self.assertEqual((Path(directory) / "container/strace").stat().st_mode & 0o777, 0o700)

    def test_symlink_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / "container").mkdir(); (root / "elsewhere").mkdir()
            (root / "container/strace").symlink_to(root / "elsewhere")
            result = subprocess.run(["bash", "-euc", 'runtime_dir=$1; project_dir=$2; agent_command=claude; source "$1/strace-env.sh"; configure_strace',
                                     "test", str(RUNTIME), directory], capture_output=True, text=True,
                                     env={**os.environ, "CONTEXT_INSPECTOR_STRACE_ENABLED": "1"})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not be a symlink", result.stderr)

    def test_wrapper_preserves_bootstrap_and_plugins(self):
        entrypoint = (RUNTIME / "container-entrypoint.sh").read_text()
        self.assertIn('set -- strace -ffttv -A -o /strace/pid "$@"', entrypoint)
        self.assertLess(entrypoint.index("MLFLOW_CLAUDE_TRACING_ENABLED"), entrypoint.index("set -- strace"))
        self.assertIn('--no-new-privs', entrypoint)
        runner = (RUNTIME / "run.sh").read_text()
        self.assertLess(runner.index("configure_mcp_dump"), runner.index("configure_strace"))
        self.assertEqual(runner.count('"${strace_options[@]}"'), 1)
        self.assertIn('"${tracing_args[@]}" "${mcp_dump_args[@]}" "$@"', runner)
        ignore = subprocess.run(["git", "check-ignore", "container/strace/pid.123"], cwd=ROOT, capture_output=True)
        self.assertEqual(ignore.returncode, 0)


@unittest.skipUnless(os.environ.get("CONTEXT_INSPECTOR_TEST_STRACE") == "1", "opt-in isolated strace container")
class StraceContainerTests(unittest.TestCase):
    def test_installed_claude_and_codex_trace_without_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for harness in ("claude", "codex"):
                trace = root / harness
                trace.mkdir(mode=0o700)
                command = ["podman", "run", "--rm", "--network", "none",
                           "--userns=keep-id:uid=1000,gid=1000", "--user", "1000:1000",
                           "--cap-add", "SYS_PTRACE", "--env", "HOME=/tmp", "--env", "CODEX_HOME=/tmp/codex",
                           "--volume", f"{trace}:/strace:rw,Z", "--entrypoint", "bash",
                           os.environ.get("CONTEXT_INSPECTOR_STRACE_TEST_IMAGE", "localhost/context-inspector-strace-test:089"),
                           "-c", 'umask 077; strace -ffttv -A -o /strace/pid /usr/local/bin/"$1" --version',
                           "fixture", harness]
                result = subprocess.run(command, capture_output=True, text=True, timeout=45)
                self.assertEqual(result.returncode, 0, result.stderr)
                files = list(trace.glob("pid.*"))
                self.assertTrue(files)
                self.assertTrue(all(file.stat().st_mode & 0o777 == 0o600 for file in files))
                self.assertIn(f'/usr/local/bin/{harness}', "\n".join(file.read_text() for file in files))

    def test_nonroot_child_tracing_io_exit_and_append(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); trace = root / "trace"; trace.mkdir(mode=0o700)
            fixture = root / "claude"
            fixture.write_text('#!/bin/sh\nid -u\nread answer\nprintf "received:%s\\n" "$answer"\ncat /fixture/input.txt\nexit 7\n')
            fixture.chmod(0o755)
            (root / "input.txt").write_text("synthetic file read\n")
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                            "-subj", "/CN=strace-fixture", "-keyout", str(root / "key.pem"), "-out", str(root / "ca.pem")],
                           check=True, capture_output=True)
            command = ["podman", "run", "--rm", "--interactive", "--network", "none", "--userns=keep-id:uid=1000,gid=1000",
                       "--user", "0", "--cap-add", "SYS_PTRACE", "--env", "CONTEXT_INSPECTOR_STRACE_ENABLED=1",
                       "--volume", f"{trace}:/strace:rw,Z", "--volume", f"{root}:/fixture:ro,Z",
                       "--volume", f"{root / 'ca.pem'}:/mitmproxy-ca-cert.pem:ro,Z",
                       "--volume", f"{RUNTIME / 'container-entrypoint.sh'}:/entrypoint.sh:ro,Z",
                       "--entrypoint", "bash", os.environ.get("CONTEXT_INSPECTOR_STRACE_TEST_IMAGE", "localhost/context-inspector-strace-test:077"),
                       "/entrypoint.sh", "/fixture/claude"]
            for iteration in range(2):
                result = subprocess.run(command, input="hello\n", text=True, capture_output=True, timeout=45)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertIn("1000\nreceived:hello\nsynthetic file read", result.stdout)
                files = sorted(trace.glob("pid.*"))
                self.assertGreaterEqual(len(files), 2)
                content = "\n".join(file.read_text() for file in files)
                self.assertIn('/fixture/input.txt', content)
                self.assertIn('execve("/fixture/claude"', content)
                self.assertRegex(content, r"\d\d:\d\d:\d\d\.\d{6} ")
                self.assertTrue(all(file.stat().st_mode & 0o777 == 0o600 for file in files))
                if iteration == 0:
                    prior = {file.name: file.read_bytes() for file in files}
                else:
                    self.assertTrue(all((trace / name).read_bytes().startswith(data) for name, data in prior.items()))
            # Exercise the native Claude executable without credentials or a model call.
            version = subprocess.run([*command[:-1], "claude", "--version"], text=True, capture_output=True, timeout=45)
            self.assertEqual(version.returncode, 0, version.stderr)
            self.assertIn("Claude Code", version.stdout)
