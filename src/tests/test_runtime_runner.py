from pathlib import Path
import unittest


class RuntimeRunnerTests(unittest.TestCase):
    def test_persists_claude_user_configuration_inside_project_state(self) -> None:
        runner = (Path(__file__).parents[1] / "runtime" / "run.sh").read_text()
        self.assertIn('claude_state_dir="${project_dir}/.state/claude"', runner)
        self.assertNotIn("XDG_STATE_HOME", runner)
        self.assertNotIn("${HOME}/.local/state", runner)
        self.assertNotIn("CONTEXT_INSPECTOR_CLAUDE_STATE_DIR", runner)
        self.assertIn('chmod 700 "${claude_state_dir}" "${claude_config_dir}"', runner)
        self.assertIn('if [[ ! -s ${claude_config_file} ]]', runner)
        self.assertIn("printf '{}\\n'", runner)
        self.assertIn('${claude_config_dir}:/home/runner/.claude:rw,Z', runner)
        self.assertIn('${claude_config_file}:/home/runner/.claude.json:rw,Z', runner)
        self.assertEqual(runner.count("--userns=keep-id:uid=1000,gid=1000"), 2)
        self.assertNotIn("--userns=keep-id ", runner)

    def test_readiness_probes_proxy_socket_not_buffered_log_text(self) -> None:
        runner = (Path(__file__).parents[1] / "runtime" / "run.sh").read_text()
        self.assertIn("if [[ ${proxy_running} != true ]]", runner)
        self.assertIn("socket.create_connection", runner)
        self.assertNotIn("podman logs \"${proxy_name}\" 2>&1 | grep", runner)
        running_check = runner.index("proxy_running=$(podman inspect")
        listening_check = runner.index("socket.create_connection")
        smoke_test = runner.index("--entrypoint curl")
        self.assertLess(running_check, listening_check)
        self.assertLess(listening_check, smoke_test)


if __name__ == "__main__":
    unittest.main()
