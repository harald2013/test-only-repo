#!/usr/bin/env python3
"""Canonical git push script served at git://scripts/git_push.py.

The MCP server does not execute this file. A client copies it into
mcp-scripts/ next to git_runtime.py and runs it with Python 3.

Usage: python3 git_push.py <repository> [remote] [base]
Log:   GIT_PUSH_LOG if set, otherwise <checkout>/workflow-logs/<branch>/push.log

Publishes the feature branch without changing commits or their messages.
With no remote, uses origin. With no base, uses that remote's
default branch. It does not fetch. A published branch is updated with
--force-with-lease against the remote-tracking ref.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from git_runtime import (
    WorkflowLog,
    checked_out_branch,
    ensure_worktree,
    finish_ok,
    git_text,
    is_feature_branch,
    open_branch_log,
    read_head,
    require_git,
    remote_default_branch,
    run_git,
)

log = WorkflowLog()


def tracking_sha(repository: Path, remote: str, branch: str) -> str:
    found = git_text(repository, ["rev-parse", "--verify", "--quiet", f"refs/remotes/{remote}/{branch}"])
    if found.returncode != 0:
        return ""
    return found.stdout.strip()


def push(argv: list[str]) -> None:
    log.step = "parse-arguments"
    if len(argv) < 1 or len(argv) > 3:
        log.open(os.environ.get("GIT_PUSH_LOG", "git-push.log"))
        log.emit("usage: python3 git_push.py <repository> [remote] [base]")
        log.fail(2)

    repository_text = argv[0]
    remote = argv[1] if len(argv) >= 2 else "origin"
    base = argv[2] if len(argv) == 3 else ""

    if os.environ.get("GIT_PUSH_LOG"):
        log.open(os.environ["GIT_PUSH_LOG"])

    log.step = "validate-remote"
    if not remote or remote.startswith("-"):
        log.emit("remote is empty or looks like an option")
        log.fail(2)

    if base:
        log.step = "validate-base"
        if base.startswith("-"):
            log.emit("base looks like an option")
            log.fail(2)

    log.step = "require-git"
    require_git(log)

    log.step = "validate-repository"
    repository = ensure_worktree(log, repository_text)
    if log.path is None:
        log.step = "open-log"
        open_branch_log(log, repository, "push")

    log.step = "validate-branch"
    symbolic = checked_out_branch(repository)
    if symbolic.returncode != 0 or not is_feature_branch(symbolic.stdout.strip()):
        log.emit("push requires branch feature/<ticket>-<short-feature-name>")
        log.fail(2)
    branch = symbolic.stdout.strip()

    log.step = "validate-clean"
    status = git_text(repository, ["status", "--porcelain"])
    if status.returncode != 0:
        detail = (status.stderr or status.stdout).strip()
        if detail:
            log.emit(detail)
        log.fail(status.returncode or 1)
    if status.stdout.strip():
        log.emit("worktree has uncommitted changes")
        log.fail(2)

    if not base:
        log.step = "resolve-base"
        base = remote_default_branch(repository, remote)
        if not base:
            log.emit(f"{remote} has no local default branch")
            log.fail(2)

    log.step = "validate-base"
    verified = git_text(repository, ["rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"])
    if verified.returncode != 0:
        log.emit(f"base is not available locally: {base}")
        log.fail(2)

    log.step = "validate-ancestor"
    ancestor = git_text(repository, ["merge-base", "--is-ancestor", base, "HEAD"])
    if ancestor.returncode != 0:
        log.emit(f"{base} is not an ancestor of HEAD; rebase onto it first")
        log.fail(2)

    log.step = "validate-ahead"
    counted = git_text(repository, ["rev-list", "--count", f"{base}..HEAD"])
    if counted.returncode != 0:
        detail = (counted.stderr or counted.stdout).strip()
        if detail:
            log.emit(detail)
        log.fail(counted.returncode or 1)
    count = int(counted.stdout.strip() or "0")
    if count < 1:
        log.emit(f"HEAD has no commits beyond {base}")
        log.fail(2)

    log.step = "push"
    log.emit(f"pushing {branch} to {remote}")
    refspec = f"HEAD:refs/heads/{branch}"
    expected = tracking_sha(repository, remote, branch)
    if expected:
        lease = f"--force-with-lease=refs/heads/{branch}:{expected}"
        run_git(log, ["-C", str(repository), "push", "-u", lease, "--", remote, refspec])
    else:
        run_git(log, ["-C", str(repository), "push", "-u", "--", remote, refspec])

    log.emit(f"BRANCH={branch}")
    log.step = "done"
    finish_ok(log, read_head(log, repository))


def main() -> None:
    push(sys.argv[1:])


if __name__ == "__main__":
    main()
