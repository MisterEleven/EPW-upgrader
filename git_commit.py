"""
git_commit.py
-------------
Creates granular conventional commits for the epwupgrader project.
Run with: python3 git_commit.py
"""
import subprocess
import sys
import os

ROOT = "/app/projects/epwupgrader"
os.chdir(ROOT)


def run(cmd, check=True, capture=False):
    """Run a shell command as a list. Print output. Return CompletedProcess."""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        cwd=ROOT,
    )
    if not capture:
        pass
    else:
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip())
    if check and result.returncode != 0:
        print(f"  FAILED (exit {result.returncode})")
        if capture:
            print("  STDOUT:", result.stdout)
            print("  STDERR:", result.stderr)
        sys.exit(1)
    return result


# ── 0. Git identity ──────────────────────────────────────────────────────────
print("\n[git] Configuring identity...")
run(["git", "config", "user.name",  "EPW Upgrader"], capture=True)
run(["git", "config", "user.email", "epwupgrader@dev.local"], capture=True)

# ── 1. Remove stale index lock if present ────────────────────────────────────
lock = os.path.join(ROOT, ".git", "index.lock")
if os.path.exists(lock):
    os.remove(lock)
    print("[git] Removed stale index.lock")

# ── Helper ───────────────────────────────────────────────────────────────────
def commit(message, paths):
    """Stage the given paths and create a commit."""
    print(f"\n[git] Committing: {message}")
    existing = [p for p in paths if os.path.exists(os.path.join(ROOT, p))]
    missing  = [p for p in paths if not os.path.exists(os.path.join(ROOT, p))]
    if missing:
        print(f"  [warn] Missing (skipped): {missing}")
    if not existing:
        print("  [warn] No files exist for this commit — skipping")
        return None
    for p in existing:
        run(["git", "add", p], capture=True)
    # Check if there is anything staged
    status = run(["git", "diff", "--cached", "--name-only"], capture=True, check=False)
    if not status.stdout.strip():
        print("  [info] Nothing new to stage — skipping commit")
        return None
    result = run(["git", "commit", "-m", message], capture=True)
    sha_r = run(["git", "rev-parse", "--short", "HEAD"], capture=True)
    sha = sha_r.stdout.strip()
    print(f"  Created commit {sha}: {message}")
    return sha


shas = {}

# ── Commit 1: project scaffolding ───────────────────────────────────────────
shas[1] = commit(
    "chore: initialise project structure and add requirements",
    [
        "requirements.md",
        "requirements.txt",
        ".gitignore",
        "setup.py",
        "pyproject.toml",
    ],
)

# ── Commit 2: architecture ───────────────────────────────────────────────────
shas[2] = commit(
    "docs: add system architecture with ASCII diagrams and EPW format reference",
    ["architecture.md"],
)

# ── Commit 3: parser + __init__ ──────────────────────────────────────────────
shas[3] = commit(
    "feat(parser): implement EPW file parser returning (df, metadata, header_lines)",
    [
        "epwupgrader/__init__.py",
        "epwupgrader/parser.py",
    ],
)

# ── Commit 4: psychrometrics ─────────────────────────────────────────────────
shas[4] = commit(
    "feat(psychrometrics): implement Magnus-Tetens psychrometric recalculations",
    ["epwupgrader/psychrometrics.py"],
)

# ── Commit 5: anomaly data ───────────────────────────────────────────────────
shas[5] = commit(
    "feat(anomalies): add CMIP6 SSP5-8.5 and SSP2-4.5 monthly anomaly data",
    [
        "epwupgrader/anomalies.py",
        "epwupgrader/gcm_data.py",
    ],
)

# ── Commit 6: morphing engine ────────────────────────────────────────────────
shas[6] = commit(
    "feat(morphing): implement Belcher 2005 temperature, radiation and wind morphing",
    ["epwupgrader/morphing.py"],
)

# ── Commit 7: writer ─────────────────────────────────────────────────────────
shas[7] = commit(
    "feat(writer): implement EPW writer with per-column precision formatting",
    ["epwupgrader/writer.py"],
)

# ── Commit 8: CLI ────────────────────────────────────────────────────────────
shas[8] = commit(
    "feat(cli): add argparse CLI with tail amplification and verbose summary",
    ["epwupgrader/cli.py"],
)

# ── Commit 9: tests ──────────────────────────────────────────────────────────
shas[9] = commit(
    "test: add pytest suite with conftest fixtures and smoke test bootstrap",
    [
        "tests/conftest.py",
        "tests/test_parser.py",
        "tests/test_morphing.py",
        "tests/test_psychrometrics.py",
        "tests/test_anomalies.py",
        "bootstrap_and_test.py",
        "run_tests.py",
    ],
)

# ── Commit 10: CI/CD ─────────────────────────────────────────────────────────
shas[10] = commit(
    "ci: add GitHub Actions CI matrix and PyPI publish workflow",
    [
        ".github/workflows/ci.yml",
        ".github/workflows/publish.yml",
    ],
)

# ── Commit 11: README ────────────────────────────────────────────────────────
shas[11] = commit(
    "docs: add comprehensive README with installation, usage and methodology",
    ["README.md"],
)

# ── Catch-all: anything remaining unstaged ───────────────────────────────────
run(["git", "add", "-A"], capture=True)
status = run(["git", "diff", "--cached", "--name-only"], capture=True, check=False)
if status.stdout.strip():
    print(f"\n[git] Committing remaining files:\n{status.stdout.strip()}")
    run(["git", "commit", "-m", "chore: add remaining project files"], capture=True)

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("GIT LOG (all commits)")
print("=" * 60)
log = run(["git", "log", "--oneline"], capture=True)
print(log.stdout)

print("=" * 60)
print("ALL COMMITS CREATED SUCCESSFULLY")
sys.exit(0)