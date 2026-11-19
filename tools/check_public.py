"""Pre-push checks for the built site in docs/. Exit 1 on any problem.

1. Every internal link and asset resolves to a file in docs/.
2. No denied term (from the private deny file, if present, plus a built-in list) appears in any text file.
3. Every file under docs/ came from an allowed source (built pages, static/, content/images, the two public repos).
4. No long Hebrew passage on English pages (guards against exam text leaking in).
"""
from __future__ import annotations

import json
import re
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DENY_FILE = ROOT.parent / "private-exams" / "runs" / "reviewer-repo-deny.json"
# Personal and other sensitive terms live only in the private deny file, never in this public repo.
BUILTIN_DENY = ["@users.noreply", "private-exams", "private-bechina", "rubrics-sealed", "salt"]
ALLOWED_DIRS = {"assets", "data", "daf", "findings", "halachabench", "hashkafabench", "values", "method", "about", "he"}

problems: list[str] = []
deny = list(BUILTIN_DENY)
if DENY_FILE.exists():
    deny += [t for t in json.loads(DENY_FILE.read_text(encoding="utf-8")) if isinstance(t, str)]
deny = sorted({t.lower() for t in deny})
# words that legitimately contain a denied substring
ALLOW_WORDS = {"salted", "salts"}

text_files = [p for p in DOCS.rglob("*") if p.is_file() and p.suffix in {".html", ".css", ".js", ".csv", ".xml", ".txt", ""}]
for p in text_files:
    t = p.read_text(encoding="utf-8", errors="replace")
    low = t.lower()
    for term in deny:
        for m in re.finditer(re.escape(term), low):
            word = re.search(r"[\w@.-]*$", low[:m.start()]).group(0) + re.match(r"[\w@.-]*", low[m.start():]).group(0)
            if word.strip(".-") in ALLOW_WORDS:
                continue
            problems.append(f"denied term {term!r} in {p.relative_to(DOCS)}: …{t[max(0, m.start() - 40):m.end() + 40]!r}…")
    if p.suffix == ".html":
        for ref in re.findall(r'(?:href|src)="(/[^"#?]*)', t):
            target = DOCS / ref.lstrip("/")
            if ref.endswith("/"):
                target = target / "index.html"
            if not target.exists():
                problems.append(f"broken link {ref} in {p.relative_to(DOCS)}")
        # Hebrew pages (docs/he/...) are translations of the public English pages; on English pages a long
        # Hebrew run would most likely be leaked exam text.
        if p.relative_to(DOCS).parts[0] != "he":
            body = re.sub(r"<[^>]+>", " ", t)
            for run in re.findall(r"[֐-׿][֐-׿\s\"'׳״,.:;()-]{60,}", body):
                problems.append(f"long Hebrew passage in {p.relative_to(DOCS)}: {run[:60]!r}")

for p in DOCS.iterdir():
    if p.is_dir() and p.name not in ALLOWED_DIRS:
        problems.append(f"unexpected folder docs/{p.name}")

if problems:
    print("\n".join(problems))
    print(f"\nFAIL: {len(problems)} problem(s)")
    sys.exit(1)
print(f"OK: {len(text_files)} text files checked, deny list of {len(deny)} terms, no broken internal links")
