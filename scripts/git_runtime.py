#!/usr/bin/env python3
"""Shared helpers for the git scripts.

The client copies this file to mcp-scripts/git_runtime.py next to the script
that imports it. The MCP server does not execute it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


class WorkflowLog:
    def __init__(self) -> None:
        self.path: Path | None = None
        self.step = "start"

    def open(self, requested: str, *, announce: bool = True) -> None:
        self.path = Path(requested).expanduser().resolve(strict=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")
        if announce:
            self.emit(f"LOGFILE={self.path}")

    def emit(self, line: str) -> None:
        print(line, flush=True)
        self._write(line + "\n")

    def fail(self, code: int) -> None:
        lines = [
            "STATUS=failed",
            f"EXIT_CODE={code}",
            f"FAILED_STEP={self.step}",
        ]
        if self.path is not None:
            lines.append(f"LOGFILE={self.path}")
        text = "\n".join(lines)
        print(text, file=sys.stderr, flush=True)
        self._write(text + "\n")
        raise SystemExit(code)

    def _write(self, text: str) -> None:
        if self.path is None:
            return
        try:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
        except FileNotFoundError:
            return


def redact_url(url: str) -> str:
    return re.sub(r"(://)[^/@]*@", r"\1", url)


def run_git(log: WorkflowLog, args: list[str]) -> None:
    log.emit("+ git " + " ".join(args))
    completed = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_MERGE_AUTOEDIT": "no"},
    )
    output = completed.stdout + completed.stderr
    if output:
        if not output.endswith("\n"):
            output += "\n"
        sys.stdout.write(output)
        sys.stdout.flush()
        if log.path is not None:
            with log.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(output)
    if completed.returncode != 0:
        log.fail(completed.returncode)


def require_git(log: WorkflowLog) -> None:
    if shutil.which("git") is None:
        log.emit("git is not on PATH")
        log.fail(127)


def is_filesystem_root(destination: str) -> bool:
    path = Path(destination).expanduser().resolve(strict=False)
    return path == Path(path.anchor)


def ensure_worktree(log: WorkflowLog, repository_text: str) -> Path:
    if not repository_text or repository_text.startswith("-") or is_filesystem_root(repository_text):
        log.emit("repository is empty, a filesystem root, or looks like an option")
        log.fail(2)
    repository = Path(repository_text)
    if not repository.is_dir():
        log.emit(f"repository is not a directory: {repository_text}")
        log.fail(2)
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or completed.stdout.strip() != "true":
        log.emit(f"repository is not a git worktree: {repository_text}")
        log.fail(2)
    return repository


def read_head(log: WorkflowLog, repository: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        if detail:
            log.emit(detail)
        log.fail(completed.returncode or 1)
    return completed.stdout.strip()


_FEATURE_BRANCH = re.compile(
    r"\Afeature/[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*-[a-z0-9]+(?:-[a-z0-9]+)*\Z"
)


def is_feature_branch(branch: str) -> bool:
    return _FEATURE_BRANCH.fullmatch(branch) is not None


def make_feature_branch(log: WorkflowLog, ticket: str, short_name: str) -> str:
    log.step = "validate-ticket"
    if not re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", ticket):
        log.emit("ticket must be a ticket number such as 123 or NRG-123")
        log.fail(2)
    log.step = "validate-feature-name"
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", short_name):
        log.emit("short feature name must be lowercase words separated by hyphens, such as add-login")
        log.fail(2)
    return f"feature/{ticket}-{short_name}"


def checked_out_branch(repository: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), "symbolic-ref", "--quiet", "--short", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )


def require_identity(log: WorkflowLog, repository: Path) -> None:
    for key in ("user.name", "user.email"):
        completed = subprocess.run(
            ["git", "-C", str(repository), "config", "--get", key],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            log.emit(f"{key} is not set")
            log.fail(2)


def git_text(repository: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def remote_default_branch(repository: Path, remote: str = "origin") -> str:
    symbolic = git_text(repository, ["symbolic-ref", "--quiet", f"refs/remotes/{remote}/HEAD"])
    prefix = f"refs/remotes/{remote}/"
    name = symbolic.stdout.strip()
    if symbolic.returncode != 0 or not name.startswith(prefix):
        return ""
    return f"{remote}/{name.removeprefix(prefix)}"


def operation_in_progress(repository: Path) -> str | None:
    for marker in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"):
        completed = git_text(repository, ["rev-parse", "--git-path", marker])
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip())
        path = Path(completed.stdout.strip())
        if not path.is_absolute():
            path = repository / path
        if path.exists():
            return marker
    return None


def require_clean(log: WorkflowLog, repository: Path) -> None:
    log.step = "validate-operation"
    if operation_in_progress(repository):
        log.emit("a git operation is already in progress")
        log.fail(2)
    log.step = "validate-clean"
    status = git_text(repository, ["status", "--porcelain"])
    if status.returncode or status.stdout:
        log.emit(status.stderr.strip() or "worktree has uncommitted changes")
        log.fail(2)


def locate_git_path(repository: Path, name: str) -> Path | None:
    completed = git_text(repository, ["rev-parse", "--git-path", name])
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    path = Path(completed.stdout.strip())
    if not path.is_absolute():
        path = repository / path
    return path


def exclude_workflow_logs(repository: Path) -> bool:
    path = locate_git_path(repository, "info/exclude")
    if path is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = "/workflow-logs/"
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    if entry in existing.splitlines():
        return True
    suffix = "" if existing.endswith("\n") or existing == "" else "\n"
    path.write_text(f"{existing}{suffix}{entry}\n", encoding="utf-8")
    return True


def branch_log_path(repository: Path, action: str, branch: str | None = None) -> Path | None:
    if branch is None:
        symbolic = checked_out_branch(repository)
        if symbolic.returncode != 0 or not symbolic.stdout.strip():
            branch = "detached"
        else:
            branch = symbolic.stdout.strip()
    parts = branch.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None
    checkout = repository.expanduser().resolve(strict=False)
    if not checkout.name or checkout.name in (".", ".."):
        return None
    return checkout / "workflow-logs" / Path(*parts) / f"{action}.log"


def open_branch_log(log: WorkflowLog, repository: Path, action: str, branch: str | None = None) -> None:
    if not exclude_workflow_logs(repository):
        log.emit("could not exclude workflow logs from the checkout")
        log.fail(2)
    path = branch_log_path(repository, action, branch)
    if path is None:
        log.emit("could not resolve the branch log path")
        log.fail(2)
    log.open(str(path))


def move_log_to_branch(log: WorkflowLog, repository: Path, action: str, branch: str) -> None:
    if not exclude_workflow_logs(repository):
        log.emit("could not exclude workflow logs from the checkout")
        log.fail(2)
    path = branch_log_path(repository, action, branch)
    if path is None or log.path is None:
        log.emit("could not resolve the branch log path")
        log.fail(2)
    resolved = path.resolve()
    if log.path.resolve() == resolved:
        log.emit(f"LOGFILE={log.path}")
        return
    resolved.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(log.path, resolved)
    log.path = resolved
    log.emit(f"LOGFILE={log.path}")


def finish_ok(log: WorkflowLog, head_sha: str) -> None:
    log.step = "done"
    log.emit("STATUS=ok")
    log.emit(f"HEAD={head_sha}")
    log.emit(f"LOGFILE={log.path}")
