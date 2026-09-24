"""Verify pinned Claude's credential/config separation with synthetic data only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def probe(container_image=None):
    binary = Path(shutil.which('claude') or '/missing-claude').resolve()
    with tempfile.TemporaryDirectory(prefix='ci-claude-storage-') as directory:
        root = Path(directory)
        auth, config = root / 'host-auth', root / 'inspector-config'
        auth.mkdir(mode=0o700)
        config.mkdir(mode=0o700)
        credentials = auth / '.credentials.json'
        credentials.write_text(json.dumps({'claudeAiOauth': {
            'accessToken': 'synthetic-access-token', 'refreshToken': 'synthetic-refresh-token',
            'expiresAt': int(time.time() * 1000) + 3600000,
            'scopes': ['user:inference', 'user:profile'], 'subscriptionType': 'max',
        }}))
        credentials.chmod(0o600)
        before = credentials.read_bytes()
        env = {'PATH': os.environ['PATH'], 'CLAUDE_CONFIG_DIR': str(config),
               'CLAUDE_SECURESTORAGE_CONFIG_DIR': str(auth), 'DISABLE_AUTOUPDATER': '1',
               'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
               'HTTP_PROXY': 'http://127.0.0.1:9', 'HTTPS_PROXY': 'http://127.0.0.1:9',
               'http_proxy': 'http://127.0.0.1:9', 'https_proxy': 'http://127.0.0.1:9'}
        status_args = ['--setting-sources', '', '--strict-mcp-config', 'auth', 'status', '--json']
        command = [str(binary), *status_args]
        process_env = env
        if container_image:
            command = ['podman', 'run', '--rm', '--pull=never', '--network=none',
                       '--userns=keep-id:uid=1000,gid=1000', '--user=1000:1000', '--security-opt=label=disable',
                       '--workdir=/inspector-config', '--volume', f'{binary}:/claude:ro',
                       '--volume', f'{auth}:/host-auth:rw', '--volume', f'{config}:/inspector-config:rw']
            for key, value in {**env, 'CLAUDE_CONFIG_DIR': '/inspector-config',
                               'CLAUDE_SECURESTORAGE_CONFIG_DIR': '/host-auth'}.items():
                if key != 'PATH':
                    command += ['--env', f'{key}={value}']
            command += ['--entrypoint=/claude', container_image, *status_args]
            process_env = None
        result = subprocess.run(command, cwd=config, env=process_env,
                                capture_output=True, text=True, timeout=20)
        try:
            status = json.loads(result.stdout)
        except ValueError:
            status = {}
        return {'synthetic_only': True, 'container_image': container_image, 'exit_code': result.returncode,
                'logged_in': status.get('loggedIn') is True, 'auth_method': status.get('authMethod'),
                'auth_unchanged': credentials.read_bytes() == before,
                'credential_file_copied_to_config': (config / '.credentials.json').exists(),
                'host_auth_extra_files': sorted(p.name for p in auth.iterdir() if p != credentials),
                'limits': ['status only', 'no refresh', 'no model request']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container-image', help='Existing image; synthetic mounts only, no network')
    print(json.dumps(probe(parser.parse_args().container_image), indent=2))
