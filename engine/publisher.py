"""
TrendPulse Engine — Publisher
Handles git operations to publish the site to GitHub Pages.
"""
import logging
import subprocess
from datetime import datetime
from pathlib import Path

from engine.config import PROJECT_ROOT, GIT_REMOTE, GIT_BRANCH

logger = logging.getLogger(__name__)


def _run_git(*args: str) -> tuple[bool, str]:
    """Run a git command in the project root."""
    cmd = ["git"] + list(args)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.warning("git %s failed: %s", args[0], result.stderr.strip())
            return False, result.stderr.strip()
        return True, result.stdout.strip()
    except Exception as e:
        logger.error("git command error: %s", e)
        return False, str(e)


def is_git_repo() -> bool:
    """Check if the project root is a git repository."""
    return (PROJECT_ROOT / ".git").is_dir()


def init_repo():
    """Initialize git repo if not already initialized."""
    if is_git_repo():
        logger.info("Git repo already initialized")
        return True
    ok, _ = _run_git("init")
    if ok:
        # Create .gitignore
        gitignore = PROJECT_ROOT / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "__pycache__/\n*.pyc\n.env\nvenv/\n*.egg-info/\n",
                encoding="utf-8",
            )
            _run_git("add", ".gitignore")
        logger.info("Initialized git repo")
    return ok


def publish(message: str | None = None, dry_run: bool = False) -> bool:
    """
    Stage all changes, commit, and push to remote.
    In dry_run mode, only stages and commits locally without pushing.
    """
    if not is_git_repo():
        logger.error("Not a git repo. Run init_repo() first.")
        return False

    if not message:
        message = f"Auto-publish: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"

    # Stage all changes in site/ and data/
    _run_git("add", "site/")
    _run_git("add", "data/")

    # Check if there are changes to commit
    ok, status = _run_git("status", "--porcelain")
    if ok and not status:
        logger.info("No changes to publish")
        return True

    # Commit
    ok, out = _run_git("commit", "-m", message)
    if not ok:
        logger.error("Commit failed")
        return False
    logger.info("Committed: %s", message)

    if dry_run:
        logger.info("Dry run — skipping push")
        return True

    # Push
    ok, out = _run_git("push", GIT_REMOTE, GIT_BRANCH)
    if not ok:
        logger.error("Push failed: %s", out)
        return False

    logger.info("Published to %s/%s", GIT_REMOTE, GIT_BRANCH)
    return True
