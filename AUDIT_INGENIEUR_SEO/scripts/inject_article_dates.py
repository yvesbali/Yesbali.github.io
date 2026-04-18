"""
inject_article_dates.py
=======================
Inject datePublished + dateModified into Article JSON-LD schema
of /articles/*.html pages, using REAL git history (first-commit = published,
last-commit = modified). Idempotent.

Source de vérité : `git log --reverse --format="%aI"` et `git log -1 --format="%aI"`
per file. Aucune date inventée.
"""
import subprocess
import re
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ARTICLES_DIR = os.path.join(REPO_ROOT, "articles")


def git_first_commit_iso(filepath):
    """Return ISO-8601 datetime of first commit touching filepath, or None."""
    try:
        rel = os.path.relpath(filepath, REPO_ROOT)
        out = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "log", "--reverse", "--format=%aI", "--", rel],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if not out:
            return None
        return out.splitlines()[0]
    except Exception:
        return None


def git_last_commit_iso(filepath):
    try:
        rel = os.path.relpath(filepath, REPO_ROOT)
        out = subprocess.check_output(
            ["git", "-C", REPO_ROOT, "log", "-1", "--format=%aI", "--", rel],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return out or None
    except Exception:
        return None


def patch_article(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find first Article JSON-LD block
    pattern = re.compile(
        r'(<script type="application/ld\+json">\s*)(\{.*?\})(\s*</script>)',
        re.DOTALL,
    )
    updated = False
    date_published = git_first_commit_iso(filepath)
    date_modified = git_last_commit_iso(filepath)

    if not date_published:
        return ("skip_no_git", None, None)

    def replace_block(match):
        nonlocal updated
        prefix, json_str, suffix = match.group(1), match.group(2), match.group(3)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return match.group(0)  # keep as-is

        items = data if isinstance(data, list) else [data]
        changed = False
        for it in items:
            if not isinstance(it, dict):
                continue
            t = it.get("@type", "")
            if t in ("Article", "BlogPosting", "NewsArticle"):
                if "datePublished" not in it or not it["datePublished"]:
                    it["datePublished"] = date_published
                    changed = True
                if "dateModified" not in it or not it["dateModified"]:
                    it["dateModified"] = date_modified or date_published
                    changed = True
        if changed:
            updated = True
            new_json = json.dumps(data if isinstance(data, list) else items[0],
                                  ensure_ascii=False, indent=2)
            return prefix + new_json + suffix
        return match.group(0)

    new_content, nsub = pattern.subn(replace_block, content, count=1)
    if updated and new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return ("patched", date_published, date_modified)
    return ("already_ok", date_published, date_modified)


def main():
    if not os.path.isdir(ARTICLES_DIR):
        print(f"ERROR: articles dir not found: {ARTICLES_DIR}", file=sys.stderr)
        sys.exit(1)

    files = sorted(
        os.path.join(ARTICLES_DIR, f)
        for f in os.listdir(ARTICLES_DIR)
        if f.endswith(".html")
    )

    patched = 0
    skipped = 0
    already = 0
    for f in files:
        status, dp, dm = patch_article(f)
        rel = os.path.relpath(f, REPO_ROOT)
        if status == "patched":
            patched += 1
            print(f"[OK] {rel}")
            print(f"     datePublished: {dp}")
            print(f"     dateModified:  {dm}")
        elif status == "already_ok":
            already += 1
        elif status == "skip_no_git":
            skipped += 1
            print(f"[SKIP] {rel} (no git history)")

    print()
    print(f"Total: {len(files)} files")
    print(f"Patched: {patched}")
    print(f"Already OK: {already}")
    print(f"Skipped (no git history): {skipped}")


if __name__ == "__main__":
    main()
