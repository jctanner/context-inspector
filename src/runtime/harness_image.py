"""Build complete latest CLI packages into a cached derived agent image."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time


def prepare_image(base: str, *, refresh: bool = False) -> str:
    context = Path(__file__).parent / 'harnesses'
    base_id = subprocess.run(['podman', 'image', 'inspect', '--format', '{{.Id}}', base],
                             check=True, capture_output=True, text=True).stdout.strip()
    digest = hashlib.sha256(base_id.encode() + (context / 'Containerfile').read_bytes()).hexdigest()[:20]
    image = f'localhost/context-inspector-harnesses:{digest}'
    if refresh or subprocess.run(['podman', 'image', 'exists', image], check=False).returncode:
        print('Installing latest Claude and Codex packages in the agent image…', file=sys.stderr)
        command = ['podman', 'build', '--build-arg', f'BASE_IMAGE={base}', '--tag', image]
        if refresh:
            command += ['--build-arg', f'HARNESS_REFRESH={time.time_ns()}']
        subprocess.run([*command, str(context)], check=True, stdout=sys.stderr)
    return image


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default=os.environ.get('AGENT_IMAGE', 'localhost/claude-task-runner:latest'))
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    print(prepare_image(args.base, refresh=args.refresh))
