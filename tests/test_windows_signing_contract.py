from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "packaging" / "desktop" / "tools" / "sign_windows_artifact.py"


spec = importlib.util.spec_from_file_location("sign_windows_artifact", HELPER_PATH)
assert spec and spec.loader
signing = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = signing
spec.loader.exec_module(signing)


def signing_env(tmp_path: Path) -> dict[str, str]:
    certificate = tmp_path / "release-cert.pfx"
    certificate.write_bytes(b"test placeholder; not a real certificate")
    signtool = tmp_path / "signtool.exe"
    signtool.write_bytes(b"test placeholder; not a real executable")
    password = "x" * 32
    return {
        signing.SIGNTOOL_ENV: str(signtool),
        signing.CERTIFICATE_ENV: str(certificate),
        signing.TIMESTAMP_ENV: "https://timestamp.example.test",
        signing.PASSWORD_ENV: password,
    }


@pytest.mark.parametrize(
    "missing,expected",
    [
        (signing.SIGNTOOL_ENV, "signtool"),
        (signing.CERTIFICATE_ENV, "证书路径"),
        (signing.TIMESTAMP_ENV, "时间戳 URL"),
        (signing.PASSWORD_ENV, "PFX 密码"),
    ],
)
def test_explicit_signing_requires_every_input(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    missing: str,
    expected: str,
) -> None:
    env = signing_env(tmp_path)
    env.pop(missing)

    # Hosted Linux runner may happen to expose an unrelated signtool command.
    # This case verifies the configured-input error path, not host autodiscovery.
    if missing == signing.SIGNTOOL_ENV:
        monkeypatch.setattr(signing.shutil, "which", lambda _name: None)
        monkeypatch.setattr(signing, "_find_windows_sdk_signtool", lambda: None)

    with pytest.raises(signing.SigningConfigError, match=expected):
        signing.validate_signing_config(env=env)


def test_signing_command_uses_sha256_and_password_is_redacted(tmp_path: Path) -> None:
    env = signing_env(tmp_path)
    config = signing.validate_signing_config(env=env)
    artifact = tmp_path / "LinRouter.exe"
    artifact.write_bytes(b"test payload")

    command = signing.build_signtool_command(config, artifact)
    rendered = signing.redact_command(command, config.password)

    assert command[1:7] == ["sign", "/fd", "sha256", "/tr", env[signing.TIMESTAMP_ENV], "/td"]
    assert command[7] == "sha256"
    assert "/f" in command
    assert "/p" in command
    assert config.password in command
    assert config.password not in rendered
    assert "<redacted>" in rendered


def test_sign_artifact_redacts_signtool_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = signing_env(tmp_path)
    config = signing.validate_signing_config(env=env)
    artifact = tmp_path / "LinRouter.exe"
    artifact.write_bytes(b"test payload")

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        command = args[0]
        assert config.password in command
        return SimpleNamespace(
            returncode=0,
            stdout=f"signed with {config.password}",
            stderr=f"debug {config.password}",
        )

    monkeypatch.setattr(signing.subprocess, "run", fake_run)
    signing.sign_artifact(artifact, config)
    output = capsys.readouterr()

    assert config.password not in output.out
    assert config.password not in output.err
    assert "<redacted>" in output.out
    assert "<redacted>" in output.err
