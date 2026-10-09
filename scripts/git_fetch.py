#!/usr/bin/env python3
"""Canonical git fetch script served at git://scripts/git_fetch.py.

The MCP server does not execute this file. A client copies it into
mcp-scripts/ next to git_runtime.py and runs it with Python 3.

Usage: python3 git_fetch.py <repository> [remote] [ref]
Log:   GIT_FETCH_LOG if set, otherwise <checkout>/workflow-logs/<branch>/fetch.log

Fetches into an existing checkout. It does not rebase, checkout, or push.
"""

from __future__ import annotations

import os
import sys

from git_runtime import WorkflowLog, ensure_worktree, finish_ok, open_branch_log, read_head, require_git, run_git

log = WorkflowLog()


def fetch(argv: list[str]) -> None:
    log.step = "parse-arguments"
    if len(argv) < 1 or len(argv) > 3:
        log.open(os.environ.get("GIT_FETCH_LOG", "git-fetch.log"))
        log.emit("usage: python3 git_fetch.py <repository> [remote] [ref]")
        log.fail(2)

    repository_text = argv[0]
    remote = argv[1] if len(argv) >= 2 else "origin"
    ref = argv[2] if len(argv) == 3 else ""

    if os.environ.get("GIT_FETCH_LOG"):
        log.open(os.environ["GIT_FETCH_LOG"])

    log.step = "require-git"
    require_git(log)

    log.step = "validate-repository"
    repository = ensure_worktree(log, repository_text)
    if log.path is None:
        log.step = "open-log"
        open_branch_log(log, repository, "fetch")

    log.step = "validate-remote"
    if not remote or remote.startswith("-"):
        log.emit("remote is empty or looks like an option")
        log.fail(2)

    log.step = "validate-ref"
    if ref.startswith("-"):
        log.emit("ref looks like an option")
        log.fail(2)

    head_before = read_head(log, repository)

    log.step = "fetch"
    if ref:
        log.emit(f"fetching {ref} from {remote}")
        run_git(log, ["-C", str(repository), "fetch", "--tags", remote, ref])
    else:
        log.emit(f"fetching {remote}")
        run_git(log, ["-C", str(repository), "fetch", "--prune", "--tags", remote])

    log.step = "verify-head"
    head_after = read_head(log, repository)
    if head_after != head_before:
        log.emit(f"HEAD changed from {head_before} to {head_after}")
        log.fail(1)
    finish_ok(log, head_after)


def main() -> None:
    fetch(sys.argv[1:])


if __name__ == "__main__":
    main()
