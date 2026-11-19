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

NAV = [("/halachabench/", "HalachaBench"), ("/hashkafabench/", "HashkafaBench"),
       ("/values/", "Halacha vs. own values"), ("/findings/", "Findings"), ("/method/", "Method"),
       ("/about/", "About")]


def fmt_date(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def short_date(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}"


def page(path: str, title: str, body: str, desc: str = "", image: str = "/assets/og.png", lang: str = "en",
         active: str = "") -> None:
    full_title = f"{title} · HalachaBench" if title != "HalachaBench" else "HalachaBench: AI models on real semicha exams"
    desc = desc or SITE["description"]
    nav = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if active == href else ""}>{e(label)}</a>' for href, label in NAV)
    beacon = ""
    if SITE.get("cf_beacon_token"):
        beacon = ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                  f"data-cf-beacon='{{\"token\": \"{e(SITE['cf_beacon_token'])}\"}}'></script>")
    dir_attr = ' dir="rtl"' if lang == "he" else ""
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
<link rel="icon" type="image/png" href="/assets/favicon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Frank+Ruhl+Libre:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/style.css?v={SITE['build']}">
<script>try{{var t=localStorage.getItem('hb-theme');if(t)document.documentElement.dataset.theme=t;}}catch(_){{}}</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>{PREVIEW_BAR}
<header class="site-head">
  <div class="wrap head-row">
    <a class="brand" href="/"><img src="/assets/favicon.png" alt="" width="28" height="28"><span>HalachaBench</span></a>
    <button class="nav-toggle" aria-expanded="false" aria-controls="site-nav" aria-label="Menu"><span></span></button>
    <nav id="site-nav" class="site-nav">{nav}<a href="/he/" lang="he" class="he-link">עברית</a>
      <button class="theme-toggle" type="button" aria-label="Switch light or dark theme" title="Light / dark"></button></nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-foot">
  <div class="wrap foot-grid">
    <div>
      <a class="brand" href="/"><img src="/assets/favicon.png" alt="" width="22" height="22"><span>HalachaBench</span></a>
      <p class="muted">An independent project. Not connected to or endorsed by the Chief Rabbinate of Israel or by any
      model developer; model names are their owners' trademarks. Results are provisional and are not psak.</p>
    </div>
    <div>
      <h4>Results</h4>
      <a href="/halachabench/">HalachaBench leaderboard</a><a href="/hashkafabench/">HashkafaBench</a>
      <a href="/values/">Halacha vs. own values</a><a href="/findings/">All findings</a>
    </div>
    <div>
      <h4>Source</h4>
      <a href="https://github.com/halachabench/halacha-bench-results">halacha-bench-results</a>
      <a href="https://github.com/halachabench/hashkafa-bench-results">hashkafa-bench-results</a>
      <a href="/method/#cite">Cite</a>
    </div>
    <div>
      <h4>Contact</h4>
      <a href="mailto:{SITE['email']}">{SITE['email']}</a><a href="https://x.com/HalachaBench">@HalachaBench on X</a>
      <p class="muted small">Last updated {fmt_date(SITE['_updated'])}</p>
    </div>
  </div>
  <div class="wrap foot-legal">© {SITE['_updated'].year} {e(SITE['copyright'])}</div>
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


# --------------------------------------------------------------------------- components


def provisional_note(kind: str = "halacha") -> str:
    if kind == "halacha":
        txt = ("<strong>Provisional.</strong> One AI judge (GPT-6 Astra, itself a contestant) has graded the answers. "
               "The rubrics were written and reviewed by AI models; no rabbi has reviewed them or graded an answer yet. "
               "These are not exam grades, and a high score is not authority to pasken.")
    else:
        txt = ("<strong>Descriptive, not psak.</strong> These results describe how models answer. "
               "Rubric positions were written and source-checked by the team and AI models, not yet reviewed by rabbis, "
               "and the judges are models from the labs being compared.")
    return f'<aside class="callout"><span class="callout-icon" aria-hidden="true">!</span><p>{txt}</p></aside>'


def axis_ticks(vals, fmt, lo, hi) -> str:
    return "".join(f'<span style="left:{(v - lo) / (hi - lo) * 100:.2f}%">{fmt(v)}</span>' for v in vals)


def halacha_table(H, limit: int | None = None, controls: bool = True) -> str:
    ms = H["models"][:limit] if limit else H["models"]
    latest = max(m["added"] for m in H["models"])
    rows = []
    for m in ms:
        notes = "".join(f'<a class="fn" href="/halachabench/#note-{n}">{SUP[int(n)]}</a>' for n in m["notes"])
        new = '<span class="badge badge-new">New</span>' if m["added"] == latest and m["added_later"] else ""
        tip = (f"{m['name']} · {m['lab']}&#10;Score {m['score']:.1f} (95% interval {m['lo']:.1f}–{m['hi']:.1f})"
               f"&#10;Worst of 3 attempts: {m['worst']:.1f}&#10;{m['how']}")
        rows.append(f"""<tr data-lab="{e(m['lab'])}" data-kind="{m['kind']}">
<td class="num rank" data-v="{m['rank']}">{m['rank']}</td>
<td class="model" data-v="{e(m['name'])}">{chip(m['lab'])}<span class="mname">{e(m['name'])}</span>{notes}{new}
  <span class="mlab">{e(m['lab'])}{' · open weights, run locally' if m['kind'] == 'open' else ''}</span></td>
<td class="bar-cell" data-v="{m['score']}"><div class="bar-track" data-tip="{tip}" tabindex="0">
  <div class="bar {lab_cls(m['lab'])}" style="width:{m['score']:.2f}%"></div>
  <div class="ci" style="left:{m['lo']:.2f}%;width:{m['hi'] - m['lo']:.2f}%"></div></div></td>
<td class="num score" data-v="{m['score']}">{m['score']:.1f}</td>
<td class="num ci-txt hide-sm" data-v="{m['lo']}">{m['lo']:.1f}–{m['hi']:.1f}</td>
<td class="num hide-sm" data-v="{m['worst']}">{m['worst']:.1f}</td>
<td class="how hide-md" data-v="{e(m['how'])}">{e(m['how'])}</td>
<td class="num hide-md" data-v="{m['added'].isoformat()}">{short_date(m['added'])}</td>
</tr>""")
    ticks = axis_ticks([0, 25, 50, 75, 100], lambda v: f"{v:g}", 0, 100)
    labs = sorted({m["lab"] for m in H["models"]}, key=lambda l: (l not in LABS, l))
    ctl = ""
    if controls:
        opts = "".join(f'<option value="{e(l)}">{e(l)}</option>' for l in labs)
        ctl = f"""<div class="controls" data-for="hb-table">
  <div class="seg" role="group" aria-label="Model type">
    <button type="button" data-kind="all" aria-pressed="true">All {len(H['models'])}</button>
    <button type="button" data-kind="hosted" aria-pressed="false">Hosted</button>
    <button type="button" data-kind="open" aria-pressed="false">Open weights</button>
  </div>
  <label class="select"><span class="visually-hidden">Lab</span><select data-lab-filter>
    <option value="">All labs</option>{opts}</select></label>
  <a class="btn-ghost" href="/data/halachabench-v1.csv" download>Download CSV</a>
</div>"""
    return f"""{ctl}
<div class="table-scroll"><table class="lb" id="hb-table">
<thead><tr>
<th class="num" data-sort="num">#</th><th data-sort="text">Model</th>
<th class="bar-head"><span class="visually-hidden">Score bar</span><div class="axis">{ticks}</div></th>
<th class="num" data-sort="num" aria-sort="descending">Score</th><th class="num hide-sm" data-sort="num">95% interval</th>
<th class="num hide-sm" data-sort="num" title="Mean of each question's lowest-scoring attempt">Worst of 3</th>
<th class="hide-md" data-sort="text">How it ran</th><th class="num hide-md" data-sort="text">Added</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="legend-row">{''.join(f'<span>{chip(l)}{l}</span>' for l in LABS)}<span>{chip('Other')}Other labs</span>
<span class="legend-ci"><i></i>95% interval (bootstrap over questions)</span><span class="muted">Higher is better · 0–100</span></p>"""


def stringency_rows(K) -> str:
    rows = []
    for m in sorted(K["models"], key=lambda m: -m["s"]):
        ex = '<span class="badge">Exploratory</span>' if m["exploratory"] else ""
        tip = f"{m['name']} · {m['lab']}&#10;Stringency {m['s']:.2f} (95% CI {m['lo']:.2f}–{m['hi']:.2f})"
        rows.append(f"""<tr data-lab="{e(m['lab'])}">
<td class="model" data-v="{e(m['name'])}">{chip(m['lab'])}<span class="mname">{e(m['name'])}</span>{ex}<span class="mlab">{e(m['lab'])}</span></td>
<td class="dot-cell" data-v="{m['s']}"><div class="dot-track" data-tip="{tip}" tabindex="0">
<div class="mid"></div><div class="ci-line" style="left:{(m['lo'] - .3) / .4 * 100:.2f}%;width:{(m['hi'] - m['lo']) / .4 * 100:.2f}%"></div>
<div class="dot {lab_cls(m['lab'])}" style="left:{(m['s'] - .3) / .4 * 100:.2f}%"></div></div></td>
<td class="num score" data-v="{m['s']}">{m['s']:.2f}</td>
<td class="num hide-sm" data-v="{m['lo']}">{m['lo']:.2f}–{m['hi']:.2f}</td></tr>""")
    ticks = axis_ticks([.3, .4, .5, .6, .7], lambda v: f"{v:.1f}", .3, .7)
    return f"""<div class="table-scroll"><table class="lb lb-dots" id="hk-table">
<thead><tr><th data-sort="text">Model</th>
<th class="bar-head"><div class="axis-ends"><span>← more lenient</span><span>more stringent →</span></div><div class="axis">{ticks}</div></th>
<th class="num" data-sort="num" aria-sort="descending">Stringency</th><th class="num hide-sm" data-sort="num">95% CI</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<p class="legend-row">{''.join(f'<span>{chip(l)}{l}</span>' for l in LABS if l in {m['lab'] for m in K['models']})}
<span class="legend-ci"><i></i>95% CI</span><span class="muted">0 = most lenient position, 1 = most stringent. Neither end is "better".</span></p>"""


def div_color(v: float) -> tuple[str, str]:
    """Diverging blue (lenient) - gray - red (stringent) around 0.5, saturating at +-0.25."""
    t = max(-1.0, min(1.0, (v - .5) / .25))
    mid = (240, 239, 236)
    pole = (42, 120, 214) if t < 0 else (227, 73, 72)
    a = abs(t)
    rgb = tuple(round(mid[i] + (pole[i] - mid[i]) * a) for i in range(3))
    lum = .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
    return "#%02x%02x%02x" % rgb, ("#0b0b0b" if lum > 150 else "#ffffff")


def heatmap(K) -> str:
    head = "".join(f'<th scope="col">{e(lbl)}</th>' for _, lbl in CATS)
    body = []
    for m in sorted(K["models"], key=lambda m: -m["s"]):
        cells = []
        for k, lbl in CATS:
            v = m["cats"][k]
            bg, fg = div_color(v)
            cells.append(f'<td style="background:{bg};color:{fg}" data-tip="{e(m["name"])} · {e(lbl)}&#10;Stringency {v:.2f}" tabindex="0">{v:.2f}</td>')
        body.append(f'<tr><th scope="row">{chip(m["lab"])}{e(m["name"])}{"*" if m["exploratory"] else ""}</th>{"".join(cells)}</tr>')
    stops = "".join(f'<span style="background:{div_color(v)[0]}"></span>' for v in [.25, .3, .35, .4, .45, .5, .55, .6, .65, .7, .75])
    return f"""<div class="table-scroll"><table class="heat"><thead><tr><th></th>{head}</tr></thead>
<tbody>{''.join(body)}</tbody></table></div>
<div class="heat-legend"><span>0.25 lenient</span><div class="ramp">{stops}</div><span>0.75 stringent</span></div>"""


def dumbbells(V) -> str:
    rows = []
    for m in sorted(V["models"], key=lambda m: -m["own_vs_ruling"]):
        a, b = m["asked_twice"], m["own_vs_ruling"]
        tip = (f"{m['name']}&#10;Ruling vs. own choice: {b:.2f}&#10;Same ruling asked twice: {a:.2f}")
        rows.append(f"""<div class="db-row" data-tip="{tip}" tabindex="0"><span class="db-name">{chip(m['lab'])}{e(m['name'])}</span>
<div class="db-track"><div class="db-line" style="left:{a / .5 * 100:.2f}%;width:{(b - a) / .5 * 100:.2f}%"></div>
<div class="db-a" style="left:{a / .5 * 100:.2f}%"></div><div class="db-b" style="left:{b / .5 * 100:.2f}%"></div></div>
<span class="db-val">{b:.2f}</span></div>""")
    ticks = axis_ticks([0, .1, .2, .3, .4, .5], lambda v: f"{v:.1f}", 0, .5)
    return f"""<div class="db-legend"><span><i class="db-a-key"></i>Same halachic question asked twice (chance)</span>
<span><i class="db-b-key"></i>Its ruling vs. what it would do itself</span></div>
<div class="dumbbell">{''.join(rows)}<div class="db-row db-axis"><span></span><div class="axis">{ticks}</div><span></span></div></div>
<p class="muted small">Average distance between the two answers on each question's rubric: 0 = same answer, 1 = opposite ends.
Graded by {e(V['grader'])}.</p>"""


def ballot(counts, cls) -> str:
    y, mid, n = counts
    dots = ["full"] * y + ["half"] * mid + ["empty"] * n
    lbl = f"{y} yes" + (f" · {mid} in between" if mid else "")
    return (f'<div class="ballot {cls}"><span class="b-lbl">{"Ruling" if cls == "b-ruling" else "Itself"}</span>'
            f'<span class="dots" role="img" aria-label="{lbl}, {n} no">{"".join(f"<i class={d}></i>" for d in dots)}</span>'
            f'<span class="b-count">{lbl}</span></div>')


def finding_card(f, compact=False) -> str:
    img = f'<img src="{e(f["image"])}" alt="" loading="lazy">' if f.get("image") and not compact else ""
    return f"""<a class="card finding-card" href="/findings/{f['slug']}/">{img}
<div class="card-body"><div class="meta"><span class="tag tag-{f['study'].lower().split()[0].replace('.', '')}">{e(f['study'])}</span>
<time datetime="{f['date'].isoformat()}">{fmt_date(f['date'])}</time></div>
<h3>{e(f['title'])}</h3><p>{e(f['summary'])}</p></div></a>"""


# --------------------------------------------------------------------------- pages


def build_home(H, K, V, F):
    top = H["models"][:5]
    hk = sorted(K["models"], key=lambda m: -m["s"])
    n_hosted = sum(1 for m in H["models"] if m["kind"] == "hosted")
    lead = H["models"][0]
    mini = "".join(
        f'<li>{chip(m["lab"])}<span class="mname">{e(m["name"])}</span><span class="mini-bar"><i class="{lab_cls(m["lab"])}" style="width:{m["score"]}%"></i></span><b>{m["score"]:.1f}</b></li>'
        for m in top)
    hk_mini = "".join(
        f'<li>{chip(m["lab"])}<span class="mname">{e(m["name"])}</span><b>{m["s"]:.2f}</b></li>' for m in (hk[:2] + hk[-2:]))
    latest = "".join(finding_card(f, compact=True) for f in F[:6])
    log = "".join(f'<li><time>{short_date(u["date"])}</time><span>{md_inline(u["text"])}</span></li>'
                  for u in sorted(H["updates"], key=lambda u: u["date"], reverse=True)[:5])
    body = f"""
<section class="hero">
  <div class="wrap">
    <p class="eyebrow">Independent AI evaluation · Torah knowledge</p>
    <h1>How well do AI models know halacha?</h1>
    <p class="lede">We give AI models real semicha exam questions from Israel's Chief Rabbinate, in Hebrew, with no
    books and no internet, and grade every answer against sealed rubrics. We also measure which way their rulings
    lean, and whether they live by the halacha they give you.</p>
    <div class="cta"><a class="btn" href="/halachabench/">See the leaderboard</a><a class="btn-ghost" href="/method/">How it works</a>
      <a class="btn-ghost" href="/findings/">Findings</a></div>
    <dl class="stats">
      <div><dt>Models tested</dt><dd>{len(H['models'])}</dd></div>
      <div><dt>Semicha questions</dt><dd>60</dd></div>
      <div><dt>Attempts per question</dt><dd>3</dd></div>
      <div><dt>Top score</dt><dd>{lead['score']:.1f}</dd></div>
    </dl>
  </div>
</section>
<div class="wrap">
{provisional_note()}
<section class="studies">
  <article class="card study">
    <div class="study-head"><span class="tag tag-halachabench">HalachaBench v1</span><span class="muted small">Updated {fmt_date(H['manifest_date'])}</span></div>
    <h2><a href="/halachabench/">The semicha exam</a></h2>
    <p>60 questions from five Cheshvan 5787 Rabbinate papers. Score = share of the rubric an answer achieves, 0–100.</p>
    <ol class="mini">{mini}</ol>
    <a class="more" href="/halachabench/">Full leaderboard: {len(H['models'])} models →</a>
  </article>
  <article class="card study">
    <div class="study-head"><span class="tag tag-hashkafabench">HashkafaBench</span><span class="muted small">{len(K['models'])} models</span></div>
    <h2><a href="/hashkafabench/">Stringent or lenient?</a></h2>
    <p>Everyday questions in seven areas of halacha. Each ruling is placed between the most lenient (0) and most stringent (1) position.</p>
    <ol class="mini mini-plain">{hk_mini}</ol>
    <p class="muted small">Most stringent and most lenient models shown.</p>
    <a class="more" href="/hashkafabench/">Stringency by model and area →</a>
  </article>
  <article class="card study">
    <div class="study-head"><span class="tag tag-values">Values</span><span class="muted small">{V['models_n']} models · {V['questions_n']} questions</span></div>
    <h2><a href="/values/">Halacha vs. own values</a></h2>
    <p>Asked for a halachic ruling, then asked "what would you do?" with no mention of Judaism.</p>
    <div class="pair-stats"><div><b>{V['headline']['asked_twice_same']:.0%}</b><span>same answer when the halachic question is asked twice</span></div>
      <div><b>{V['headline']['own_vs_ruling_same']:.0%}</b><span>same answer when it decides for itself</span></div></div>
    <a class="more" href="/values/">Where the models' own values part from halacha →</a>
  </article>
</section>

<section class="split">
  <div>
    <div class="section-head"><h2>Latest findings</h2><a href="/findings/">All findings →</a></div>
    <div class="findings-grid compact">{latest}</div>
  </div>
  <aside>
    <div class="section-head"><h2>Leaderboard updates</h2></div>
    <ol class="changelog">{log}</ol>
    <div class="card trust">
      <h3>Built to be checked</h3>
      <ul class="checks">
        <li>Rubrics sealed with salted cryptographic commitments before any answer was graded</li>
        <li>Model list, questions and analysis pre-registered by hash; every later change is a recorded amendment</li>
        <li>Questions, answers and rubric text kept private so they stay out of training data</li>
        <li>Rabbis are invited to review the rubrics and grade a random sample of answers</li>
      </ul>
      <a class="more" href="/method/">Method and proof bundle →</a>
      <div class="sources-credit">
        <a class="sefaria-badge" href="https://www.sefaria.org">
          <img class="on-light" src="/assets/img/powered-by-sefaria-navy.png" alt="Powered by Sefaria" width="140" height="73">
          <img class="on-dark" src="/assets/img/powered-by-sefaria-white.png" alt="Powered by Sefaria" width="140" height="73">
        </a>
        <p>Rubric sources were checked against texts from the Sefaria library.</p>
      </div>
    </div>
  </aside>
</section>
</div>"""
    page("/", "HalachaBench", body, active="/")


def build_halacha(H):
    lead = H["models"][0]
    notes = "".join(f'<li id="note-{k}"><span class="fn-mark">{SUP[int(k)]}</span> {md_inline(v)}</li>' for k, v in sorted(H["notes"].items()))
    comp = markdown.markdown(H["comparisons"])
    log = "".join(f'<li><time>{fmt_date(u["date"])}</time><span>{md_inline(u["text"])}</span></li>'
                  for u in sorted(H["updates"], key=lambda u: u["date"], reverse=True))
    body = f"""
<section class="page-head"><div class="wrap">
  <p class="eyebrow">HalachaBench v1 · test set · provisional</p>
  <h1>The semicha exam leaderboard</h1>
  <p class="lede">{len(H['models'])} AI models answered the 60 questions of five Chief Rabbinate semicha papers from the
  Cheshvan 5787 sitting (Niddah, Chuppah v'Kiddushin, Mitzvot HaTeluyot BaAretz, Mikvaot, Tefillah u'Brachot): three
  times each, in Hebrew, closed-book. {e(lead['name'])} leads with {lead['score']:.1f}.</p>
  <p class="page-meta">Bundle {e(H['manifest']['stage'])} · updated {fmt_date(H['manifest_date'])} · judge GPT-6 Astra ·
  <a href="https://github.com/halachabench/halacha-bench-results">source data</a></p>
</div></section>
<div class="wrap">
{provisional_note()}
<section>
{halacha_table(H)}
<p class="muted small">Score: how much of the rubric an answer achieves, 0–100, averaged over 60 questions × 3 attempts.
Worst of 3: the lowest of the three attempts at each question, averaged. 95% intervals come from a bootstrap over
questions (10,000 replicates) and cover only the choice of questions, not judge or rubric error. Click a column to sort.</p>
</section>
<section class="prose">
<h2 id="apart">Which models are clearly apart?</h2>
<p>Overlapping intervals do not by themselves mean two models are tied, so models were also compared question by question:</p>
{comp}
</section>
<section class="prose">
<h2 id="notes">Notes on individual runs</h2>
<ol class="footnotes-list">{notes}</ol>
</section>
<section class="prose">
<h2 id="updates">Changelog</h2>
<ol class="changelog wide">{log}<li><time>1 November 2026</time><span>First results: {sum(1 for m in H["models"] if not m["added_later"])} models.</span></li></ol>
</section>
<section class="prose"><h2>More</h2>
<p><a href="/method/">How the exam is run and graded</a> · <a href="/findings/grok-checks/">Checks on the Grok results</a> ·
<a href="/findings/hardest-paper/">Which paper is hardest</a> · <a href="https://github.com/halachabench/halacha-bench-results/tree/main/bundle">Proof bundle on GitHub</a></p></section>
</div>"""
    page("/halachabench/", "HalachaBench leaderboard", body,
         desc=f"{len(H['models'])} AI models on real Chief Rabbinate semicha exam questions. {lead['name']} leads with {lead['score']:.1f}.",
         active="/halachabench/")


def build_hashkafa(K):
    sp = K["sephardi"]
    body = f"""
<section class="page-head"><div class="wrap">
  <p class="eyebrow">HashkafaBench · results of 6 November 2026, updated 12 November</p>
  <h1>Is your AI stringent or lenient?</h1>
  <p class="lede">Religious Jews already ask AI models everyday halachic questions. HashkafaBench measures which way
  each model leans, machmir or maikel, by area of halacha.</p>
  <p class="page-meta">{len(K['models'])} models · 288 scored questions · judge Claude Opus 5.5 ·
  <a href="https://github.com/halachabench/hashkafa-bench-results">source data</a></p>
</div></section>
<div class="wrap">
{provisional_note('hashkafa')}
<section>
<h2>Overall stringency</h2>
{stringency_rows(K)}
<p class="muted small">Adjusted stringency from a mixed model (model + question), Opus judge. * Claude Fable 5.2 was
added on 9 November, after the pre-registered comparisons, so it is exploratory and not in the lab averages.</p>
</section>
<section>
<h2>By area of halacha</h2>
<p class="section-sub">Mean rubric position per category. Blue = more lenient, red = more stringent than the midpoint.</p>
{heatmap(K)}
</section>
<section class="prose">
<h2>What the pre-selected comparisons show</h2>
<ul>
<li><strong>Claude is the most lenient lab.</strong> Claude's models average about 0.07 below GPT, Gemini and Grok
overall; all three gaps survive correction. The largest tested gap is Claude vs Grok on Shabbat (0.18).</li>
<li><strong>GPT, Gemini and Grok are not distinguishable</strong> from each other overall.</li>
<li><strong>Bein adam lachavero: no lab difference.</strong> All four labs average 0.53–0.57 on interpersonal questions.</li>
</ul>
<p>21 lab-against-lab comparisons were chosen before the answers were collected, paired by question, with 95%
bootstrap intervals and Holm-corrected p-values. Only those 21 are confirmatory; everything else is descriptive.</p>
<figure><img src="/assets/hashkafa/labs-radar.png" alt="Average stringency by lab and category, radar chart" loading="lazy">
<figcaption>Average stringency by lab and category.</figcaption></figure>
</section>
<section class="studies two">
  <a class="card study link-card" href="/findings/poskim/"><span class="tag tag-hashkafabench">Finding</span>
  <h3>Which poskim are the models closest to?</h3><p>Claude and the Geminis sit near R. Ovadia Yosef and R. Shlomo
  Zalman Auerbach; the GPT models cluster with the Shulchan Aruch, Rema and Shemiras Shabbos K'hilchasah.</p></a>
  <a class="card study link-card" href="/findings/sephardi-asker/"><span class="tag tag-hashkafabench">Finding</span>
  <h3>Tell it you're Sephardi</h3><p>Rulings get {abs(sp['overall']['diff']):.2f} more lenient on average
  ({sp['overall']['more_lenient']} questions more lenient, {sp['overall']['more_stringent']} stricter), almost all in ritual
  law, where the two traditions actually differ.</p></a>
</section>
<section class="prose">
<h2>Setup</h2>
<ul>
<li><strong>Models:</strong> 13 pre-registered, from four labs, plus Claude Fable 5.2 (exploratory). Each ran through its
maker's command-line tool with tools and web search off, one answer per question.</li>
<li><strong>Questions:</strong> 288 everyday questions in seven areas, asked in English as an Ashkenazi Jew, with no
community or denomination stated. About 250 were kept because an earlier panel of six models disagreed on them, so the
bank is built to find differences. Control questions with settled answers check knowledge and grading.</li>
<li><strong>Scoring:</strong> each question has a written rubric of positions from 0 (most lenient) to 1 (most
stringent). Primary judge: Claude Opus 5.5 on every answer; GPT-6 Astra re-graded a fixed 15% sample (91% exact
agreement). A full re-grade with Claude Fable 5.1 left all 21 pre-selected comparisons unchanged.</li>
<li><strong>Limits:</strong> one answer per model per question; questions selected for disagreement, not a random
sample; rubric positions not yet reviewed by rabbis. The question bank and answers are not published, to keep them out
of training data.</li>
</ul>
<p><a href="https://github.com/halachabench/hashkafa-bench-results/tree/main/data">All tables as CSV</a> ·
<a href="https://github.com/halachabench/hashkafa-bench-results/tree/main/charts">All charts</a></p>
</section>
</div>"""
    page("/hashkafabench/", "HashkafaBench", body,
         desc="Which way do AI models lean on everyday halachic questions? Stringency by model, lab and area of halacha.",
         image="/assets/hashkafa/labs-radar.png", active="/hashkafabench/")


def build_values(V):
    h = V["headline"]
    ballots = "".join(f"""<article class="card ballot-card"><h3>{e(b['q'])}</h3>{ballot(b['ruling'], 'b-ruling')}{ballot(b['itself'], 'b-itself')}
<p class="muted small">{e(b['note'])}</p></article>""" for b in V["ballots"])
    body = f"""
<section class="page-head"><div class="wrap">
  <p class="eyebrow">HashkafaBench follow-up · bein adam lachavero · posted {fmt_date(datetime.strptime(V['posted'], '%Y-%m-%d').date())}</p>
  <h1>AI knows the halacha. Its own choices land elsewhere.</h1>
  <p class="lede">We asked {V['models_n']} AI models {V['questions_n']} everyday bein adam lachavero questions twice: once
  for a halachic ruling, and once as "you're in this situation, what would you do?", with no mention of Judaism.</p>
  <p class="page-meta">Grader {e(V['grader'])} · <a href="{e(V['x'])}">Thread on X</a></p>
</div></section>
<div class="wrap">
<section class="big-stats">
  <div class="card"><b>{h['asked_twice_same']:.0%}</b><span>Ask the same halachic question twice: same ruling. A full yes-to-no flip: {h['asked_twice_flip']:.0%}.</span></div>
  <div class="card accent"><b>{h['own_vs_ruling_same']:.0%}</b><span>Compare its ruling with what it would do itself: same answer. A full flip: {h['own_vs_ruling_flip']:.0%}.</span></div>
</section>
<section>
<h2>Every model drifts from its own ruling</h2>
<p class="section-sub">How far each model's own choice sits from its halachic ruling, against the run-to-run noise of
asking the halachic question twice.</p>
{dumbbells(V)}
</section>
<section>
<h2>Six questions, two answers</h2>
<p class="section-sub">Each dot is one of the {V['models_n']} models. <span class="key-inline"><i class="full"></i>yes</span>
<span class="key-inline"><i class="half"></i>in between / only with a condition</span><span class="key-inline"><i class="empty"></i>no</span></p>
<div class="ballots">{ballots}</div>
</section>
<section class="prose">
<h2>The pattern</h2>
<p>The models' own values put honesty and consent first. Halacha puts dignity, peace and honor first, and lets the
literal truth give way to peace. It isn't that AI is more lenient or stricter: it runs on a different moral system.</p>
<h2>How it was kept blind</h2>
<p>No Jewish or religious terms appear in any "what would you do?" question (a Shabbat meal became a dinner party),
and a probe confirmed no model was told who was asking. One answer per question each way; {e(V['grader'])} graded
every answer against the halachic rubric.</p>
<h2>Next</h2>
<p>Questions where Jewish and secular Western ethics are known to disagree, to see which side each model's own values
fall on.</p>
</section>
</div>"""
    page("/values/", "Halacha vs. own values", body,
         desc="AI models give the halachic ruling, then decide differently for themselves. 13 models, 53 bein adam lachavero questions.",
         image="/assets/img/beinadam-personal-gap.png", active="/values/")


def build_findings(F):
    cards = "".join(finding_card(f) for f in F)
    studies = sorted({f["study"] for f in F})
    chips = "".join(f'<button type="button" data-study="{e(s)}" aria-pressed="false">{e(s)}</button>' for s in studies)
    page("/findings/", "Findings", f"""
<section class="page-head"><div class="wrap"><p class="eyebrow">Findings</p><h1>What we've found</h1>
<p class="lede">Each result we've published, with the data behind it. Newest first.</p></div></section>
<div class="wrap"><div class="controls"><div class="seg" role="group" aria-label="Study">
<button type="button" data-study="" aria-pressed="true">All</button>{chips}</div></div>
<div class="findings-grid" id="findings">{cards}</div></div>""", desc="Every HalachaBench and HashkafaBench finding, newest first.",
         active="/findings/")
    for i, f in enumerate(F):
        newer = F[i - 1] if i > 0 else None
        older = F[i + 1] if i + 1 < len(F) else None
        x = f'<a class="btn-ghost" href="{e(f["x"])}">Read the thread on X</a>' if f.get("x") else ""
        pager = "".join([
            f'<a class="pg prev" href="/findings/{older["slug"]}/"><span>Older</span>{e(older["title"])}</a>' if older else "<span></span>",
            f'<a class="pg next" href="/findings/{newer["slug"]}/"><span>Newer</span>{e(newer["title"])}</a>' if newer else "<span></span>",
        ])
        page(f"/findings/{f['slug']}/", f["title"], f"""
<article class="post">
<header class="page-head"><div class="wrap narrow">
<p class="eyebrow"><a href="/findings/">Findings</a> · <span class="tag tag-{f['study'].lower().split()[0].replace('.', '')}">{e(f['study'])}</span></p>
<h1>{e(f['title'])}</h1><p class="lede">{e(f['summary'])}</p>
<p class="page-meta"><time datetime="{f['date'].isoformat()}">{fmt_date(f['date'])}</time></p>
</div></header>
<div class="wrap narrow prose">{f['body']}
<div class="post-foot">{x}<a class="btn-ghost" href="{e(f.get('data', '/halachabench/'))}">See the data</a></div>
<nav class="pager">{pager}</nav></div></article>""", desc=f["summary"], image=f.get("image") or "/assets/og.png",
             active="/findings/")


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
<section class="page-head"><div class="wrap narrow"><p class="eyebrow">Method · HalachaBench v1</p>
<h1>How the exam is run and graded</h1>
<p class="lede">Real questions, closed-book answers, AI-written rubrics sealed before grading, and a public record that
any later change can be checked against.</p></div></section>
<div class="wrap narrow prose">
<div class="steps">
<div><b>1</b><h3>Questions</h3><p>60 questions from five Chief Rabbinate semicha papers, Cheshvan 5787.</p></div>
<div><b>2</b><h3>Answers</h3><p>Each model answers every question three times, in Hebrew, closed-book, in a fresh process.</p></div>
<div><b>3</b><h3>Rubrics</h3><p>Drafted, critiqued and cross-reviewed by three labs' models, then sealed on 29 Oct 2026.</p></div>
<div><b>4</b><h3>Grading</h3><p>A judge model checks every criterion of every answer under one fixed protocol.</p></div>
</div>
{markdown.markdown(s['How it works'])}
<h2>Scoring</h2>{markdown.markdown(s['Scoring'])}
<h2 id="caveats">Caveats</h2>{markdown.markdown(s['Caveats'])}
<h2 id="bundle">The proof bundle</h2>
{markdown.markdown(s['The bundle'].replace('[`bundle/`](bundle/)', '[`bundle/`](https://github.com/halachabench/halacha-bench-results/tree/main/bundle)'), extensions=['tables'])}
<h3>Current bundle hashes</h3>
<p class="muted small">Stage: {e(H['manifest']['stage'])} · created {e(H['manifest']['createdAt'])} · SHA-256</p>
<div class="table-scroll"><table class="hashes"><tbody>{files}</tbody></table></div>
<h2 id="cite">Cite</h2>
<div class="code-block"><button type="button" class="copy" data-copy="bibtex">Copy</button><pre id="bibtex">{e(bib)}</pre></div>
</div>""", desc="How HalachaBench questions are answered, how rubrics are sealed, and how answers are graded.",
         active="/method/")


def build_about():
    page("/about/", "About", f"""
<section class="page-head"><div class="wrap narrow"><p class="eyebrow">About</p><h1>About HalachaBench</h1>
<p class="lede">An independent project measuring how well AI models know halacha, and how they reason when they rule.</p></div></section>
<div class="wrap narrow prose">
<h2>What we publish</h2>
<p>Scores, charts, statistics and the hashes that fix them. We do not publish the exam questions, the models' answers
or the rubric text, so that they stay out of future training data and the test stays useful.</p>
<h2>For rabbis</h2>
<p>Rabbis are invited to review the rubrics and grade a random sample of answers. Their grades will correct the AI
scores, and the results will be called validated only if the AI judges agree with them well enough. To take part,
write to <a href="mailto:{SITE['email']}">{SITE['email']}</a>; each reviewer receives a private review packet.</p>
<h2>For researchers</h2>
<p>Approved researchers can run their own model on the exam under a written agreement and send back a submission,
which we grade with the official judge and publish marked "run by the submitter". Write to us to ask.</p>
<h2>Collaborate</h2>
<p>If you would like to help expand the test (more papers, more models, more rabbinic review), please reach out at
<a href="mailto:{SITE['email']}">{SITE['email']}</a>.</p>
<h2>Independence</h2>
<p>HalachaBench is not connected to or endorsed by the Chief Rabbinate of Israel or by any model developer; model names
are their owners' trademarks. Nothing here is psak, and no model's score is authority to rule on halacha.</p>
<p><a href="https://x.com/HalachaBench">@HalachaBench on X</a> · <a href="https://github.com/halachabench">github.com/halachabench</a></p>
</div>""", active="/about/")


def build_hebrew(H):
    body_md = re.sub(r"\n(?=[^\n])", " ", H["hebrew"])
    page("/he/", "בעברית", f"""
<section class="page-head"><div class="wrap narrow"><p class="eyebrow">HalachaBench</p><h1>בינה מלאכותית במבחני הסמיכה</h1></div></section>
<div class="wrap narrow prose he">{markdown.markdown(H['hebrew'])}
<p><a href="/halachabench/">לטבלת התוצאות המלאה (באנגלית)</a></p></div>""", lang="he",
         desc="HalachaBench בעברית: מודלים של בינה מלאכותית על שאלות אמיתיות ממבחני הסמיכה של הרבנות הראשית.")


def build_404():
    page("/404.html", "Not found", """<section class="page-head"><div class="wrap narrow"><h1>Page not found</h1>
<p class="lede">That page doesn't exist. <a href="/">Back to the home page</a>.</p></div></section>""")


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
    shutil.copy2(CONTENT / "images" / "avatar.png", a / "favicon.png")
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
