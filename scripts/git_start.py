#!/usr/bin/env python3
"""Create or resume a feature branch in an existing checkout.

Usage: python3 -B git_start.py <repository> <ticket> <short-feature-name> [base]
Log:   GIT_START_LOG if set, otherwise <checkout>/workflow-logs/<branch>/start.log
"""

from __future__ import annotations

import os
import sys

from git_runtime import (
    WorkflowLog, checked_out_branch, ensure_worktree, finish_ok, git_text,
    make_feature_branch, open_branch_log, operation_in_progress, read_head,
    remote_default_branch, require_clean, require_git, run_git,
)

log = WorkflowLog()


def start(argv: list[str]) -> None:
    log.step = "parse-arguments"
    if len(argv) not in (3, 4):
        log.open(os.environ.get("GIT_START_LOG", "git-start.log"))
        log.emit(__doc__ or "")
        log.fail(2)
    require_git(log)
    repository = ensure_worktree(log, argv[0])
    if os.environ.get("GIT_START_LOG"):
        log.open(os.environ["GIT_START_LOG"])
    else:
        open_branch_log(log, repository, "start")
    log.step = "validate-operation"
    if operation_in_progress(repository):
        log.emit("a git operation is already in progress")
        log.fail(2)
    branch = make_feature_branch(log, argv[1], argv[2])
    base = argv[3] if len(argv) == 4 else remote_default_branch(repository)
    log.step = "validate-base"
    if base.startswith("-"):
        log.fail(2)
    current = checked_out_branch(repository)
    if current.returncode or current.stdout.strip() != branch:
        require_clean(log, repository)
        local = git_text(repository, ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"])
        if local.returncode == 0:
            run_git(log, ["-C", str(repository), "switch", "--", branch])
        else:
            remote = git_text(repository, ["show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"])
            if remote.returncode == 0:
                run_git(log, ["-C", str(repository), "switch", "--track", "-c", branch, f"origin/{branch}"])
            else:
                if not base:
                    log.emit("origin has no local default branch; supply the intended base ref")
                    log.fail(2)
                run_git(log, ["-C", str(repository), "switch", "-c", branch, base])
    log.emit(f"BRANCH={branch}")
    finish_ok(log, read_head(log, repository))


if __name__ == "__main__":
    start(sys.argv[1:])
