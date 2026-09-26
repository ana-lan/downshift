"""Read a directory as it was at a git ref (used by `downshift diff`)."""

from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path


class GitError(Exception):
    """A git command failed or the ref/path is not usable."""


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise GitError("git is not installed or not on PATH") from exc


def repo_root(path: Path) -> Path:
    """Top level of the git repository that contains path."""
    start = path if path.is_dir() else path.parent
    if not start.exists():
        raise GitError(f"{path} does not exist")
    proc = _git(start, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        raise GitError(f"{path} is not inside a git repository")
    return Path(proc.stdout.decode().strip()).resolve()


def verify_ref(root: Path, ref: str) -> None:
    proc = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    if proc.returncode != 0:
        raise GitError(f"unknown git ref: {ref}")


def has_path(root: Path, ref: str, rel: Path) -> bool:
    if rel == Path("."):
        return True
    return _git(root, "cat-file", "-e", f"{ref}:{rel.as_posix()}").returncode == 0


def extract_ref(root: Path, ref: str, rel: Path, dest: Path) -> Path | None:
    """Extract rel (relative to the repo root) at ref into dest.

    Returns dest / rel, or None if rel did not exist at ref.
    """
    verify_ref(root, ref)
    if not has_path(root, ref, rel):
        return None
    args = ["archive", "--format=tar", ref]
    if rel != Path("."):
        args += ["--", rel.as_posix()]
    proc = _git(root, *args)
    if proc.returncode != 0:
        raise GitError(f"git archive {ref} failed: {proc.stderr.decode().strip()}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(proc.stdout)) as tar:
        if hasattr(tarfile, "data_filter"):
            tar.extractall(dest, filter="data")
        else:
            tar.extractall(dest)
    return dest / rel
