"""Build halachabench.ai into docs/ from PUBLIC sources only.

Sources (nothing else is read):
  ../halacha-bench-results   public repo: README results table, footnotes, updates, bundle/, results.png
  ../hashkafa-bench-results  public repo: README table, data/*.csv, charts/*.png
  content/                   this repo: findings (Markdown), values.json, images already posted on X

Usage:  python tools/build.py            (then: python tools/check_public.py)
"""
from __future__ import annotations

import csv
import html
import json
import math
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
HB = ROOT.parent / "halacha-bench-results"
HK = ROOT.parent / "hashkafa-bench-results"
CONTENT = ROOT / "content"
STATIC = ROOT / "static"
PREVIEW = "--preview" in sys.argv
OUT = ROOT / ("preview-build" if PREVIEW else "docs")
PREVIEW_META = '\n<meta name="robots" content="noindex, nofollow">' if PREVIEW else ""
PREVIEW_BAR = ('\n<div class="preview-bar">Private preview for the team. Not public yet, please do not share.</div>'
               if PREVIEW else "")
SITE = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))

e = html.escape

# --------------------------------------------------------------------------- labs

LABS = {  # lab -> css class. Four hues validated all-pairs (light and dark), xAI as ink, the rest neutral gray.
    "Anthropic": "lab-anthropic", "OpenAI": "lab-openai", "Google": "lab-google", "Meta": "lab-meta", "xAI": "lab-xai",
}


def lab_of(name: str) -> str:
    n = name.lower()
    if n.startswith("claude"):
        return "Anthropic"
    if n.startswith("gpt"):
        return "OpenAI"
    if n.startswith(("gemini", "gemma")):
        return "Google"
    if n.startswith("grok"):
        return "xAI"
    if n.startswith(("muse", "llama")):
        return "Meta"
    if n.startswith("qwen"):
        return "Alibaba"
    if n.startswith("dictalm"):
        return "Dicta"
    if n.startswith("ling"):
        return "inclusionAI"
    return "Other"


def lab_cls(lab: str) -> str:
    return LABS.get(lab, "lab-other")


def chip(lab: str) -> str:
    return f'<span class="lab-dot {lab_cls(lab)}" aria-hidden="true"></span>'


SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"


def sup_to_int(s: str) -> str:
    return "".join(str(SUP.index(c)) for c in s if c in SUP)


def md_inline(s: str) -> str:
    out = markdown.markdown(s)
    return re.sub(r"^<p>|</p>$", "", out.strip())


# --------------------------------------------------------------------------- HalachaBench


def parse_halacha():
    text = (HB / "README.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    models = []
    in_table = False
    for ln in lines:
        if ln.startswith("| # | Model |"):
            in_table = True
            continue
        if in_table:
            if not ln.startswith("|"):
                if models:
                    break
                continue
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if set(cells[0]) <= set("-"):
                continue
            rank, name, score, ci, worst, how = cells
            notes = sup_to_int(name + how)
            added_later = "†" in name
            clean = re.sub(r"[†" + SUP + r"]", "", name).strip()
            how_clean = re.sub("[" + SUP + "]", "", how).strip()
            lo, hi = [float(x) for x in re.split(r"\s*[–-]\s*", ci)]
            local = how_clean.lower().startswith("local")
            models.append({
                "rank": int(rank), "name": clean, "lab": lab_of(clean), "score": float(score),
                "lo": lo, "hi": hi, "worst": float(worst), "how": how_clean, "notes": sorted(set(notes)),
                "added_later": added_later, "kind": "open" if local else "hosted",
                "slug": clean.lower().replace(" ", "-"),
            })
    # cross-check every score against bundle/scores.json
    sj = json.loads((HB / "bundle" / "scores.json").read_text(encoding="utf-8"))
    means = {re.sub(r"[^a-z0-9]", "", k): v for k, v in sj["scores"]["test"]["gpt-6-astra"].items()}
    for m in models:
        key = re.sub(r"[^a-z0-9]", "", m["slug"])
        if key not in means:
            raise SystemExit(f"scores.json has no entry for {m['slug']}")
        if round(means[key]["mean"], 1) != m["score"]:
            raise SystemExit(f"README score {m['score']} != scores.json {means[key]['mean']} for {m['name']}")
    if len(models) != len(means):
        raise SystemExit(f"README table has {len(models)} models, scores.json {len(means)}")

    # footnotes ¹..⁹ : paragraphs starting with a superscript digit
    notes = {}
    cur = None
    for ln in lines:
        mm = re.match("^([" + SUP + "]+) (.*)", ln)
        if mm:
            cur = sup_to_int(mm.group(1))
            notes[cur] = mm.group(2)
        elif cur and ln.strip() and not ln.startswith("#") and not ln.startswith("|"):
            notes[cur] += " " + ln.strip()
        else:
            cur = None
    # dated updates at the top: **13 November:** ...
    updates = []
    for para in re.split(r"\n\s*\n", text.split("## Results")[0]):
        mm = re.match(r"\*\*(\d{1,2}) November:\*\*\s*(.*)", para.strip(), re.S)
        if mm:
            t = " ".join(mm.group(2).split())
            t = re.sub(r"\s*See \[[^\]]+\]\(#[^)]+\)\.?", "", t)          # README-internal "See [Results](#results)."
            t = re.sub(r"\[([^\]]+)\]\(#[^)]+\)", r"\1", t)                # any other in-README anchor link
            t = re.sub(r";?\s*see note ([" + SUP + r"])", lambda x: f" (note {x.group(1)})", t)
            t = re.sub(r";\s*see Results\.?", ".", t)
            t = t[:1].upper() + t[1:]
            updates.append({"date": date(2026, 11, int(mm.group(1))), "text": t})
    # which models each update added
    first = date(2026, 11, 1)
    for m in models:
        m["added"] = first
        if m["added_later"]:
            for u in sorted(updates, key=lambda u: u["date"]):
                if re.search(r"(?<![\w.])" + re.escape(m["name"]) + r"(?!\w|\.\d)", u["text"]):
                    m["added"] = u["date"]
                    break
    # comparison bullets and section texts reused on pages
    comp = text.split("question\nby question:")[1].split("\n¹")[0] if "question\nby question:" in text else ""
    sect = {}
    for name in ["Checks on the Grok results", "How it works", "Caveats", "The bundle"]:
        mm = re.search(r"^## " + re.escape(name) + r"\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        sect[name] = mm.group(1).strip() if mm else ""
    mm = re.search(r"^### Scoring\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    sect["Scoring"] = mm.group(1).strip() if mm else ""
    sect["How it works"] = sect["How it works"].split("### Scoring")[0].strip()
    manifest = json.loads((HB / "bundle" / "MANIFEST.json").read_text(encoding="utf-8"))
    he = re.search(r'<div dir="rtl">\s*## [^\n]*\n(.*?)</div>', text, re.S)
    return {
        "models": models, "notes": notes, "updates": updates, "comparisons": comp.strip(),
        "sections": sect, "manifest": manifest, "hebrew": he.group(1).strip() if he else "",
    }


# --------------------------------------------------------------------------- HashkafaBench

CATS = [("shabbat", "Shabbat"), ("yomtov", "Yom Tov"), ("kashrut", "Kashrut"), ("tefillah", "Tefillah"),
        ("fasts_aveilut", "Fasts & mourning"), ("business", "Business"), ("bein_adam", "Bein adam lachavero")]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("-cli", ""))


def parse_hashkafa():
    text = (HK / "README.md").read_text(encoding="utf-8")
    models = []
    in_table = False
    for ln in text.splitlines():
        if ln.startswith("| Model | Stringency"):
            in_table = True
            continue
        if in_table:
            if not ln.startswith("|"):
                break
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if set(cells[0]) <= set("-"):
                continue
            name, s, ci = cells
            exploratory = "*" in name
            clean = name.replace("*", "").strip()
            lo, hi = [float(x) for x in re.split(r"\s*[–-]\s*", ci)]
            models.append({"name": clean, "lab": lab_of(clean), "s": float(s), "lo": lo, "hi": hi,
                           "exploratory": exploratory})
    rows = list(csv.DictReader(open(HK / "data" / "fable52_stringency_by_category.csv", encoding="utf-8")))
    bycat = {norm(r["model"]): r for r in rows if r["judge"].startswith("judge-claude-opus")}
    for m in models:
        r = bycat.get(norm(m["name"]))
        if not r:
            raise SystemExit(f"no per-category row for {m['name']}")
        m["cats"] = {k: float(r[k]) for k, _ in CATS}
    seph = json.loads((HK / "data" / "sephardi" / "overall.json").read_text(encoding="utf-8"))
    commits = sorted(HK.glob("charts/*.png"))
    return {"models": models, "sephardi": seph, "charts": [p.name for p in commits]}


# --------------------------------------------------------------------------- findings


def parse_findings():
    items = []
    for p in sorted((CONTENT / "findings").glob("*.md")):
        raw = p.read_text(encoding="utf-8")
        fm, body = raw.split("\n---\n", 1) if raw.startswith("---") else ("", raw)
        meta = {}
        for ln in fm.strip("-\n").splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip()
        meta["slug"] = p.stem[11:] if re.match(r"\d{4}-\d\d-\d\d-", p.stem) else p.stem
        meta["date"] = datetime.strptime(meta["date"], "%Y-%m-%d").date()
        meta["body"] = markdown.markdown(body, extensions=["tables", "attr_list", "md_in_html", "footnotes"])
        items.append(meta)
    return sorted(items, key=lambda m: (m["date"], m.get("order", "0")), reverse=True)


# --------------------------------------------------------------------------- layout

NAV = [("/halachabench/", "Leaderboard"), ("/hashkafabench/", "HashkafaBench"),
       ("/values/", "Halacha vs. own values"), ("/findings/", "Findings"), ("/method/", "Method"),
       ("/about/", "About")]


def fmt_date(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def short_date(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}"


def page(path: str, title: str, body: str, desc: str = "", image: str = "/assets/og.png", lang: str = "en",
         active: str = "") -> None:
    full_title = f"{title} | HalachaBench" if title != "HalachaBench" else "HalachaBench: AI models on real semicha exams"
    desc = desc or SITE["description"]
    nav = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if active == href else ""}>{e(label)}</a>' for href, label in NAV)
    beacon = ""
    if SITE.get("cf_beacon_token"):
        beacon = ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                  f"data-cf-beacon='{{\"token\": \"{e(SITE['cf_beacon_token'])}\"}}'></script>")
    dir_attr = ' dir="rtl"' if lang == "he" else ""
    hebrew_font = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" '
                   'href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?'
                   'family=Frank+Ruhl+Libre:wght@400;500;700&display=swap" rel="stylesheet">') if lang == "he" else ""
    doc = f"""<!doctype html>
<html lang="{lang}"{dir_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">{PREVIEW_META}
<link rel="canonical" href="https://{SITE['domain']}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="HalachaBench">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="https://{SITE['domain']}{path}">
<meta property="og:image" content="https://{SITE['domain']}{image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@HalachaBench">
<meta name="theme-color" content="#f6f4ef">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
{hebrew_font}
<link rel="stylesheet" href="/assets/style.css?v={SITE['build']}">
<script>try{{var t=localStorage.getItem('hb-theme');if(t)document.documentElement.dataset.theme=t;}}catch(_){{}}</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>{PREVIEW_BAR}
<header class="site-head">
  <div class="wrap head-row">
    <a class="wordmark" href="/">HalachaBench<span>.ai</span></a>
    <button class="nav-toggle" aria-expanded="false" aria-controls="site-nav"><span class="visually-hidden">Menu</span><i></i></button>
    <nav id="site-nav" class="site-nav" aria-label="Main">{nav}<a href="/he/" lang="he" class="he-link">עברית</a>
      <button class="theme-toggle" type="button" aria-label="Switch between light and dark"></button></nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-foot">
  <div class="wrap foot-grid">
    <div class="foot-about">
      <a class="wordmark small" href="/">HalachaBench<span>.ai</span></a>
      <p>An independent project. Not connected to or endorsed by the Chief Rabbinate of Israel or by any model
      developer; model names are their owners' trademarks. Results are provisional, and nothing here is psak.</p>
    </div>
    <nav class="foot-links" aria-label="Results"><h2>Results</h2>
      <a href="/halachabench/">Semicha exam leaderboard</a><a href="/hashkafabench/">HashkafaBench</a>
      <a href="/values/">Halacha vs. own values</a><a href="/findings/">All findings</a></nav>
    <nav class="foot-links" aria-label="Sources"><h2>Sources</h2>
      <a href="https://github.com/halachabench/halacha-bench-results">Results data on GitHub</a>
      <a href="https://github.com/halachabench/hashkafa-bench-results">HashkafaBench data on GitHub</a>
      <a href="/method/#cite">Cite HalachaBench</a></nav>
    <nav class="foot-links" aria-label="Contact"><h2>Contact</h2>
      <a href="mailto:{SITE['email']}">{SITE['email']}</a><a href="https://x.com/HalachaBench">@HalachaBench on X</a></nav>
  </div>
  <div class="wrap foot-legal"><span>© {SITE['_updated'].year} {e(SITE['copyright'])}</span><span>Last updated {fmt_date(SITE['_updated'])}</span></div>
</footer>
<div class="tip" role="tooltip" hidden></div>
<script src="/assets/site.js?v={SITE['build']}" defer></script>
{beacon}
</body>
</html>
"""
    dest = OUT / path.strip("/") / "index.html" if path != "/" else OUT / "index.html"
    if path.endswith(".html"):
        dest = OUT / path.strip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(doc, encoding="utf-8")


# --------------------------------------------------------------------------- shared pieces


def provisional_note(kind: str = "halacha") -> str:
    if kind == "halacha":
        txt = ("<strong>Provisional.</strong> One AI judge, GPT-6 Astra, which is itself on the board, has graded every "
               "answer. The rubrics were written and reviewed by AI models; no rabbi has reviewed them or graded an "
               "answer yet. These are not exam grades, and a high score is not authority to pasken.")
    else:
        txt = ("<strong>Descriptive, not psak.</strong> These results describe how models answer. Rubric positions "
               "were written and source-checked by the team and AI models, not yet reviewed by rabbis, and the judges "
               "are models from the labs being compared.")
    return f'<aside class="note-provisional"><p>{txt}</p></aside>'


def lab_key() -> str:
    items = "".join(f'<li>{chip(l)}{e(l)}</li>' for l in LABS)
    return f'<ul class="lab-key">{items}<li>{chip("Other")}Other labs</li></ul>'


def pct(v, lo, hi) -> float:
    return (v - lo) / (hi - lo) * 100


def score_track(m, big=False, lo=0, hi=100) -> str:
    """Dot for the mean, line for the 95% interval, open diamond for worst-of-3, on a lo..hi scale."""
    p = lambda v: max(0.0, min(100.0, pct(v, lo, hi)))
    worst = "" if big else f'<i class="worst" style="left:{p(m["worst"]):.2f}%"></i>'
    return (f'<span class="track{" big" if big else ""}"><i class="ci" style="left:{p(m["lo"]):.2f}%;'
            f'width:{p(m["hi"]) - p(m["lo"]):.2f}%"></i>{worst}<i class="dot {lab_cls(m["lab"])}" style="left:{p(m["score"]):.2f}%">'
            f'</i></span>')


def axis(vals, fmt, lo, hi, cls="axis") -> str:
    return f'<span class="{cls}" aria-hidden="true">' + "".join(
        f'<span style="left:{pct(v, lo, hi):.2f}%">{fmt(v)}</span>' for v in vals) + "</span>"


# --------------------------------------------------------------------------- HalachaBench charts


def leaderboard(H) -> str:
    latest = max(m["added"] for m in H["models"])
    rows = []
    for m in H["models"]:
        notes = "".join(f'<a class="fn" href="#note-{n}" aria-label="Note {n}">{SUP[int(n)]}</a>' for n in m["notes"])
        new = '<span class="new">new</span>' if m["added"] == latest and m["added_later"] else ""
        tip = (f"{m['name']} ({m['lab']})&#10;Score {m['score']:.1f}, 95% interval {m['lo']:.1f} to {m['hi']:.1f}"
               f"&#10;Worst of 3 attempts: {m['worst']:.1f}&#10;{m['how']}")
        top = " top" if m["rank"] <= 3 else ""
        rows.append(f"""<tr class="r{top}" data-lab="{e(m['lab'])}" data-kind="{m['kind']}">
<td class="rank" data-v="{m['rank']}">{m['rank']}</td>
<td class="model" data-v="{e(m['name'])}"><span class="mname">{chip(m['lab'])}{e(m['name'])}{notes}{new}</span>
<span class="msub">{e(m['lab'])}{', open weights' if m['kind'] == 'open' else ''}</span></td>
<td class="chart" data-v="{m['score']}" data-tip="{tip}" tabindex="0">{score_track(m)}</td>
<td class="num score" data-v="{m['score']}">{m['score']:.1f}</td>
<td class="num ci-txt hide-sm" data-v="{m['lo']}">{m['lo']:.1f}–{m['hi']:.1f}</td>
<td class="num hide-sm" data-v="{m['worst']}">{m['worst']:.1f}</td>
<td class="how hide-md" data-v="{e(m['how'])}">{e(m['how'])}</td>
<td class="num added hide-md" data-v="{m['added'].isoformat()}">{short_date(m['added'])}</td>
</tr>""")
    labs = sorted({m["lab"] for m in H["models"]}, key=lambda l: (l not in LABS, l))
    opts = "".join(f'<option value="{e(l)}">{e(l)}</option>' for l in labs)
    return f"""<div class="controls" data-for="hb-table">
  <div class="seg" role="group" aria-label="Which models">
    <button type="button" data-kind="all" aria-pressed="true">All {len(H['models'])}</button>
    <button type="button" data-kind="hosted" aria-pressed="false">Hosted</button>
    <button type="button" data-kind="open" aria-pressed="false">Open weights</button>
  </div>
  <label class="select"><span class="visually-hidden">Lab</span><select data-lab-filter><option value="">Every lab</option>{opts}</select></label>
  <a class="plain-link csv" href="/data/halachabench-v1.csv" download>Download CSV</a>
</div>
<div class="table-wrap"><table class="board" id="hb-table">
<caption class="visually-hidden">HalachaBench v1 scores, highest first</caption>
<thead><tr>
<th class="rank" data-sort="num" scope="col">#</th><th data-sort="text" scope="col">Model</th>
<th class="chart" scope="col"><span class="visually-hidden">Score with 95% interval</span>{axis([0, 25, 50, 75, 100], lambda v: f"{v:g}", 0, 100)}</th>
<th class="num" data-sort="num" aria-sort="descending" scope="col">Score</th>
<th class="num hide-sm" data-sort="num" scope="col">95% interval</th>
<th class="num hide-sm" data-sort="num" scope="col" title="Mean of each question's lowest-scoring attempt">Worst of 3</th>
<th class="hide-md" data-sort="text" scope="col">How it ran</th><th class="num hide-md" data-sort="text" scope="col">Added</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="chart-key">{lab_key()}<p><i class="k-dot"></i>score <i class="k-ci"></i>95% interval <i class="k-worst"></i>worst of 3 attempts</p></div>"""


def seq_color(v: float, lo=0.0, hi=100.0) -> tuple[str, str]:
    """Single-hue blue ramp (light -> dark), with ink that keeps contrast."""
    stops = [(0, (231, 238, 250)), (.25, (183, 211, 246)), (.5, (109, 167, 236)), (.75, (42, 120, 214)), (1, (16, 66, 129))]
    t = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            u = (t - a) / (b - a)
            rgb = tuple(round(ca[i] + (cb[i] - ca[i]) * u) for i in range(3))
            break
    lum = .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
    return "#%02x%02x%02x" % rgb, ("#111111" if lum > 140 else "#ffffff")


def by_paper_table(P) -> str:
    head = "".join(f'<th scope="col">{e(p)}</th>' for p in P["papers"])
    means = [sum(m["scores"][i] for m in P["models"]) / len(P["models"]) for i in range(len(P["papers"]))]
    body = []
    for m in P["models"]:
        cells = []
        for p, v in zip(P["papers"], m["scores"]):
            bg, fg = seq_color(v)
            cells.append(f'<td style="background:{bg};color:{fg}" data-tip="{e(m["name"])}&#10;{e(p)}: {v}" tabindex="0">{v}</td>')
        body.append(f'<tr><th scope="row">{chip(m["lab"])}{e(m["name"])}</th>{"".join(cells)}</tr>')
    foot = "".join(f"<td>{v:.0f}</td>" for v in means)
    return f"""<div class="table-wrap heat-wrap"><table class="heat seq">
<thead><tr><th></th>{head}</tr></thead><tbody>{''.join(body)}</tbody>
<tfoot><tr><th scope="row">Average of these 8</th>{foot}</tr></tfoot></table></div>"""


# --------------------------------------------------------------------------- HashkafaBench charts


def stringency_strip(K) -> str:
    rows = []
    for m in sorted(K["models"], key=lambda m: -m["s"]):
        ex = '<span class="new muted-tag">exploratory</span>' if m["exploratory"] else ""
        tip = f"{m['name']} ({m['lab']})&#10;Stringency {m['s']:.2f}, 95% CI {m['lo']:.2f} to {m['hi']:.2f}"
        rows.append(f"""<tr data-lab="{e(m['lab'])}">
<td class="model" data-v="{e(m['name'])}"><span class="mname">{chip(m['lab'])}{e(m['name'])}{ex}</span><span class="msub">{e(m['lab'])}</span></td>
<td class="chart" data-v="{m['s']}" data-tip="{tip}" tabindex="0"><span class="track mid"><i class="ci" style="left:{pct(m['lo'], .3, .7):.2f}%;width:{pct(m['hi'], .3, .7) - pct(m['lo'], .3, .7):.2f}%"></i><i class="dot {lab_cls(m['lab'])}" style="left:{pct(m['s'], .3, .7):.2f}%"></i></span></td>
<td class="num score" data-v="{m['s']}">{m['s']:.2f}</td>
<td class="num ci-txt hide-sm" data-v="{m['lo']}">{m['lo']:.2f}–{m['hi']:.2f}</td></tr>""")
    return f"""<div class="table-wrap"><table class="board" id="hk-table">
<caption class="visually-hidden">Stringency by model, most stringent first</caption>
<thead><tr><th data-sort="text" scope="col">Model</th>
<th class="chart" scope="col"><span class="ends" aria-hidden="true"><span>more lenient</span><span>more stringent</span></span>{axis([.3, .4, .5, .6, .7], lambda v: f"{v:.1f}", .3, .7)}</th>
<th class="num" data-sort="num" aria-sort="descending" scope="col">Stringency</th><th class="num hide-sm" data-sort="num" scope="col">95% CI</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="chart-key">{lab_key()}<p>0 is the most lenient position on a question's rubric, 1 the most stringent. Neither end is better.</p></div>"""


def radar(K) -> str:
    """Lab averages (pre-registered models only) on seven categories, plus every model as an optional overlay."""
    n = len(CATS)
    cx, cy, R, lo, hi = 260, 250, 190, .2, .7

    def pt(i, v):
        a = -math.pi / 2 + 2 * math.pi * i / n
        r = R * (v - lo) / (hi - lo)
        return cx + r * math.cos(a), cy + r * math.sin(a)

    rings = ""
    for v in [.3, .4, .5, .6, .7]:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i in range(n)))
        rings += f'<polygon class="ring{" ring-mid" if v == .5 else ""}" points="{pts}"/>'
        x, y = pt(0, v)
        rings += f'<text class="ring-lbl" x="{x + 6:.1f}" y="{y + 4:.1f}">{v:.1f}</text>'
    spokes, labels = "", ""
    for i, (_, lbl) in enumerate(CATS):
        x, y = pt(i, hi)
        spokes += f'<line class="spoke" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/>'
        lx, ly = pt(i, hi + .07)
        anchor = "middle" if abs(lx - cx) < 20 else ("start" if lx > cx else "end")
        labels += f'<text class="axis-lbl" x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}">{e(lbl)}</text>'
    labs = {}
    for m in K["models"]:
        if not m["exploratory"]:
            labs.setdefault(m["lab"], []).append(m)
    shapes, keys = "", ""
    for lab in [l for l in LABS if l in labs]:
        ms = labs[lab]
        vals = [sum(m["cats"][k] for m in ms) / len(ms) for k, _ in CATS]
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(vals)))
        dots = "".join(
            f'<circle class="vtx" cx="{x:.1f}" cy="{y:.1f}" r="4.5" data-tip="{e(lab)} average&#10;{e(CATS[i][1])}: {v:.2f}"/>'
            for i, ((x, y), v) in enumerate(zip((pt(i, v) for i, v in enumerate(vals)), vals)))
        shapes += f'<g class="shape {lab_cls(lab)}" data-series="{e(lab)}"><polygon points="{pts}"/>{dots}</g>'
        keys += (f'<button type="button" class="key-btn" data-series="{e(lab)}" aria-pressed="true">{chip(lab)}{e(lab)}'
                 f' <span class="muted">{len(ms)} model{"s" if len(ms) > 1 else ""}</span></button>')
    overlays, opts = "", ""
    for m in sorted(K["models"], key=lambda m: m["name"]):
        vals = [m["cats"][k] for k, _ in CATS]
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(vals)))
        dots = "".join(
            f'<circle class="vtx" cx="{x:.1f}" cy="{y:.1f}" r="4" data-tip="{e(m["name"])}&#10;{e(CATS[i][1])}: {v:.2f}"/>'
            for i, ((x, y), v) in enumerate(zip((pt(i, v) for i, v in enumerate(vals)), vals)))
        sid = re.sub(r"[^a-z0-9]+", "-", m["name"].lower())
        overlays += f'<g class="overlay {lab_cls(m["lab"])}" data-model="{sid}" hidden><polygon points="{pts}"/>{dots}</g>'
        opts += f'<option value="{sid}">{e(m["name"])}</option>'
    return f"""<div class="radar-block">
<svg class="radar" viewBox="0 0 520 500" role="img" aria-label="Average stringency by lab across seven areas of halacha">
{rings}{spokes}{shapes}{overlays}{labels}</svg>
<div class="radar-side">
<p class="side-head">Labs</p><div class="key-btns">{keys}</div>
<label class="select overlay-pick"><span>Add one model</span><select data-overlay><option value="">None</option>{opts}</select></label>
<p class="muted small">Each shape is the average of a lab's pre-registered models. The middle ring is 0.5; further
out is more stringent. Tap a lab to hide it.</p></div></div>"""


def div_color(v: float) -> tuple[str, str]:
    """Diverging blue (lenient) - neutral - red (stringent) around 0.5, saturating at +-0.25."""
    t = max(-1.0, min(1.0, (v - .5) / .25))
    mid = (239, 236, 228)
    pole = (42, 120, 214) if t < 0 else (214, 64, 63)
    a = abs(t) ** .85
    rgb = tuple(round(mid[i] + (pole[i] - mid[i]) * a) for i in range(3))
    lum = .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
    return "#%02x%02x%02x" % rgb, ("#111111" if lum > 140 else "#ffffff")


def heatmap(K) -> str:
    head = "".join(f'<th scope="col">{e(lbl)}</th>' for _, lbl in CATS)
    body = []
    for m in sorted(K["models"], key=lambda m: -m["s"]):
        cells = []
        for k, lbl in CATS:
            v = m["cats"][k]
            bg, fg = div_color(v)
            cells.append(f'<td style="background:{bg};color:{fg}" data-tip="{e(m["name"])}&#10;{e(lbl)}: {v:.2f}" tabindex="0">{v:.2f}</td>')
        body.append(f'<tr><th scope="row">{chip(m["lab"])}{e(m["name"])}{"*" if m["exploratory"] else ""}</th>{"".join(cells)}</tr>')
    stops = "".join(f'<span style="background:{div_color(v)[0]}"></span>' for v in [.25, .3, .35, .4, .45, .5, .55, .6, .65, .7, .75])
    return f"""<div class="table-wrap heat-wrap"><table class="heat"><thead><tr><th></th>{head}</tr></thead>
<tbody>{''.join(body)}</tbody></table></div>
<div class="ramp-key"><span>more lenient</span><span class="ramp">{stops}</span><span>more stringent</span></div>"""


# --------------------------------------------------------------------------- values charts


def dumbbells(V) -> str:
    rows = []
    for m in sorted(V["models"], key=lambda m: -m["own_vs_ruling"]):
        a, b = m["asked_twice"], m["own_vs_ruling"]
        tip = f"{m['name']}&#10;Ruling vs. its own choice: {b:.2f}&#10;Same ruling asked twice: {a:.2f}"
        rows.append(f"""<li data-tip="{tip}" tabindex="0"><span class="db-name">{chip(m['lab'])}{e(m['name'])}</span>
<span class="db-track"><i class="db-line" style="left:{a / .5 * 100:.2f}%;width:{(b - a) / .5 * 100:.2f}%"></i>
<i class="db-a" style="left:{a / .5 * 100:.2f}%"></i><i class="db-b" style="left:{b / .5 * 100:.2f}%"></i></span>
<span class="db-val">{b:.2f}</span></li>""")
    return f"""<div class="db-key"><span><i class="db-a-key"></i>The same halachic question, asked twice</span>
<span><i class="db-b-key"></i>Its ruling against what it would do itself</span></div>
<ol class="dumbbell">{''.join(rows)}</ol>
<div class="db-axis">{axis([0, .1, .2, .3, .4, .5], lambda v: f"{v:.1f}", 0, .5)}</div>
<p class="fig-note">Average distance between the two answers on each question's rubric: 0 is the same answer, 1 is
the opposite end. Graded by {e(V['grader'])}.</p>"""


def ballot(counts, who) -> str:
    y, mid, n = counts
    dots = ["full"] * y + ["half"] * mid + ["empty"] * n
    lbl = f"{y} yes" + (f", {mid} in between" if mid else "") + (f", {n} no" if n else "")
    name = "Ruling" if who == "ruling" else "Itself"
    return (f'<div class="ballot b-{who}"><span class="b-lbl">{name}</span>'
            f'<span class="dots" role="img" aria-label="{name}: {lbl}">{"".join(f"<i class={d}></i>" for d in dots)}</span>'
            f'<span class="b-count">{y} yes</span></div>')


# --------------------------------------------------------------------------- findings list


def study_tag(study: str) -> str:
    cls = {"HalachaBench": "t-hb", "HashkafaBench": "t-hk", "Values": "t-v"}.get(study, "t-hb")
    return f'<span class="tag {cls}">{e(study)}</span>'


def finding_row(f, thumbs=True) -> str:
    img = (f'<img src="{e(f["image"])}" alt="" loading="lazy" width="320" height="180">'
           if thumbs and f.get("image") else "")
    return f"""<li class="f-row" data-study="{e(f['study'])}"><a href="/findings/{f['slug']}/">
<time datetime="{f['date'].isoformat()}">{short_date(f['date'])}</time>
<div class="f-text">{study_tag(f['study'])}<h3>{e(f['title'])}</h3><p>{e(f['summary'])}</p></div>{img}</a></li>"""


# --------------------------------------------------------------------------- pages


def build_home(H, K, V, F):
    lead = H["models"][0]
    top = H["models"][:10]
    rows = "".join(f"""<li data-tip="{e(m['name'])}&#10;{m['score']:.1f} (95% interval {m['lo']:.1f} to {m['hi']:.1f})" tabindex="0" style="--d:{i * 60}ms">
<span class="h-rank">{m['rank']}</span><span class="h-name">{e(m['name'])}<small>{e(m['lab'])}</small></span>
{score_track(m, big=True, lo=50)}<span class="h-score">{m['score']:.1f}</span></li>""" for i, m in enumerate(top))
    hk = sorted(K["models"], key=lambda m: -m["s"])
    strip = "".join(f'<i class="dot {lab_cls(m["lab"])}" style="left:{pct(m["s"], .35, .6):.2f}%" data-tip="{e(m["name"])}: {m["s"]:.2f}" tabindex="0"></i>' for m in hk)
    latest = "".join(finding_row(f, thumbs=False) for f in F[:5])
    log = "".join(f'<li><time>{short_date(u["date"])}</time><span>{md_inline(u["text"])}</span></li>'
                  for u in sorted(H["updates"], key=lambda u: u["date"], reverse=True)[:4])
    n_hosted = sum(1 for m in H["models"] if m["kind"] == "hosted")
    body = f"""
<section class="hero">
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <h1>How well do AI models know halacha?</h1>
      <p class="lede">We give AI models the real semicha exam of Israel's Chief Rabbinate: in Hebrew, with no seforim
      and no internet, three attempts at every question. Each answer is graded against a rubric sealed before grading began.</p>
      <p class="hero-meta">{len(H['models'])} models, {n_hosted} of them hosted, on 60 questions from five Cheshvan 5787 papers.
      Updated {fmt_date(H['manifest_date'])}.</p>
      <p class="hero-links"><a class="btn" href="/halachabench/">See all {len(H['models'])} models</a>
      <a class="plain-link" href="/method/">How grading works</a></p>
    </div>
    <figure class="hero-board">
      <figcaption><span class="cap">Top ten, score out of 100</span><span class="h-axis"><span></span><span></span>{axis([50, 60, 70, 80, 90, 100], lambda v: f"{v:g}", 50, 100)}<span></span></span></figcaption>
      <ol>{rows}</ol>
      <p class="fig-note">Axis starts at 50. The line around each score is its 95% interval. Provisional: one AI judge, and no rabbi has graded an answer yet.</p>
    </figure>
  </div>
</section>

<section class="studies wrap" aria-label="The three studies">
  <article>
    <h2><a href="/halachabench/">The semicha exam</a></h2>
    <p>Can a model answer the questions a rabbi must answer for semicha? {e(lead['name'])} leads with
    {lead['score']:.1f}; the open-weight models we can run locally all score under 11.</p>
    <a class="plain-link" href="/halachabench/">Leaderboard</a>
  </article>
  <article>
    <h2><a href="/hashkafabench/">Stringent or lenient?</a></h2>
    <p>Which way do models lean on everyday questions? Claude's models rule most leniently; GPT, Gemini and Grok
    can't be told apart.</p>
    <div class="mini-strip" aria-label="Stringency of {len(hk)} models on one line"><span class="ms-track">{strip}</span>
    <span class="ms-ends"><span>lenient</span><span>stringent</span></span></div>
    <a class="plain-link" href="/hashkafabench/">Stringency by area</a>
  </article>
  <article>
    <h2><a href="/values/">Halacha vs. own values</a></h2>
    <p>Asked twice for a ruling, a model gives the same answer {V['headline']['asked_twice_same']:.0%} of the time.
    Asked what it would do itself, its answer matches its ruling only {V['headline']['own_vs_ruling_same']:.0%} of the time.</p>
    <div class="pair"><b>{V['headline']['asked_twice_same']:.0%}</b><b class="b2">{V['headline']['own_vs_ruling_same']:.0%}</b></div>
    <a class="plain-link" href="/values/">Where they part ways</a>
  </article>
</section>

<section class="wrap home-lower">
  <div>
    <h2 class="sec-title">Latest findings</h2>
    <ol class="f-list">{latest}</ol>
    <a class="plain-link" href="/findings/">Every finding</a>
  </div>
  <aside>
    <h2 class="sec-title">Leaderboard changes</h2>
    <ol class="changelog">{log}</ol>
    <div class="trust">
      <h2 class="sec-title">Built to be checked</h2>
      <ul>
        <li>Rubrics sealed with salted cryptographic commitments before any answer was graded.</li>
        <li>Model list, questions and analysis pre-registered by hash; every later change is a recorded amendment.</li>
        <li>Questions, answers and rubric text stay private, out of training data.</li>
        <li>Rabbis are invited to review the rubrics and grade a random sample of answers.</li>
      </ul>
      <a class="plain-link" href="/method/">Method and proof bundle</a>
      <div class="sources-credit">
        <a class="sefaria-badge" href="https://www.sefaria.org">
          <img class="on-light" src="/assets/img/powered-by-sefaria-navy.png" alt="Powered by Sefaria" width="140" height="73">
          <img class="on-dark" src="/assets/img/powered-by-sefaria-white.png" alt="Powered by Sefaria" width="140" height="73">
        </a>
        <p>Rubric sources were checked against texts from the Sefaria library.</p>
      </div>
    </div>
  </aside>
</section>"""
    page("/", "HalachaBench", body, active="/")


def build_halacha(H):
    lead = H["models"][0]
    P = json.loads((CONTENT / "by_paper.json").read_text(encoding="utf-8"))
    notes = "".join(f'<li id="note-{k}"><span class="fn-mark">{SUP[int(k)]}</span>{md_inline(v)}</li>' for k, v in sorted(H["notes"].items()))
    comp = markdown.markdown(H["comparisons"])
    log = "".join(f'<li><time>{fmt_date(u["date"])}</time><span>{md_inline(u["text"])}</span></li>'
                  for u in sorted(H["updates"], key=lambda u: u["date"], reverse=True))
    first = sum(1 for m in H["models"] if not m["added_later"])
    body = f"""
<section class="page-head wrap">
  <h1>The semicha exam leaderboard</h1>
  <p class="lede">{len(H['models'])} AI models answered the 60 questions of five Chief Rabbinate semicha papers from the
  Cheshvan 5787 sitting: three times each, in Hebrew, closed-book. {e(lead['name'])} leads with {lead['score']:.1f}.</p>
  <dl class="facts">
    <div><dt>Papers</dt><dd>Niddah, Chuppah v'Kiddushin, Mitzvot HaTeluyot BaAretz, Mikvaot, Tefillah u'Brachot</dd></div>
    <div><dt>Judge</dt><dd>GPT-6 Astra, effort high</dd></div>
    <div><dt>Data</dt><dd>{e(H['manifest']['stage'].capitalize())} bundle of {fmt_date(H['manifest_date'])}, <a href="https://github.com/halachabench/halacha-bench-results">on GitHub</a></dd></div>
  </dl>
</section>
<div class="wrap">
{provisional_note()}
<section class="block">
{leaderboard(H)}
<p class="fig-note">Score: how much of the rubric an answer achieves, 0 to 100, averaged over 60 questions and 3
attempts. Worst of 3: each question's lowest-scoring attempt, averaged. The 95% intervals come from a bootstrap over
questions (10,000 replicates) and cover only the choice of questions, not judge or rubric error. Select a column
heading to sort.</p>
</section>
<section class="block two-col">
  <div>
    <h2 class="sec-title" id="papers">Which paper is hardest?</h2>
    <p class="section-sub">Mean score per paper for the eight models scored on 1 November. Chuppah v'Kiddushin and
    Niddah are hardest for almost every model.</p>
    {by_paper_table(P)}
  </div>
</section>
<section class="block prose">
<h2 id="apart">Which models are clearly apart?</h2>
<p>Overlapping intervals do not by themselves mean two models are tied, so models were also compared question by question.</p>
{comp}
</section>
<section class="block prose">
<h2 id="notes">Notes on individual runs</h2>
<ol class="notes">{notes}</ol>
</section>
<section class="block prose">
<h2 id="updates">Changelog</h2>
<ol class="changelog wide">{log}<li><time>1 November 2026</time><span>First results: {first} models.</span></li></ol>
<p><a href="/method/">How the exam is run and graded</a>. <a href="/findings/grok-checks/">Checks on the Grok results</a>.</p>
</section>
</div>"""
    page("/halachabench/", "Semicha exam leaderboard", body,
         desc=f"{len(H['models'])} AI models on real Chief Rabbinate semicha exam questions. {lead['name']} leads with {lead['score']:.1f}.",
         active="/halachabench/")


def build_hashkafa(K):
    sp = K["sephardi"]["overall"]
    body = f"""
<section class="page-head wrap">
  <h1>Is your AI stringent or lenient?</h1>
  <p class="lede">Religious Jews already ask AI models everyday halachic questions. HashkafaBench measures which way
  each model leans, machmir or maikel, in seven areas of halacha.</p>
  <dl class="facts">
    <div><dt>Questions</dt><dd>288 everyday questions, asked in English as an Ashkenazi Jew</dd></div>
    <div><dt>Judge</dt><dd>Claude Opus 5.5; GPT-6 Astra re-graded 15% (91% exact agreement)</dd></div>
    <div><dt>Data</dt><dd>Results of 6 November 2026, <a href="https://github.com/halachabench/hashkafa-bench-results">on GitHub</a></dd></div>
  </dl>
</section>
<div class="wrap">
{provisional_note('hashkafa')}
<section class="block">
<h2 class="sec-title">Overall stringency</h2>
{stringency_strip(K)}
<p class="fig-note">Adjusted stringency from a mixed model (model and question), Opus judge. Claude Fable 5.2 was
added on 9 November, after the pre-registered comparisons, so it is exploratory and left out of the lab averages.</p>
</section>
<section class="block">
<h2 class="sec-title">Where each lab leans</h2>
<p class="section-sub">Mean rubric position in each area of halacha.</p>
{radar(K)}
</section>
<section class="block">
<h2 class="sec-title">Every model, every area</h2>
<p class="section-sub">Blue is more lenient than the midpoint, red more stringent. * exploratory.</p>
{heatmap(K)}
</section>
<section class="block prose">
<h2>What the pre-selected comparisons show</h2>
<p>21 lab-against-lab comparisons were fixed before the answers were collected, paired by question, with 95%
bootstrap intervals and Holm-corrected p-values. Only those 21 are confirmatory.</p>
<ul>
<li><strong>Claude is the most lenient lab.</strong> Claude's models average about 0.07 below GPT, Gemini and Grok;
all three gaps survive correction. The largest is Claude against Grok on Shabbat (0.18).</li>
<li><strong>GPT, Gemini and Grok cannot be told apart</strong> overall.</li>
<li><strong>Bein adam lachavero: no lab difference.</strong> All four labs average 0.53 to 0.57.</li>
</ul>
<h2>More from HashkafaBench</h2>
<p><a href="/findings/poskim/">Which poskim are the models closest to?</a> Claude and the Geminis sit near R. Ovadia
Yosef and R. Shlomo Zalman Auerbach; the GPT models cluster with the Shulchan Aruch and Rema.</p>
<p><a href="/findings/sephardi-asker/">Tell the AI you're Sephardi.</a> Rulings get {abs(sp['diff']):.2f} more
lenient on average ({sp['more_lenient']} questions more lenient, {sp['more_stringent']} stricter), almost all in ritual
law, where the traditions differ.</p>
<h2>Limits</h2>
<p>One answer per model per question. Most questions were kept because an earlier panel of models disagreed on them,
so the bank is built to find differences, not to be a random sample. Rubric positions are not yet reviewed by rabbis.
The question bank and answers are not published, to keep them out of training data.
<a href="https://github.com/halachabench/hashkafa-bench-results/tree/main/data">Every table as CSV</a>.</p>
</section>
</div>"""
    page("/hashkafabench/", "HashkafaBench", body,
         desc="Which way do AI models lean on everyday halachic questions? Stringency by model, lab and area of halacha.",
         image="/assets/hashkafa/labs-radar.png", active="/hashkafabench/")


def build_values(V):
    h = V["headline"]
    ballots = "".join(f"""<article class="ballot-card"><h3>{e(b['q'])}</h3>{ballot(b['ruling'], 'ruling')}{ballot(b['itself'], 'itself')}
<p>{e(b['note'])}</p></article>""" for b in V["ballots"])
    posted = datetime.strptime(V["posted"], "%Y-%m-%d").date()
    body = f"""
<section class="page-head wrap">
  <h1>AI knows the halacha. Its own choices land elsewhere.</h1>
  <p class="lede">We asked {V['models_n']} AI models {V['questions_n']} everyday bein adam lachavero questions twice:
  once for a halachic ruling, and once as "you're in this situation, what would you do?", with no mention of Judaism.</p>
  <dl class="facts">
    <div><dt>Grader</dt><dd>{e(V['grader'])}, against the halachic rubric</dd></div>
    <div><dt>Published</dt><dd>{fmt_date(posted)}, <a href="{e(V['x'])}">thread on X</a></dd></div>
  </dl>
</section>
<div class="wrap">
<section class="block versus">
  <div><b>{h['asked_twice_same']:.0%}</b><p>Ask the same halachic question twice: the same ruling. A full flip from
  yes to no: {h['asked_twice_flip']:.0%}.</p></div>
  <div class="vs-2"><b>{h['own_vs_ruling_same']:.0%}</b><p>Compare its ruling with what it would do itself: the same
  answer. A full flip: {h['own_vs_ruling_flip']:.0%}.</p></div>
</section>
<section class="block">
<h2 class="sec-title">Every model drifts from its own ruling</h2>
<p class="section-sub">How far each model's own choice sits from its halachic ruling, against the noise of asking the
halachic question twice.</p>
{dumbbells(V)}
</section>
<section class="block">
<h2 class="sec-title">Six questions, two answers</h2>
<p class="section-sub">Each circle is one of the {V['models_n']} models.
<span class="key-inline"><i class="full"></i>yes</span><span class="key-inline"><i class="half"></i>in between, or only with a condition</span><span class="key-inline"><i class="empty"></i>no</span></p>
<div class="ballots">{ballots}</div>
</section>
<section class="block prose">
<h2>The pattern</h2>
<p>The models' own values put honesty and consent first. Halacha puts dignity, peace and honor first, and lets the
literal truth give way to peace. It isn't that AI is more lenient or stricter: it runs on a different moral system.</p>
<h2>How it was kept blind</h2>
<p>No Jewish or religious terms appear in any "what would you do?" question (a Shabbat meal became a dinner party),
and a probe confirmed no model was told who was asking. One answer per question each way.</p>
<h2>Next</h2>
<p>Questions where Jewish and secular Western ethics are known to disagree, to see which side each model's own values
fall on.</p>
</section>
</div>"""
    page("/values/", "Halacha vs. own values", body,
         desc="AI models give the halachic ruling, then decide differently for themselves. 13 models, 53 bein adam lachavero questions.",
         image="/assets/img/beinadam-personal-gap.png", active="/values/")


def build_findings(F):
    rows = "".join(finding_row(f) for f in F)
    studies = sorted({f["study"] for f in F})
    chips = "".join(f'<button type="button" data-study="{e(s)}" aria-pressed="false">{e(s)}</button>' for s in studies)
    page("/findings/", "Findings", f"""
<section class="page-head wrap"><h1>Findings</h1>
<p class="lede">Every result we have published, newest first, each with the data behind it.</p></section>
<div class="wrap"><div class="controls"><div class="seg" role="group" aria-label="Study">
<button type="button" data-study="" aria-pressed="true">All</button>{chips}</div></div>
<ol class="f-list big" id="findings">{rows}</ol></div>""",
         desc="Every HalachaBench and HashkafaBench finding, newest first.", active="/findings/")
    for i, f in enumerate(F):
        newer = F[i - 1] if i > 0 else None
        older = F[i + 1] if i + 1 < len(F) else None
        x = f'<a class="plain-link" href="{e(f["x"])}">Read the thread on X</a>' if f.get("x") else ""
        pager = "".join([
            f'<a class="pg prev" href="/findings/{older["slug"]}/"><small>Older</small>{e(older["title"])}</a>' if older else "<span></span>",
            f'<a class="pg next" href="/findings/{newer["slug"]}/"><small>Newer</small>{e(newer["title"])}</a>' if newer else "<span></span>",
        ])
        page(f"/findings/{f['slug']}/", f["title"], f"""
<article class="post">
<header class="page-head wrap narrow">
<p class="crumbs"><a href="/findings/">Findings</a> {study_tag(f['study'])}
<time datetime="{f['date'].isoformat()}">{fmt_date(f['date'])}</time></p>
<h1>{e(f['title'])}</h1><p class="lede">{e(f['summary'])}</p>
</header>
<div class="wrap narrow prose">{f['body']}
<p class="post-links">{x}<a class="plain-link" href="{e(f.get('data', '/halachabench/'))}">See the data</a></p>
<nav class="pager" aria-label="More findings">{pager}</nav></div></article>""", desc=f["summary"],
             image=f.get("image") or "/assets/og.png", active="/findings/")


def build_method(H):
    s = H["sections"]
    bib = f"""@misc{{halachabench2026,
  title        = {{HalachaBench: AI models on real semicha exam questions}},
  author       = {{{{HalachaBench}}}},
  year         = {{2026}},
  howpublished = {{\\url{{https://{SITE['domain']}}}}},
  note         = {{v1, provisional results, {H['manifest']['stage']} bundle of {H['manifest_date'].isoformat()}}}
}}"""
    files = "".join(f"<tr><td><code>{e(k)}</code></td><td><code class='hash'>{e(v)}</code></td></tr>"
                    for k, v in H["manifest"]["files"].items())
    page("/method/", "Method", f"""
<section class="page-head wrap narrow"><h1>How the exam is run and graded</h1>
<p class="lede">Real questions, closed-book answers, rubrics sealed before grading, and a public record that any later
change can be checked against.</p></section>
<div class="wrap narrow prose">
<ol class="steps">
<li><h3>Questions</h3><p>60 questions from five Chief Rabbinate semicha papers, Cheshvan 5787.</p></li>
<li><h3>Answers</h3><p>Every model answers every question three times, in Hebrew, closed-book, each in a fresh process.</p></li>
<li><h3>Rubrics</h3><p>Drafted, critiqued and cross-reviewed by models from three labs, then sealed on 29 October 2026.</p></li>
<li><h3>Grading</h3><p>A judge model checks every criterion of every answer under one fixed protocol.</p></li>
</ol>
{markdown.markdown(s['How it works'])}
<h2>Scoring</h2>{markdown.markdown(s['Scoring'])}
<h2 id="caveats">Caveats</h2>{markdown.markdown(s['Caveats'])}
<h2 id="bundle">The proof bundle</h2>
{markdown.markdown(s['The bundle'].replace('[`bundle/`](bundle/)', '[`bundle/`](https://github.com/halachabench/halacha-bench-results/tree/main/bundle)'), extensions=['tables'])}
<h3>Current bundle hashes</h3>
<p class="fig-note">Stage {e(H['manifest']['stage'])}, created {e(H['manifest']['createdAt'])}, SHA-256.</p>
<div class="table-wrap"><table class="hashes"><tbody>{files}</tbody></table></div>
<h2 id="cite">Cite</h2>
<div class="code-block"><button type="button" class="copy" data-copy="bibtex">Copy</button><pre id="bibtex">{e(bib)}</pre></div>
</div>""", desc="How HalachaBench questions are answered, how rubrics are sealed, and how answers are graded.",
         active="/method/")


def build_about():
    page("/about/", "About", f"""
<section class="page-head wrap narrow"><h1>About HalachaBench</h1>
<p class="lede">An independent project measuring how well AI models know halacha, and how they reason when they rule.</p></section>
<div class="wrap narrow prose">
<h2>What we publish</h2>
<p>Scores, charts, statistics and the hashes that fix them. We do not publish the exam questions, the models' answers
or the rubric text, so they stay out of future training data and the test stays useful.</p>
<h2>For rabbis</h2>
<p>Rabbis are invited to review the rubrics and grade a random sample of answers. Their grades will correct the AI
scores, and the results will be called validated only if the AI judges agree with them well enough. To take part,
write to <a href="mailto:{SITE['email']}">{SITE['email']}</a>; each reviewer receives a private review packet.</p>
<h2>For researchers</h2>
<p>Approved researchers can run their own model on the exam under a written agreement and send back a submission,
which we grade with the official judge and publish marked "run by the submitter". Write to us to ask.</p>
<h2>Collaborate</h2>
<p>If you would like to help expand the test, with more papers, more models or more rabbinic review, write to
<a href="mailto:{SITE['email']}">{SITE['email']}</a>.</p>
<h2>Independence</h2>
<p>HalachaBench is not connected to or endorsed by the Chief Rabbinate of Israel or by any model developer; model names
are their owners' trademarks. Nothing here is psak, and no model's score is authority to rule on halacha.</p>
<p><a href="https://x.com/HalachaBench">@HalachaBench on X</a>. <a href="https://github.com/halachabench">github.com/halachabench</a>.</p>
</div>""", active="/about/")


def build_hebrew(H):
    page("/he/", "בעברית", f"""
<section class="page-head wrap narrow"><h1>בינה מלאכותית במבחני הסמיכה</h1></section>
<div class="wrap narrow prose he">{markdown.markdown(H['hebrew'])}
<p><a href="/halachabench/">לטבלת התוצאות המלאה (באנגלית)</a></p></div>""", lang="he",
         desc="HalachaBench בעברית: מודלים של בינה מלאכותית על שאלות אמיתיות ממבחני הסמיכה של הרבנות הראשית.")


def build_404():
    page("/404.html", "Not found", """<section class="page-head wrap narrow"><h1>Page not found</h1>
<p class="lede">That page doesn't exist. <a href="/">Go to the home page</a>.</p></section>""")


def write_csv(H, K):
    d = OUT / "data"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "halachabench-v1.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "model", "lab", "score", "ci95_low", "ci95_high", "worst_of_3", "how_it_ran", "added"])
        for m in H["models"]:
            w.writerow([m["rank"], m["name"], m["lab"], m["score"], m["lo"], m["hi"], m["worst"], m["how"], m["added"].isoformat()])
    with open(d / "hashkafabench.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "lab", "stringency", "ci95_low", "ci95_high", "exploratory"] + [k for k, _ in CATS])
        for m in K["models"]:
            w.writerow([m["name"], m["lab"], m["s"], m["lo"], m["hi"], m["exploratory"]] + [round(m["cats"][k], 4) for k, _ in CATS])


def main():
    if OUT.exists():
        for p in OUT.iterdir():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    OUT.mkdir(exist_ok=True)
    H = parse_halacha()
    H["manifest_date"] = datetime.fromisoformat(H["manifest"]["createdAt"]).date()
    K = parse_hashkafa()
    V = json.loads((CONTENT / "values.json").read_text(encoding="utf-8"))
    F = parse_findings()
    SITE["_updated"] = max([H["manifest_date"]] + [f["date"] for f in F])
    SITE["build"] = datetime.now().strftime("%Y%m%d%H%M")
    # assets
    a = OUT / "assets"
    (a / "img").mkdir(parents=True)
    (a / "hashkafa").mkdir()
    for p in STATIC.iterdir():
        shutil.copy2(p, a / p.name)
    for p in (CONTENT / "images").iterdir():
        shutil.copy2(p, a / "img" / p.name)
    for p in (HK / "charts").glob("*.png"):
        shutil.copy2(p, a / "hashkafa" / p.name)
    shutil.copy2(HB / "results.png", a / "img" / "halachabench-results.png")
    shutil.copy2(HB / "results.png", a / "og.png")
    build_home(H, K, V, F)
    build_halacha(H)
    build_hashkafa(K)
    build_values(V)
    build_findings(F)
    build_method(H)
    build_about()
    build_hebrew(H)
    build_404()
    write_csv(H, K)
    if not PREVIEW:
        (OUT / "CNAME").write_text(SITE["domain"] + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    urls = ["/", "/halachabench/", "/hashkafabench/", "/values/", "/findings/", "/method/", "/about/", "/he/"] + \
           [f"/findings/{f['slug']}/" for f in F]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"  <url><loc>https://{SITE['domain']}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    robots = ("User-agent: *\nDisallow: /\n" if PREVIEW
              else f"User-agent: *\nAllow: /\nSitemap: https://{SITE['domain']}/sitemap.xml\n")
    (OUT / "robots.txt").write_text(robots, encoding="utf-8")
    print(f"built {len(urls)} pages, {len(H['models'])} HalachaBench models, {len(K['models'])} HashkafaBench models, {len(F)} findings")


if __name__ == "__main__":
    main()
