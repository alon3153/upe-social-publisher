"""Fail (exit 1) if secret-looking strings are about to be committed.

Usage:
  python scripts/check_no_secrets.py --staged          # added lines in `git diff --cached`
  python scripts/check_no_secrets.py FILE [FILE ...]   # whole files

Only masked fingerprints are printed, never the matched value. --staged checks ADDED lines
only, so copies already in history (alert #1, handled separately) do not block the daily run,
but any new leak stops the commit/push.
"""
import sys, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aeo_models import find_secrets


def staged_added_text():
    out = subprocess.run(["git", "diff", "--cached", "-U0", "--no-color"],
                         capture_output=True, text=True, check=True).stdout
    return "\n".join(l[1:] for l in out.splitlines() if l.startswith("+") and not l.startswith("+++"))


def main(argv):
    if argv[:1] == ["--staged"]:
        sources = {"<staged diff>": staged_added_text()}
    else:
        sources = {f: Path(f).read_text(encoding="utf-8", errors="replace") for f in argv if Path(f).exists()}
    bad = 0
    for name, text in sources.items():
        hits = find_secrets(text)
        if hits:
            bad += len(hits)
            print(f"::error::{len(hits)} secret-like value(s) in {name}: {sorted(set(hits))[:5]}")
    if bad:
        return 1
    print("check_no_secrets: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
