#!/usr/bin/env python3
"""Canonical git commit script served at git://scripts/git_commit.py.

The MCP server does not execute this file. A client copies it into
mcp-scripts/ next to git_runtime.py and runs it with Python 3.

Usage: python3 git_commit.py <repository> <message>
Log:   GIT_COMMIT_LOG if set, otherwise <checkout>/workflow-logs/<branch>/commit.log

Stages every change in an existing feature-branch checkout and commits it.
It does not push.
"""

from __future__ import annotations

import os
import sys

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
    require_identity,
    run_git,
)

log = WorkflowLog()


def commit(argv: list[str]) -> None:
    log.step = "parse-arguments"
    if len(argv) != 2:
        log.open(os.environ.get("GIT_COMMIT_LOG", "git-commit.log"))
        log.emit("usage: python3 git_commit.py <repository> <message>")
        log.fail(2)

    repository_text = argv[0]
    message = argv[1]

    if os.environ.get("GIT_COMMIT_LOG"):
        log.open(os.environ["GIT_COMMIT_LOG"])

    log.step = "validate-message"
    if not message.strip() or message.startswith("-"):
        log.emit("message is empty or looks like an option")
        log.fail(2)

    log.step = "require-git"
    require_git(log)

    log.step = "validate-repository"
    repository = ensure_worktree(log, repository_text)
    if log.path is None:
        log.step = "open-log"
        open_branch_log(log, repository, "commit")

    log.step = "validate-branch"
    symbolic = checked_out_branch(repository)
    if symbolic.returncode != 0 or not is_feature_branch(symbolic.stdout.strip()):
        log.emit("commit requires branch feature/<ticket>-<short-feature-name>")
        log.fail(2)
    branch = symbolic.stdout.strip()

    log.step = "require-identity"
    require_identity(log, repository)

    log.step = "validate-changes"
    status = git_text(repository, ["status", "--porcelain"])
    if status.returncode != 0:
        detail = (status.stderr or status.stdout).strip()
        if detail:
            log.emit(detail)
        log.fail(status.returncode or 1)
    if not status.stdout.strip():
        log.emit("worktree has no changes")
        log.fail(2)

    log.step = "commit"
    log.emit(f"committing on {branch}")
    run_git(log, ["-C", str(repository), "add", "-A"])
    run_git(log, ["-C", str(repository), "commit", "-m", message])
    log.emit(f"BRANCH={branch}")
    log.step = "done"
    finish_ok(log, read_head(log, repository))


def main() -> None:
    commit(sys.argv[1:])


if __name__ == "__main__":
    main()
