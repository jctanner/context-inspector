"""Native file-auth preflight. Never return credentials or copy an auth cache."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import stat
import sys
import tomllib


class CredentialError(ValueError):
    """A safe diagnostic: messages must not include credential contents."""


@dataclass(frozen=True)
class SharedAuthFile:
    path: Path
    device: int
    inode: int
    directory: bool = False

    def unchanged_identity(self) -> bool:
        try:
            info = self.path.lstat()
            expected_type = stat.S_ISDIR(info.st_mode) if self.directory else stat.S_ISREG(info.st_mode)
            return expected_type and (info.st_dev, info.st_ino) == (self.device, self.inode)
        except OSError:
            return False


def codex_auth_file(home: Path) -> SharedAuthFile:
    """Admit only the known file backend and native ChatGPT token structure.

    A bind-mounted file follows in-place refresh, but not replacement/logout.
    Callers must monitor its identity and stop rather than use a stale mount.
    """
    home = home.expanduser().resolve()
    try:
        config_path = home / "config.toml"
        config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    except (OSError, ValueError):
        raise CredentialError("Cannot determine Codex credential storage from host configuration") from None
    if config.get("cli_auth_credentials_store", "file") != "file":
        raise CredentialError("This runtime currently supports Codex's file credential store only")
    path = home / "auth.json"
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise CredentialError("Codex auth.json must be an owner-only regular file owned by this user")
            if not 0 < info.st_size <= 1024 * 1024:
                raise CredentialError("Codex auth.json has an invalid size")
            value = json.loads(stream.read(1024 * 1024 + 1))
    except (OSError, ValueError) as error:
        if isinstance(error, CredentialError):
            raise
        raise CredentialError("Cannot read a valid native Codex auth.json; log in with the host CLI") from None
    if not isinstance(value, dict) or value.get("auth_mode") not in (None, "chatgpt") or value.get("OPENAI_API_KEY"):
        raise CredentialError("Codex must be logged in with ChatGPT, not an API key")
    tokens = value.get("tokens")
    if not isinstance(tokens, dict) or any(not isinstance(tokens.get(key), str) or not tokens[key]
                                           for key in ("access_token", "refresh_token", "id_token", "account_id")):
        raise CredentialError("Codex ChatGPT credentials are incomplete; use the host CLI to log in")
    result = SharedAuthFile(path, info.st_dev, info.st_ino)
    if not result.unchanged_identity():
        raise CredentialError("Codex credentials changed during preflight; retry launch")
    return result


def isolated_codex_environment(proxy_url: str) -> dict[str, str]:
    """Explicit container values: do not inherit API keys or Vertex settings."""
    return {
        "CODEX_HOME": "/home/evaluator/.codex",
        "HTTP_PROXY": proxy_url, "HTTPS_PROXY": proxy_url,
        "http_proxy": proxy_url, "https_proxy": proxy_url,
        "NO_PROXY": "localhost,127.0.0.1", "no_proxy": "localhost,127.0.0.1",
        "CODEX_CA_CERTIFICATE": "/mitmproxy-ca-cert.pem",
        "CONTEXT_INSPECTOR_STRACE_ENABLED": "0",
        "MLFLOW_CLAUDE_TRACING_ENABLED": "false",
    }


def codex_command(model: str) -> tuple[str, ...]:
    if not model or any(ord(c) < 32 for c in model) or model.startswith("-"):
        raise ValueError("Invalid Codex model")
    return ("codex", "--no-daemon", "--model", model, "--sandbox", "danger-full-access",
            "--ask-for-approval", "never", "-c", 'cli_auth_credentials_store="file"',
            "-c", 'model_provider="openai"')


def claude_auth_directory(home: Path) -> SharedAuthFile:
    """Pin the directory, not its replaceable native credential file."""
    home = home.expanduser().resolve()
    try:
        info = home.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise CredentialError("Claude credential directory must be owned by this user and not writable by others")
        fd = os.open(home / ".credentials.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
                raise CredentialError("Claude credentials must be an owner-only regular file owned by this user")
            if not 0 < metadata.st_size <= 1024 * 1024:
                raise CredentialError("Claude credential file has an invalid size")
            value = json.loads(stream.read(1024 * 1024 + 1))
    except (OSError, ValueError) as error:
        if isinstance(error, CredentialError):
            raise
        raise CredentialError("Cannot read native Claude credentials; log in with the host CLI") from None
    tokens = value.get("claudeAiOauth") if isinstance(value, dict) else None
    if not isinstance(tokens, dict) or any(not isinstance(tokens.get(key), str) or not tokens[key]
                                          for key in ("accessToken", "refreshToken")):
        raise CredentialError("Claude subscription credentials are incomplete; use the host CLI to log in")
    result = SharedAuthFile(home, info.st_dev, info.st_ino, directory=True)
    if not result.unchanged_identity():
        raise CredentialError("Claude credential directory changed during preflight; retry launch")
    return result


@dataclass(frozen=True)
class NativeLaunch:
    auth: SharedAuthFile


def native_launch(harness: str) -> NativeLaunch:
    """Validate host credentials only; CLI executables live in the image."""
    if harness == "codex":
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        auth = codex_auth_file(home)
    elif harness == "claude":
        selected = (os.environ["CLAUDE_SECURESTORAGE_CONFIG_DIR"] if "CLAUDE_SECURESTORAGE_CONFIG_DIR" in os.environ
                    else os.environ.get("CLAUDE_CONFIG_DIR"))
        auth = claude_auth_directory(Path(selected or str(Path.home() / ".claude")))
    else:
        raise CredentialError("Unsupported OAuth harness")
    if any(c in str(auth.path) for c in ("\n", "\r", ":")):
        raise CredentialError("Native credential paths must not contain mount separators or newlines")
    return NativeLaunch(auth)


def codex_cached_models(home: Path | None = None) -> tuple[str, ...]:
    """Use native model metadata, never guessed provider/model combinations."""
    home = home if home is not None else Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    try:
        path = home / "models_cache.json"
        if path.stat().st_size > 16 * 1024 * 1024:
            return ()
        data = json.loads(path.read_text())
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            return ()
    except (OSError, ValueError):
        return ()
    result = []
    for entry in models:
        if not isinstance(entry, dict) or entry.get("visibility") != "list":
            continue
        slug = entry.get("slug")
        if (isinstance(slug, str) and 0 < len(slug) <= 200 and not slug.startswith("-")
                and all(character.isascii() and (character.isalnum() or character in "._-") for character in slug)
                and slug not in result):
            result.append(slug)
    return tuple(result)


if __name__ == "__main__":
    try:
        launch = native_launch(sys.argv[1] if len(sys.argv) > 1 else "codex")
        print(launch.auth.path)
        print(f"{launch.auth.device}:{launch.auth.inode}")
    except CredentialError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(2)
