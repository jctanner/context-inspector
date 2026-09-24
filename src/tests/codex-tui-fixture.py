"""Drive the real interactive CLI through a private PTY, with a fixture model."""
import os
import fcntl
import struct
import termios
from pathlib import Path
import pty
import select
import subprocess
import sys
import time

log = Path(os.environ['CODEX_HOME']) / 'mlflow-tracing.log'
before = log.read_bytes() if log.exists() else b''
master, slave = pty.openpty()
fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 140, 0, 0))
child = subprocess.Popen(sys.argv[1:], stdin=slave, stdout=slave, stderr=slave,
                         env={**os.environ, 'TERM': 'xterm-256color'})
os.close(slave)
transcript = bytearray()
exiting = False
try:
    deadline = time.monotonic() + 40
    while child.poll() is None:
        if time.monotonic() > deadline:
            raise RuntimeError('Interactive fixture timed out: ' + transcript.decode(errors='replace')[-2500:])
        if select.select([master], [], [], .1)[0]:
            try:
                chunk = os.read(master, 65536)
            except OSError:
                break
            transcript.extend(chunk)
            if b'\x1b[6n' in chunk:
                os.write(master, b'\x1b[1;1R')
            if b'\x1b[c' in chunk:
                os.write(master, b'\x1b[?1;2c')
        if not exiting and log.exists() and log.read_bytes() != before:
            # Completed export means the turn finished; now exercise native /exit.
            os.write(master, b'/exit')
            time.sleep(.1)
            os.write(master, b'\r')
            exiting = True
    code = child.wait(timeout=5)
    if code or not exiting:
        raise RuntimeError(f'Interactive fixture failed ({code}): ' + transcript.decode(errors='replace')[-2500:])
finally:
    if child.poll() is None:
        child.kill()
        child.wait()
    os.close(master)
