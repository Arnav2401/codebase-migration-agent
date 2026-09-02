import subprocess

from pmigrate.corpus.subprocess_utils import subprocess_error_detail


def test_includes_stderr_text_when_present() -> None:
    e = subprocess.CalledProcessError(
        returncode=128, cmd=["git", "log"], output=b"", stderr=b"fatal: bad object\n"
    )
    detail = subprocess_error_detail(e)
    assert "fatal: bad object" in detail


def test_decodes_bytes_stderr() -> None:
    e = subprocess.CalledProcessError(returncode=1, cmd=["docker", "build"], stderr=b"boom")
    assert "boom" in subprocess_error_detail(e)


def test_falls_back_to_str_when_stderr_is_empty() -> None:
    e = subprocess.CalledProcessError(returncode=1, cmd=["docker", "build"], stderr=b"")
    detail = subprocess_error_detail(e)
    assert detail == str(e)


def test_works_on_timeout_expired_too() -> None:
    e = subprocess.TimeoutExpired(cmd=["pytest"], timeout=60, stderr=b"hung waiting on lock")
    assert "hung waiting on lock" in subprocess_error_detail(e)
