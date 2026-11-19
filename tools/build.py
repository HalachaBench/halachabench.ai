"""Build halachabench.ai into docs/ from PUBLIC sources only.

Sources (nothing else is read):
  ../halacha-bench-results   public repo: README results table, footnotes, updates, bundle/, results.png
  ../hashkafa-bench-results  public repo: README table, data/*.csv, charts/*.png
  content/                   this repo: findings (Markdown), values.json, images already posted on X

Usage:  python tools/build.py            (then: python tools/check_public.py)
"""
from __future__ import annotations

import csv
import hashlib
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


STALE: list[str] = []


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _sha_ok(sha: str, text: str) -> bool:
    """A translation's recorded source hash matches the current English (LF or CRLF line endings)."""
    lf = text.replace("\r\n", "\n")
    return sha in (_sha12(text), _sha12(lf), _sha12(lf.replace("\n", "\r\n")))


def parse_findings(lang: str = "en"):
    base = CONTENT / "findings"
    folder = base if lang == "en" else CONTENT / "he" / "findings"
    items = []
    for p in sorted(base.glob("*.md")):
        src = folder / p.name
        used_lang = lang
        if not src.exists():
            src, used_lang = p, "en"
            if lang == "he":
                STALE.append(f"no Hebrew translation for findings/{p.name} (English shown)")
        raw = src.read_text(encoding="utf-8").replace("\r\n", "\n")
        fm, body = raw.split("\n---\n", 1) if raw.startswith("---") else ("", raw)
        meta = {}
        for ln in fm.strip("-\n").splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip()
        if lang == "he" and used_lang == "he":
            want = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
            if meta.get("source_sha") and meta["source_sha"] != want:
                STALE.append(f"Hebrew findings/{p.name} was translated from an older English version")
        meta["slug"] = p.stem[11:] if re.match(r"\d{4}-\d\d-\d\d-", p.stem) else p.stem
        meta["date"] = datetime.strptime(meta["date"], "%Y-%m-%d").date()
        meta["body"] = markdown.markdown(body, extensions=["tables", "attr_list", "md_in_html", "footnotes"])
        meta["lang"] = used_lang
        items.append(meta)
    return sorted(items, key=lambda m: (m["date"], m.get("order", "0")), reverse=True)


# --------------------------------------------------------------------------- language

LANG = "en"
HE_MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]
CAT_HE = {"shabbat": "שבת", "yomtov": "יום טוב", "kashrut": "כשרות", "tefillah": "תפילה",
          "fasts_aveilut": "צומות ואבלות", "business": "ממונות", "bein_adam": "בין אדם לחברו"}
STUDY_HE = {"HalachaBench": "HalachaBench", "HashkafaBench": "HashkafaBench", "Values": "ערכים"}


def tr(en: str, he: str) -> str:
    return he if LANG == "he" else en


def u(path: str) -> str:
    """Site link in the current language."""
    if LANG == "he" and path.startswith("/") and not path.startswith(("/assets", "/data", "/he/")):
        return "/he" + path
    return path


def bdi(s: str) -> str:
    return f"<bdi>{s}</bdi>" if LANG == "he" else s


def fmt_date(d: date) -> str:
    return f"{d.day} ב{HE_MONTHS[d.month - 1]} {d.year}" if LANG == "he" else f"{d.day} {d.strftime('%B %Y')}"


def short_date(d: date) -> str:
    return f"{d.day}.{d.month}" if LANG == "he" else f"{d.strftime('%b')} {d.day}"


def cat_label(k: str, en: str) -> str:
    return CAT_HE[k] if LANG == "he" else en


def lab_name(lab: str) -> str:
    return tr("Other labs", "מעבדות אחרות") if lab == "Other" else lab


def nav_items():
    return [("/halachabench/", tr("Leaderboard", "טבלת התוצאות")), ("/hashkafabench/", "HashkafaBench"),
            ("/values/", tr("Halacha vs. own values", "הלכה מול ערכים")), ("/findings/", tr("Findings", "ממצאים")),
            ("/method/", tr("Method", "שיטה")), ("/about/", tr("About", "אודות"))]


# --------------------------------------------------------------------------- brand mark

ROOF = "M9 9h40.5a7.5 7.5 0 0 1 7.5 7.5V56h-8V17H9z"
BARS4 = [("m1", 19, 27, 26, 5), ("m2", 19, 35, 20, 5), ("m3", 19, 43, 14, 5), ("m4", 19, 51, 8, 5)]
BARS3 = [("m1", 20, 27, 25, 7), ("m2", 20, 38, 17, 7), ("m3", 20, 49, 9, 7)]


def mark_svg(size: int, small: bool = False, cls: str = "mark") -> str:
    """The HalachaBench mark: a hei whose full-weight left leg is the axis of a ranked bar chart."""
    bars = BARS3 if small else BARS4
    rects = "".join(f'<rect class="{c}" x="{x}" y="{y}" width="{w}" height="{h}" rx="1"/>' for c, x, y, w, h in bars)
    return (f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
            f'<path class="m0" d="{ROOF}"/><rect class="m0" x="9" y="26" width="8" height="30"/>{rects}</svg>')


# --------------------------------------------------------------------------- share cards (Open Graph images)

CARD_JOBS: list[dict] = []
CARD_DIR = ROOT / "cards"          # committed cache: one PNG per distinct card content
CARD_VERSION = "4"
CHROME = next((p for p in [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
                           Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
                           Path("/usr/bin/google-chrome"), Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
               if p.exists()), None)


def card_id(title: str, desc: str, lang: str, stat: str = "") -> str:
    return hashlib.sha256(f"{CARD_VERSION}|{lang}|{title}|{desc}|{stat}".encode("utf-8")).hexdigest()[:16]


def card_html(title: str, desc: str, lang: str, stat: str = "") -> str:
    fonts = (STATIC / "fonts").resolve().as_uri()
    rtl = lang == "he"
    face = "'Frank Ruhl Libre', 'Domitian'" if rtl else "'Domitian', 'Frank Ruhl Libre'"
    small = "'IBM Plex Sans Hebrew', 'IBM Plex Mono'" if rtl else "'IBM Plex Mono', 'IBM Plex Sans Hebrew'"
    kicker = "מבחן הסמיכה ומחקרים נלווים" if rtl else "AI models on real semicha exams"
    css = (STATIC / "fonts" / "fonts.css").read_text(encoding="utf-8").replace("/assets/fonts/", fonts + "/")
    return f"""<!doctype html><html lang="{lang}"{' dir="rtl"' if rtl else ''}><head><meta charset="utf-8"><style>{css}
html,body{{margin:0;width:1200px;height:630px;background:#f6f4ef;color:#111;overflow:hidden}}
.c{{box-sizing:border-box;width:1200px;height:630px;padding:56px 72px 52px;display:flex;flex-direction:column}}
.top{{display:flex;justify-content:space-between;align-items:center;border-bottom:3px double #111;padding-bottom:18px}}
.wm{{display:flex;align-items:center;gap:14px;font:400 38px 'Domitian',serif;letter-spacing:-.02em;direction:ltr}}
.wm b{{font-weight:400}} .wm b span{{color:#77736b}}
.mid{{display:flex;gap:48px;align-items:flex-start}} .mid>div{{flex:1;min-width:0}}
.stat{{font:400 128px/1 'Domitian',serif;letter-spacing:-.04em;color:#2a78d6;margin-top:40px;white-space:nowrap;direction:ltr}}
.k{{font:400 20px {small};color:#45423c}}
h1{{font:400 {'66px' if len(title) < 46 else '56px'}/1.1 {face};letter-spacing:-.015em;margin:44px 0 0;max-width:1000px}}
p{{font:400 27px/1.45 {face};color:#45423c;margin:22px 0 0;max-width:980px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.bot{{margin-top:auto;display:flex;gap:8px;align-items:flex-end;direction:ltr}}
.bot i{{display:block;height:10px;border-radius:2px}}
</style></head><body><div class="c">
<div class="top"><div class="wm">{mark_svg(52).replace('class="m0"', 'fill="#111"').replace('class="m1"', 'fill="#2a78d6"').replace('class="m2"', 'fill="#eb6834"').replace('class="m3"', 'fill="#1baf7a"').replace('class="m4"', 'fill="#a3459c"')}<b>HalachaBench<span>.ai</span></b></div>
<div class="k">{e(kicker)}</div></div>
<div class="mid"><div><h1>{e(title)}</h1><p>{e(desc)}</p></div>{f'<div class="stat">{e(stat)}</div>' if stat else ''}</div>
<div class="bot"><i style="width:420px;background:#2a78d6"></i><i style="width:300px;background:#eb6834"></i><i style="width:200px;background:#1baf7a"></i><i style="width:110px;background:#a3459c"></i></div>
</div></body></html>"""


def render_cards() -> None:
    """Render missing cards with headless Chrome (cached by content hash) and copy them into the site."""
    CARD_DIR.mkdir(exist_ok=True)
    tmp = ROOT / "preview-build" / "_cards" if PREVIEW else ROOT / "_cards_tmp"
    todo = [j for j in CARD_JOBS if not (CARD_DIR / f"{j['id']}.png").exists()]
    if todo and not CHROME:
        print(f"WARNING: {len(todo)} share cards need Chrome to render; those pages fall back to the default image")
    if todo and CHROME:
        import subprocess
        tmp.mkdir(parents=True, exist_ok=True)
        for j in todo:
            h = tmp / f"{j['id']}.html"
            h.write_text(card_html(j["title"], j["desc"], j["lang"], j.get("stat", "")), encoding="utf-8")
            png = tmp / f"{j['id']}.png"
            subprocess.run([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                            "--virtual-time-budget=1500", "--window-size=1200,630", f"--screenshot={png}", h.resolve().as_uri()],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            if png.exists():
                from PIL import Image
                Image.open(png).convert("RGB").crop((0, 0, 1200, 630)).save(CARD_DIR / f"{j['id']}.png", optimize=True)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"rendered {len(todo)} share cards")
    dest = OUT / "assets" / "og"
    dest.mkdir(parents=True, exist_ok=True)
    keep = set()
    for j in CARD_JOBS:
        src = CARD_DIR / f"{j['id']}.png"
        if src.exists():
            shutil.copy2(src, dest / f"{j['id']}.png")
            keep.add(src.name)
    for old in CARD_DIR.glob("*.png"):  # drop cards no page uses any more
        if old.name not in keep:
            old.unlink()


# --------------------------------------------------------------------------- page shell


def page(path: str, title: str, body: str, desc: str = "", image: str = "/assets/og.png", active: str = "", stat: str = "") -> None:
    """path is the English path; the Hebrew twin lives under /he."""
    lang = LANG
    here = u(path)
    en_path, he_path = path, ("/he" + path if path != "/404.html" else "/he/404.html")
    alt = he_path if lang == "en" else en_path
    full_title = (f"{title} | HalachaBench" if title != "HalachaBench"
                  else tr("HalachaBench: AI models on real semicha exams", "HalachaBench: בינה מלאכותית במבחני הסמיכה"))
    desc = desc or tr(SITE["description"], "HalachaBench בודק מודלים של בינה מלאכותית על שאלות אמיתיות ממבחני הסמיכה של "
                                           "הרבנות הראשית לישראל, ומודד לאיזה כיוון נוטות הפסיקות שלהם.")
    cid = card_id(title if title != "HalachaBench" else full_title, desc, lang, stat)
    if path != "/404.html":
        CARD_JOBS.append({"id": cid, "lang": lang, "title": title if title != "HalachaBench" else full_title, "desc": desc, "stat": stat})
        image = f"/assets/og/{cid}.png"
    nav = "".join(f'<a href="{u(h)}"{" aria-current=\"page\"" if active == h else ""}>{e(lbl)}</a>' for h, lbl in nav_items())
    switch = (f'<a class="lang-switch" href="{alt}" data-lang-to="{"he" if lang == "en" else "en"}" '
              f'lang="{"he" if lang == "en" else "en"}" hreflang="{"he" if lang == "en" else "en"}">'
              f'{"עברית" if lang == "en" else "English"}</a>')
    beacon = ""
    if SITE.get("cf_beacon_token"):
        beacon = ('<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                  f"data-cf-beacon='{{\"token\": \"{e(SITE['cf_beacon_token'])}\"}}'></script>")
    first_font = "frank-ruhl-libre-400-hebrew" if lang == "he" else "domitian-roman"
    fonts = (f'<link rel="preload" href="/assets/fonts/{first_font}.woff2" as="font" type="font/woff2" crossorigin>'
             f'<link rel="stylesheet" href="/assets/fonts/fonts.css?v={SITE["build"]}">')
    redirect = "" if path == "/404.html" else (
        "var p=localStorage.getItem('hb-lang'),h='" + lang + "';"
        "if(!p&&h==='en'&&/^he\\b/i.test((navigator.languages&&navigator.languages[0])||navigator.language||''))p='he';"
        "if(p&&p!==h&&location.search.indexOf('lang=')<0)location.replace('" + alt + "');")
    doc = f"""<!doctype html>
<html lang="{lang}"{' dir="rtl"' if lang == "he" else ""}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">{PREVIEW_META}
<link rel="canonical" href="https://{SITE['domain']}{here}">
<link rel="alternate" hreflang="en" href="https://{SITE['domain']}{en_path}">
<link rel="alternate" hreflang="he" href="https://{SITE['domain']}{he_path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="HalachaBench">
<meta property="og:locale" content="{'he_IL' if lang == 'he' else 'en_US'}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="https://{SITE['domain']}{here}">
<meta property="og:image" content="https://{SITE['domain']}{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@HalachaBench">
<meta name="theme-color" content="#f6f4ef">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
{fonts}
<link rel="stylesheet" href="/assets/style.css?v={SITE['build']}">
<script>try{{var t=localStorage.getItem('hb-theme');if(t)document.documentElement.dataset.theme=t;{redirect}}}catch(_){{}}</script>
</head>
<body>
<a class="skip" href="#main">{tr("Skip to content", "דילוג לתוכן")}</a>{PREVIEW_BAR if lang == "en" else PREVIEW_BAR.replace(
        "Private preview for the team. Not public yet, please do not share.", "תצוגה מקדימה פרטית לצוות. עדיין לא פורסם, נא לא להעביר הלאה.")}
<header class="site-head">
  <div class="wrap head-row">
    <a class="wordmark" href="{u('/')}" dir="ltr">{mark_svg(34)}HalachaBench<span>.ai</span></a>
    <button class="nav-toggle" aria-expanded="false" aria-controls="site-nav"><span class="visually-hidden">{tr("Menu", "תפריט")}</span><i></i></button>
    <nav id="site-nav" class="site-nav" aria-label="{tr('Main', 'ראשי')}">{nav}{switch}
      <button class="theme-toggle" type="button" aria-label="{tr('Switch between light and dark', 'מעבר בין מצב בהיר לכהה')}"></button></nav>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-foot">
  <div class="wrap foot-grid">
    <div class="foot-about">
      <a class="wordmark small" href="{u('/')}" dir="ltr">{mark_svg(28)}HalachaBench<span>.ai</span></a>
      <p>{tr("An independent project. Not connected to or endorsed by the Chief Rabbinate of Israel or by any model developer; model names are their owners' trademarks. Results are provisional, and nothing here is psak.",
             "מיזם עצמאי. אין לו קשר לרבנות הראשית לישראל או לחברות שמפתחות את המודלים, והוא אינו פועל מטעמן; שמות המודלים הם סימני מסחר של בעליהם. התוצאות זמניות, ואין בשום דבר כאן פסק הלכה.")}</p>
    </div>
    <nav class="foot-links" aria-label="{tr('Results', 'תוצאות')}"><h2>{tr("Results", "תוצאות")}</h2>
      <a href="{u('/halachabench/')}">{tr("Semicha exam leaderboard", "טבלת מבחן הסמיכה")}</a><a href="{u('/hashkafabench/')}">HashkafaBench</a>
      <a href="{u('/values/')}">{tr("Halacha vs. own values", "הלכה מול ערכים")}</a><a href="{u('/findings/')}">{tr("All findings", "כל הממצאים")}</a></nav>
    <nav class="foot-links" aria-label="{tr('Sources', 'מקורות')}"><h2>{tr("Sources", "מקורות")}</h2>
      <a href="https://github.com/halachabench/halacha-bench-results">{tr("Results data on GitHub", "נתוני התוצאות ב-GitHub")}</a>
      <a href="https://github.com/halachabench/hashkafa-bench-results">{tr("HashkafaBench data on GitHub", "נתוני HashkafaBench ב-GitHub")}</a>
      <a href="{u('/method/')}#cite">{tr("Cite HalachaBench", "ציטוט HalachaBench")}</a></nav>
    <nav class="foot-links" aria-label="{tr('Contact', 'יצירת קשר')}"><h2>{tr("Contact", "יצירת קשר")}</h2>
      <a href="mailto:{SITE['email']}" dir="ltr">{SITE['email']}</a><a href="https://x.com/HalachaBench">{tr("@HalachaBench on X", "‎@HalachaBench ב-X")}</a></nav>
  </div>
  <div class="wrap foot-legal"><span dir="ltr">© {SITE['_updated'].year} {e(SITE['copyright'])}</span><a class="daf-egg" href="{u('/daf/')}" data-hint="{tr('Read it as a daf', 'לקרוא כדף גמרא')}" aria-label="{tr('Read it as a daf', 'לקרוא כדף גמרא')}">{tr("2a", "ב.")}</a><span>{tr("Last updated", "עודכן לאחרונה")} {fmt_date(SITE['_updated'])}</span></div>
</footer>
<div class="tip" role="tooltip" hidden></div>
<script src="/assets/site.js?v={SITE['build']}" defer></script>
{beacon}
</body>
</html>
"""
    dest = OUT / here.strip("/") / "index.html" if here not in ("/",) else OUT / "index.html"
    if here.endswith(".html"):
        dest = OUT / here.strip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(doc, encoding="utf-8")


# --------------------------------------------------------------------------- shared pieces


def provisional_note(kind: str = "halacha") -> str:
    if kind == "halacha":
        txt = tr("<strong>Provisional.</strong> One AI judge, GPT-6 Astra, which is itself on the board, has graded every "
                 "answer. The rubrics were written and reviewed by AI models; no rabbi has reviewed them or graded an "
                 "answer yet. These are not exam grades, and a high score is not authority to pasken.",
                 "<strong>תוצאות זמניות.</strong> את כל התשובות בדק עד כה שופט ממוחשב אחד, <bdi>GPT-6 Astra</bdi>, שהוא עצמו "
                 "אחד המודלים בטבלה. המחוונים נכתבו ונבדקו בידי מודלים של בינה מלאכותית; אף רב עדיין לא עבר עליהם ואף רב "
                 "עדיין לא בדק תשובה. אין אלה ציוני מבחן, וציון גבוה אינו היתר לסמוך על מודל בפסיקת הלכה.")
    else:
        txt = tr("<strong>Descriptive, not psak.</strong> These results describe how models answer. Rubric positions "
                 "were written and source-checked by the team and AI models, not yet reviewed by rabbis, and the judges "
                 "are models from the labs being compared.",
                 "<strong>תיאור, לא פסק.</strong> התוצאות מתארות איך המודלים עונים. העמדות במחוונים נכתבו ונבדקו מול "
                 "המקורות בידי הצוות ובידי מודלים, עדיין לא בידי רבנים, והשופטים הם מודלים של אותן חברות שמושוות כאן.")
    return f'<aside class="note-provisional"><p>{txt}</p></aside>'


def lab_key() -> str:
    items = "".join(f'<li>{chip(l)}{e(l)}</li>' for l in LABS)
    return f'<ul class="lab-key">{items}<li>{chip("Other")}{lab_name("Other")}</li></ul>'


def pct(v, lo, hi) -> float:
    return (v - lo) / (hi - lo) * 100


def score_track(m, big=False, lo=0, hi=100) -> str:
    """Dot for the mean, line for the 95% interval, open diamond for worst-of-3, on a lo..hi scale (always left to right)."""
    p = lambda v: max(0.0, min(100.0, pct(v, lo, hi)))
    worst = "" if big else f'<i class="worst" style="left:{p(m["worst"]):.2f}%"></i>'
    return (f'<span class="track{" big" if big else ""}"><i class="ci" style="left:{p(m["lo"]):.2f}%;'
            f'width:{p(m["hi"]) - p(m["lo"]):.2f}%"></i>{worst}<i class="dot {lab_cls(m["lab"])}" style="left:{p(m["score"]):.2f}%">'
            f'</i></span>')


def axis(vals, fmt, lo, hi, cls="axis") -> str:
    return f'<span class="{cls}" aria-hidden="true">' + "".join(
        f'<span style="left:{pct(v, lo, hi):.2f}%">{fmt(v)}</span>' for v in vals) + "</span>"


def nl(s: str) -> str:
    """Tooltip line break."""
    return "&#10;" + s


# --------------------------------------------------------------------------- HalachaBench charts


def leaderboard(H) -> str:
    latest = max(m["added"] for m in H["models"])
    rows = []
    for m in H["models"]:
        notes = "".join(f'<a class="fn" href="#note-{n}" aria-label="{tr("Note", "הערה")} {n}">{SUP[int(n)]}</a>' for n in m["notes"])
        new = f'<span class="new">{tr("new", "חדש")}</span>' if m["added"] == latest and m["added_later"] else ""
        tip = (f"{m['name']} ({m['lab']})" + nl(tr(f"Score {m['score']:.1f}, 95% interval {m['lo']:.1f} to {m['hi']:.1f}",
                                                 f"ציון {m['score']:.1f}, רווח סמך {m['lo']:.1f} עד {m['hi']:.1f}"))
               + nl(tr(f"Worst of 3 attempts: {m['worst']:.1f}", f"הגרוע מבין 3 הניסיונות: {m['worst']:.1f}")) + nl(m['how']))
        top = " top" if m["rank"] <= 3 else ""
        sub = m["lab"] + (tr(", open weights", ", משקלות פתוחים") if m["kind"] == "open" else "")
        rows.append(f"""<tr class="r{top}" data-lab="{e(m['lab'])}" data-kind="{m['kind']}">
<td class="rank" data-v="{m['rank']}">{m['rank']}</td>
<td class="model" data-v="{e(m['name'])}"><span class="mname">{chip(m['lab'])}<bdi>{e(m['name'])}</bdi>{notes}{new}</span>
<span class="msub">{sub}</span></td>
<td class="chart" data-v="{m['score']}" data-tip="{e(tip)}" tabindex="0">{score_track(m)}</td>
<td class="num score" data-v="{m['score']}">{m['score']:.1f}</td>
<td class="num ci-txt hide-sm" data-v="{m['lo']}"><bdi>{m['lo']:.1f}–{m['hi']:.1f}</bdi></td>
<td class="num hide-sm" data-v="{m['worst']}">{m['worst']:.1f}</td>
<td class="how hide-md" data-v="{e(m['how'])}" dir="ltr">{e(m['how'])}</td>
<td class="num added hide-md" data-v="{m['added'].isoformat()}">{short_date(m['added'])}</td>
</tr>""")
    labs = sorted({m["lab"] for m in H["models"]}, key=lambda l: (l not in LABS, l))
    opts = "".join(f'<option value="{e(l)}">{e(l)}</option>' for l in labs)
    return f"""<div class="controls" data-for="hb-table">
  <div class="seg" role="group" aria-label="{tr('Which models', 'אילו מודלים')}">
    <button type="button" data-kind="all" aria-pressed="true">{tr(f"All {len(H['models'])}", f"כל {len(H['models'])}")}</button>
    <button type="button" data-kind="hosted" aria-pressed="false">{tr("Hosted", "בענן")}</button>
    <button type="button" data-kind="open" aria-pressed="false">{tr("Open weights", "משקלות פתוחים")}</button>
  </div>
  <label class="select"><span class="visually-hidden">{tr("Lab", "חברה")}</span><select data-lab-filter><option value="">{tr("Every lab", "כל החברות")}</option>{opts}</select></label>
  <a class="plain-link csv" href="/data/halachabench-v1.csv" download>{tr("Download CSV", "הורדת CSV")}</a>
</div>
<div class="table-wrap"><table class="board" id="hb-table">
<caption class="visually-hidden">{tr("HalachaBench v1 scores, highest first", "ציוני HalachaBench v1, מהגבוה לנמוך")}</caption>
<thead><tr>
<th class="rank" data-sort="num" scope="col">#</th><th data-sort="text" scope="col">{tr("Model", "מודל")}</th>
<th class="chart" scope="col"><span class="visually-hidden">{tr("Score with 95% interval", "ציון ורווח סמך של 95%")}</span>{axis([0, 25, 50, 75, 100], lambda v: f"{v:g}", 0, 100)}</th>
<th class="num" data-sort="num" aria-sort="descending" scope="col">{tr("Score", "ציון")}</th>
<th class="num hide-sm" data-sort="num" scope="col">{tr("95% interval", "רווח סמך 95%")}</th>
<th class="num hide-sm" data-sort="num" scope="col" title="{tr("Mean of each question's lowest-scoring attempt", "ממוצע הניסיון החלש ביותר בכל שאלה")}">{tr("Worst of 3", "הגרוע מ-3")}</th>
<th class="hide-md" data-sort="text" scope="col">{tr("How it ran", "איך הורץ")}</th><th class="num hide-md" data-sort="text" scope="col">{tr("Added", "נוסף")}</th>
</tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="chart-key">{lab_key()}<p><i class="k-dot"></i>{tr("score", "ציון")} <i class="k-ci"></i>{tr("95% interval", "רווח סמך 95%")} <i class="k-worst"></i>{tr("worst of 3 attempts", "הגרוע מבין 3 הניסיונות")}</p></div>"""


def seq_color(v: float, lo=0.0, hi=100.0) -> tuple[str, str]:
    """Single-hue blue ramp (light -> dark), with ink that keeps contrast."""
    stops = [(0, (231, 238, 250)), (.25, (183, 211, 246)), (.5, (109, 167, 236)), (.75, (42, 120, 214)), (1, (16, 66, 129))]
    t = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if t <= b:
            uu = (t - a) / (b - a)
            rgb = tuple(round(ca[i] + (cb[i] - ca[i]) * uu) for i in range(3))
            break
    lum = .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
    return "#%02x%02x%02x" % rgb, ("#111111" if lum > 140 else "#ffffff")


def by_paper_table(P) -> str:
    papers = P["papers_he"] if LANG == "he" else P["papers"]
    head = "".join(f'<th scope="col">{e(p)}</th>' for p in papers)
    means = [sum(m["scores"][i] for m in P["models"]) / len(P["models"]) for i in range(len(papers))]
    body = []
    for m in P["models"]:
        cells = []
        for p, v in zip(papers, m["scores"]):
            bg, fg = seq_color(v)
            cells.append(f'<td style="background:{bg};color:{fg}" data-tip="{e(m["name"])}{nl(e(p) + ": " + str(v))}" tabindex="0">{v}</td>')
        body.append(f'<tr><th scope="row">{chip(m["lab"])}<bdi>{e(m["name"])}</bdi></th>{"".join(cells)}</tr>')
    foot = "".join(f"<td>{v:.0f}</td>" for v in means)
    return f"""<div class="table-wrap heat-wrap"><table class="heat seq">
<thead><tr><th></th>{head}</tr></thead><tbody>{''.join(body)}</tbody>
<tfoot><tr><th scope="row">{tr("Average of these 8", "ממוצע שמונת המודלים")}</th>{foot}</tr></tfoot></table></div>"""


# --------------------------------------------------------------------------- HashkafaBench charts


def stringency_strip(K) -> str:
    rows = []
    for m in sorted(K["models"], key=lambda m: -m["s"]):
        ex = f'<span class="new muted-tag">{tr("exploratory", "גישוש")}</span>' if m["exploratory"] else ""
        tip = f"{m['name']} ({m['lab']})" + nl(tr(f"Stringency {m['s']:.2f}, 95% CI {m['lo']:.2f} to {m['hi']:.2f}",
                                                  f"חומרה {m['s']:.2f}, רווח סמך {m['lo']:.2f} עד {m['hi']:.2f}"))
        rows.append(f"""<tr data-lab="{e(m['lab'])}">
<td class="model" data-v="{e(m['name'])}"><span class="mname">{chip(m['lab'])}<bdi>{e(m['name'])}</bdi>{ex}</span><span class="msub">{e(m['lab'])}</span></td>
<td class="chart" data-v="{m['s']}" data-tip="{e(tip)}" tabindex="0"><span class="track mid"><i class="ci" style="left:{pct(m['lo'], .3, .7):.2f}%;width:{pct(m['hi'], .3, .7) - pct(m['lo'], .3, .7):.2f}%"></i><i class="dot {lab_cls(m['lab'])}" style="left:{pct(m['s'], .3, .7):.2f}%"></i></span></td>
<td class="num score" data-v="{m['s']}">{m['s']:.2f}</td>
<td class="num ci-txt hide-sm" data-v="{m['lo']}"><bdi>{m['lo']:.2f}–{m['hi']:.2f}</bdi></td></tr>""")
    return f"""<div class="table-wrap"><table class="board" id="hk-table">
<caption class="visually-hidden">{tr("Stringency by model, most stringent first", "רמת החומרה לפי מודל, מהמחמיר ביותר")}</caption>
<thead><tr><th data-sort="text" scope="col">{tr("Model", "מודל")}</th>
<th class="chart" scope="col"><span class="ends" aria-hidden="true"><span>{tr("more lenient", "מקל יותר")}</span><span>{tr("more stringent", "מחמיר יותר")}</span></span>{axis([.3, .4, .5, .6, .7], lambda v: f"{v:.1f}", .3, .7)}</th>
<th class="num" data-sort="num" aria-sort="descending" scope="col">{tr("Stringency", "חומרה")}</th><th class="num hide-sm" data-sort="num" scope="col">{tr("95% CI", "רווח סמך 95%")}</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="chart-key">{lab_key()}<p>{tr("0 is the most lenient position on a question's rubric, 1 the most stringent. Neither end is better.",
                                          "0 היא העמדה המקלה ביותר במחוון של השאלה, 1 המחמירה ביותר. אף קצה אינו עדיף.")}</p></div>"""


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
    for i, (k, lbl) in enumerate(CATS):
        x, y = pt(i, hi)
        spokes += f'<line class="spoke" x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}"/>'
        lx, ly = pt(i, hi + .07)
        anchor = "middle" if abs(lx - cx) < 20 else ("start" if lx > cx else "end")
        labels += f'<text class="axis-lbl" x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}">{e(cat_label(k, lbl))}</text>'
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
            f'<circle class="vtx" cx="{x:.1f}" cy="{y:.1f}" r="4.5" data-tip="{e(lab)} {tr("average", "ממוצע")}{nl(e(cat_label(CATS[i][0], CATS[i][1])) + f": {v:.2f}")}"/>'
            for i, ((x, y), v) in enumerate(zip((pt(i, v) for i, v in enumerate(vals)), vals)))
        shapes += f'<g class="shape {lab_cls(lab)}" data-series="{e(lab)}"><polygon points="{pts}"/>{dots}</g>'
        cnt = tr(f'{len(ms)} model{"s" if len(ms) > 1 else ""}', f'{len(ms)} {"מודלים" if len(ms) > 1 else "מודל"}')
        keys += (f'<button type="button" class="key-btn" data-series="{e(lab)}" aria-pressed="true">{chip(lab)}{e(lab)}'
                 f' <span class="muted">{cnt}</span></button>')
    overlays, opts = "", ""
    for m in sorted(K["models"], key=lambda m: m["name"]):
        vals = [m["cats"][k] for k, _ in CATS]
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, v) for i, v in enumerate(vals)))
        dots = "".join(
            f'<circle class="vtx" cx="{x:.1f}" cy="{y:.1f}" r="4" data-tip="{e(m["name"])}{nl(e(cat_label(CATS[i][0], CATS[i][1])) + f": {v:.2f}")}"/>'
            for i, ((x, y), v) in enumerate(zip((pt(i, v) for i, v in enumerate(vals)), vals)))
        sid = re.sub(r"[^a-z0-9]+", "-", m["name"].lower())
        overlays += f'<g class="overlay {lab_cls(m["lab"])}" data-model="{sid}" hidden><polygon points="{pts}"/>{dots}</g>'
        opts += f'<option value="{sid}">{e(m["name"])}</option>'
    return f"""<div class="radar-block">
<svg class="radar" viewBox="0 0 520 500" role="img" aria-label="{tr('Average stringency by lab across seven areas of halacha', 'רמת החומרה הממוצעת לפי חברה בשבעה תחומי הלכה')}">
{rings}{spokes}{shapes}{overlays}{labels}</svg>
<div class="radar-side">
<p class="side-head">{tr("Labs", "חברות")}</p><div class="key-btns">{keys}</div>
<label class="select overlay-pick"><span>{tr("Add one model", "הוספת מודל אחד")}</span><select data-overlay><option value="">{tr("None", "ללא")}</option>{opts}</select></label>
<p class="muted small">{tr("Each shape is the average of a lab's pre-registered models. The middle ring is 0.5; further out is more stringent. Tap a lab to hide it.",
                          "כל צורה היא ממוצע המודלים שנרשמו מראש של אותה חברה. הטבעת האמצעית היא 0.5; ככל שהקו רחוק יותר מהמרכז, הפסיקה מחמירה יותר. הקשה על שם חברה מסתירה אותה.")}</p></div></div>"""


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
    head = "".join(f'<th scope="col">{e(cat_label(k, lbl))}</th>' for k, lbl in CATS)
    body = []
    for m in sorted(K["models"], key=lambda m: -m["s"]):
        cells = []
        for k, lbl in CATS:
            v = m["cats"][k]
            bg, fg = div_color(v)
            cells.append(f'<td style="background:{bg};color:{fg}" data-tip="{e(m["name"])}{nl(e(cat_label(k, lbl)) + f": {v:.2f}")}" tabindex="0">{v:.2f}</td>')
        body.append(f'<tr><th scope="row">{chip(m["lab"])}<bdi>{e(m["name"])}</bdi>{"*" if m["exploratory"] else ""}</th>{"".join(cells)}</tr>')
    stops = "".join(f'<span style="background:{div_color(v)[0]}"></span>' for v in [.25, .3, .35, .4, .45, .5, .55, .6, .65, .7, .75])
    return f"""<div class="table-wrap heat-wrap"><table class="heat"><thead><tr><th></th>{head}</tr></thead>
<tbody>{''.join(body)}</tbody></table></div>
<div class="ramp-key"><span>{tr("more lenient", "מקל יותר")}</span><span class="ramp">{stops}</span><span>{tr("more stringent", "מחמיר יותר")}</span></div>"""


# --------------------------------------------------------------------------- values charts


def dumbbells(V) -> str:
    rows = []
    for m in sorted(V["models"], key=lambda m: -m["own_vs_ruling"]):
        a, b = m["asked_twice"], m["own_vs_ruling"]
        tip = m["name"] + nl(tr(f"Ruling vs. its own choice: {b:.2f}", f"פסיקה מול בחירה אישית: {b:.2f}")) + \
            nl(tr(f"Same ruling asked twice: {a:.2f}", f"אותה שאלה הלכתית פעמיים: {a:.2f}"))
        rows.append(f"""<li data-tip="{e(tip)}" tabindex="0"><span class="db-name">{chip(m['lab'])}<bdi>{e(m['name'])}</bdi></span>
<span class="db-track"><i class="db-line" style="left:{a / .5 * 100:.2f}%;width:{(b - a) / .5 * 100:.2f}%"></i>
<i class="db-a" style="left:{a / .5 * 100:.2f}%"></i><i class="db-b" style="left:{b / .5 * 100:.2f}%"></i></span>
<span class="db-val">{b:.2f}</span></li>""")
    return f"""<div class="db-key"><span><i class="db-a-key"></i>{tr("The same halachic question, asked twice", "אותה שאלה הלכתית, פעמיים")}</span>
<span><i class="db-b-key"></i>{tr("Its ruling against what it would do itself", "הפסיקה שלו מול מה שהיה עושה בעצמו")}</span></div>
<ol class="dumbbell">{''.join(rows)}</ol>
<div class="db-axis">{axis([0, .1, .2, .3, .4, .5], lambda v: f"{v:.1f}", 0, .5)}</div>
<p class="fig-note">{tr(f"Average distance between the two answers on each question's rubric: 0 is the same answer, 1 is the opposite end. Graded by {e(V['grader'])}.",
                       f"המרחק הממוצע בין שתי התשובות על המחוון של כל שאלה: 0 פירושו אותה תשובה, 1 הקצה ההפוך. הבדיקה: <bdi>{e(V['grader'])}</bdi>.")}</p>"""


def ballot(counts, who) -> str:
    y, mid, n = counts
    dots = ["full"] * y + ["half"] * mid + ["empty"] * n
    lbl = tr(f"{y} yes" + (f", {mid} in between" if mid else "") + (f", {n} no" if n else ""),
             f"{y} כן" + (f", {mid} באמצע" if mid else "") + (f", {n} לא" if n else ""))
    name = (tr("Ruling", "פסיקה") if who == "ruling" else tr("Itself", "בעצמו"))
    return (f'<div class="ballot b-{who}"><span class="b-lbl">{name}</span>'
            f'<span class="dots" role="img" aria-label="{name}: {lbl}">{"".join(f"<i class={d}></i>" for d in dots)}</span>'
            f'<span class="b-count">{tr(f"{y} yes", f"{y} כן")}</span></div>')


# --------------------------------------------------------------------------- findings list


def study_tag(study: str) -> str:
    cls = {"HalachaBench": "t-hb", "HashkafaBench": "t-hk", "Values": "t-v"}.get(study, "t-hb")
    return f'<span class="tag {cls}">{e(STUDY_HE.get(study, study) if LANG == "he" else study)}</span>'


def finding_row(f, thumbs=True) -> str:
    img = (f'<img src="{e(f["image"])}" alt="" loading="lazy" width="320" height="180">'
           if thumbs and f.get("image") else "")
    lang_attr = ' lang="en" dir="ltr"' if LANG == "he" and f.get("lang") == "en" else ""
    return f"""<li class="f-row" data-study="{e(f['study'])}"><a href="{u('/findings/' + f['slug'] + '/')}">
<time datetime="{f['date'].isoformat()}">{short_date(f['date'])}</time>
<div class="f-text"{lang_attr}>{study_tag(f['study'])}<h3>{e(f['title'])}</h3><p>{e(f['summary'])}</p></div>{img}</a></li>"""


# --------------------------------------------------------------------------- finding charts (native, bilingual)

DATA = {}  # filled in main(): H, K, V, P, tokens, poskim, citations, style, sephardi


def fig(inner: str, caption: str = "", cls: str = "") -> str:
    cap = f'<figcaption>{e(caption)}</figcaption>' if caption else ""
    return f'<figure class="chart-fig {cls}">{inner}{cap}</figure>'


def mini_board(names: list[str] | None = None, lo: float = 0, hi: float = 100) -> str:
    """All models as ranked dots; the named ones are highlighted."""
    H = DATA["H"]
    hl = set(names or [])
    rows = []
    for m in H["models"]:
        on = (not hl) or m["name"] in hl
        tip = m["name"] + nl(tr(f"{m['score']:.1f} (95% interval {m['lo']:.1f} to {m['hi']:.1f})",
                                f"{m['score']:.1f} (רווח סמך {m['lo']:.1f} עד {m['hi']:.1f})"))
        rows.append(f'<li class="{"on" if on else "off"}" data-tip="{e(tip)}" tabindex="0"><span class="mb-rank">{m["rank"]}</span>'
                    f'<span class="mb-name">{chip(m["lab"])}<bdi>{e(m["name"])}</bdi></span>{score_track(m, lo=lo, hi=hi)}'
                    f'<span class="mb-score">{m["score"]:.1f}</span></li>')
    ax = axis([0, 25, 50, 75, 100], lambda v: f"{v:g}", 0, 100)
    return (f'<div class="mini-board{" has-hl" if hl else ""}"><div class="mb-axis"><span></span><span></span>{ax}<span></span></div>'
            f'<ol>{"".join(rows)}</ol></div>')


def scatter(points, xlab, ylab, logx=False, xr=None, yr=None, xticks=(), yticks=(), w=760, h=460, legend="") -> str:
    """points: dicts with x, y, label, cls (lab class or 'auth'), tip, prio (higher = label placed first).
    Labels try eight positions around their point and are dropped (tooltip only) when nothing fits."""
    L, R, T, B = 56, 24, 16, 58
    f = (lambda v: math.log10(v)) if logx else (lambda v: v)
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    x0, x1 = xr or (min(map(f, xs)), max(map(f, xs)))
    y0, y1 = yr or (min(ys), max(ys))
    px = lambda v: L + (f(v) - x0) / (x1 - x0) * (w - L - R)
    py = lambda v: T + (1 - (v - y0) / (y1 - y0)) * (h - T - B)
    g = []
    for t, lab in xticks:
        X = px(t)
        g.append(f'<line class="grid" x1="{X:.1f}" x2="{X:.1f}" y1="{T}" y2="{h - B}"/><text class="tick" x="{X:.1f}" y="{h - B + 18}" text-anchor="middle">{lab}</text>')
    for t, lab in yticks:
        Y = py(t)
        g.append(f'<line class="grid" x1="{L}" x2="{w - R}" y1="{Y:.1f}" y2="{Y:.1f}"/><text class="tick" x="{L - 8}" y="{Y + 4:.1f}" text-anchor="end">{lab}</text>')
    g.append(f'<text class="ax-lbl" x="{(L + w - R) / 2:.0f}" y="{h - 8}" text-anchor="middle">{e(xlab)}</text>')
    g.append(f'<text class="ax-lbl" transform="translate(14 {(T + h - B) / 2:.0f}) rotate(-90)" text-anchor="middle">{e(ylab)}</text>')
    pos = [(p, px(p["x"]), py(p["y"])) for p in points]
    boxes = [(X - 7, Y - 7, X + 7, Y + 7) for _, X, Y in pos]  # points are obstacles too
    dots, labels = [], []
    for p, X, Y in pos:
        shape = (f'<rect class="pt auth" x="{X - 5:.1f}" y="{Y - 5:.1f}" width="10" height="10" transform="rotate(45 {X:.1f} {Y:.1f})"/>'
                 if p["cls"] == "auth" else f'<circle class="pt {p["cls"]}" cx="{X:.1f}" cy="{Y:.1f}" r="6"/>')
        dots.append(f'<g class="pt-g" data-tip="{e(p["tip"])}" tabindex="0">{shape}<circle class="hit" cx="{X:.1f}" cy="{Y:.1f}" r="12"/></g>')
    for p, X, Y in sorted(pos, key=lambda t: -t[0].get("prio", 0)):
        tw, th = len(p["label"]) * 6.4 + 4, 14
        cands = [(X + 10, Y + 4, "start"), (X - 10, Y + 4, "end"), (X, Y - 11, "middle"), (X, Y + 19, "middle"),
                 (X + 9, Y - 8, "start"), (X - 9, Y - 8, "end"), (X + 9, Y + 16, "start"), (X - 9, Y + 16, "end")]
        for lx, ly, anchor in cands:
            bx0 = lx if anchor == "start" else (lx - tw if anchor == "end" else lx - tw / 2)
            box = (bx0, ly - th + 3, bx0 + tw, ly + 3)
            if box[0] < L - 4 or box[2] > w - 2 or box[1] < 0 or box[3] > h - B:
                continue
            if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in boxes):
                continue
            boxes.append(box)
            labels.append(f'<text class="pt-lbl{" auth-lbl" if p["cls"] == "auth" else ""}" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{e(p["label"])}</text>')
            break
    svg = (f'<svg class="scatter" viewBox="0 0 {w} {h}" role="img" aria-label="{e(ylab)} / {e(xlab)}">'
           f'{"".join(g)}{"".join(dots)}{"".join(labels)}</svg>')
    return svg + (f'<div class="chart-key">{legend}</div>' if legend else "")


def chart_tokens() -> str:
    H, T = DATA["H"], DATA["tokens"]
    pts = []
    for m in H["models"]:
        if m["name"] in T:
            t = T[m["name"]]
            approx = f"{round(t, -3):,.0f}" if t >= 1000 else f"{t:,.0f}"
            pts.append({"x": t, "y": m["score"], "label": m["name"], "cls": lab_cls(m["lab"]), "prio": m["score"],
                        "tip": m["name"] + nl(tr(f"Score {m['score']:.1f}", f"ציון {m['score']:.1f}")) +
                        nl(tr(f"About {approx} tokens per answer", f"כ-{approx} טוקנים לתשובה"))})
    xt = [(500, "500"), (1000, "1K"), (2000, "2K"), (5000, "5K"), (10000, "10K"), (20000, "20K"), (50000, "50K")]
    yt = [(v, str(v)) for v in (0, 20, 40, 60, 80, 100)]
    return scatter(pts, tr("Output tokens per answer, median (thinking included; log scale)", "טוקנים בתשובה, חציון (כולל חשיבה; סולם לוגריתמי)"),
                   tr("Score, 0 to 100", "ציון, 0 עד 100"), logx=True, xr=(math.log10(400), math.log10(90000)), yr=(0, 100),
                   xticks=xt, yticks=yt, legend=lab_key())


def chart_map(kind: str) -> str:
    rows = DATA["poskim" if kind == "poskim" else "citations"]
    pts = []
    for r in rows:
        is_model = r["kind"] == "model"
        name = r["name"]
        n = r.get("n_questions") or r.get("n")
        tip = name if is_model else name + nl(tr(f"named on {n} questions", f"מוזכר ב-{n} שאלות") if kind == "poskim"
                                              else tr(f"named {n} times", f"מוזכר {n} פעמים"))
        pts.append({"x": float(r["x"]), "y": float(r["y"]), "label": name, "cls": lab_cls(lab_of(name)) if is_model else "auth",
                    "tip": tip, "prio": 1 if not is_model else 0})
    xs, ys = [p["x"] for p in pts], [p["y"] for p in pts]
    pad = lambda a, b: (a - (b - a) * .1, b + (b - a) * .12)
    legend = (lab_key() + f'<p><svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="2" width="8" height="8" '
              f'transform="rotate(45 6 6)" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>'
              f'{tr("authority (posek or source)", "פוסק או מקור")}</p>')
    return scatter(pts, tr("First axis", "ציר ראשון"), tr("Second axis", "ציר שני"), xr=pad(min(xs), max(xs)),
                   yr=pad(min(ys), max(ys)), h=520, legend=legend)


def chart_style() -> str:
    names, M = DATA["style"]
    head = "".join(f'<th scope="col"><span>{e(n)}</span></th>' for n in names)
    vals = [v for row in M for v in row if v > 0]
    lo, hi = min(vals), max(vals)
    body = []
    for n, row in zip(names, M):
        cells = []
        for m2, v in zip(names, row):
            if v == 0:
                cells.append('<td class="diag"></td>')
                continue
            t = 1 - (v - lo) / (hi - lo)
            bg, fg = seq_color(t * 100)
            cells.append(f'<td style="background:{bg};color:{fg}" data-tip="{e(n)} / {e(m2)}{nl(f"Delta {v:.2f}")}" tabindex="0">{v:.2f}</td>')
        body.append(f'<tr><th scope="row">{chip(lab_of(n))}<bdi>{e(n)}</bdi></th>{"".join(cells)}</tr>')
    return (f'<div class="table-wrap heat-wrap"><table class="heat style-heat"><thead><tr><th></th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div><p class="fig-note">{tr("Darker means the two models write more alike (smaller Delta).", "צבע כהה יותר פירושו ששני המודלים כותבים בסגנון דומה יותר (דלתא קטנה יותר).")}</p>')


def bars_diverging(items, lo=-.2, hi=.05, fmt=lambda v: f"{v:+.2f}") -> str:
    """items: (label, value, ci_low, ci_high, significant). Zero line, bar to value, interval whiskers."""
    rows = []
    z = pct(0, lo, hi)
    for label, v, a, b, sig in items:
        x0, x1 = sorted((z, pct(v, lo, hi)))
        tip = f"{label}" + nl(f"{fmt(v)} ({tr('95% CI', 'רווח סמך')} {a:+.2f} {tr('to', 'עד')} {b:+.2f})")
        rows.append(f'<li data-tip="{e(tip)}" tabindex="0"><span class="dv-name">{e(label)}</span><span class="dv-track">'
                    f'<i class="dv-zero" style="left:{z:.2f}%"></i><i class="dv-bar{" sig" if sig else ""}" style="left:{x0:.2f}%;width:{x1 - x0:.2f}%"></i>'
                    f'<i class="dv-ci" style="left:{pct(a, lo, hi):.2f}%;width:{pct(b, lo, hi) - pct(a, lo, hi):.2f}%"></i></span>'
                    f'<span class="dv-val">{fmt(v)}</span></li>')
    return f'<ol class="diverge">{"".join(rows)}</ol>'


def chart_sephardi_shift() -> str:
    S = DATA["sephardi"]
    cats = [(cat_label(r["category"], dict(CATS).get(r["category"], r["category"])), float(r["diff"]), float(r["ci_low"]),
             float(r["ci_high"]), r["significant"] == "True") for r in S["by_category"]]
    cats.sort(key=lambda t: t[1])
    labs = {"claude": "Claude", "gpt": "GPT", "gemini": "Gemini", "grok": "Grok"}
    vend = [(labs.get(r["vendor"], r["vendor"]), float(r["diff"]), float(r["ci_low"]), float(r["ci_high"]), r["significant"] == "True")
            for r in S["by_vendor"]]
    vend.sort(key=lambda t: t[1])
    return (f'<div class="two-charts"><div><p class="chart-sub">{tr("By area of halacha", "לפי תחום הלכה")}</p>{bars_diverging(cats)}</div>'
            f'<div><p class="chart-sub">{tr("By lab", "לפי חברה")}</p>{bars_diverging(vend)}</div></div>'
            f'<p class="fig-note">{tr("Change in stringency when the asker is Sephardi (negative = more lenient). Solid bars are significant after Holm correction; lines are 95% intervals.", "השינוי ברמת החומרה כשהשואל ספרדי (שלילי = מקל יותר). עמודות מלאות מובהקות אחרי תיקון הולם; הקווים הם רווחי סמך של 95%.")}</p>')


def chart_ovadia() -> str:
    rows = DATA["sephardi"]["citations_by_vendor"]
    by = {}
    for r in rows:
        by.setdefault(r["vendor"], {})[r["asker"]] = float(r["Rav Ovadia Yosef"])
    li = []
    for v in ["Claude", "Gemini", "Grok", "GPT"]:
        if v not in by:
            continue
        a, s = by[v].get("ashkenazi", 0), by[v].get("sephardi", 0)
        li.append(f'<li data-tip="{e(v)}{nl(tr(f"Ashkenazi asker {a:.0f}%, Sephardi asker {s:.0f}%", f"שואל אשכנזי {a:.0f}%, שואל ספרדי {s:.0f}%"))}" tabindex="0">'
                  f'<span class="db-name">{chip({"Claude": "Anthropic", "Gemini": "Google", "Grok": "xAI", "GPT": "OpenAI"}[v])}{v}</span>'
                  f'<span class="db-track"><i class="db-line" style="left:{a:.2f}%;width:{s - a:.2f}%"></i><i class="db-a" style="left:{a:.2f}%"></i>'
                  f'<i class="db-b" style="left:{s:.2f}%"></i></span><span class="db-val">{s:.0f}%</span></li>')
    return (f'<div class="db-key"><span><i class="db-a-key"></i>{tr("Ashkenazi asker", "שואל אשכנזי")}</span><span><i class="db-b-key"></i>{tr("Sephardi asker", "שואל ספרדי")}</span></div>'
            f'<ol class="dumbbell">{"".join(li)}</ol><div class="db-axis">{axis([0, 25, 50, 75, 100], lambda v: f"{v:g}%", 0, 100)}</div>'
            f'<p class="fig-note">{tr("Share of answers that name R. Ovadia Yosef.", "שיעור התשובות שמזכירות את הרב עובדיה יוסף.")}</p>')


def chart_ballots() -> str:
    V = DATA["V"]
    he_v = V.get("he") or {}
    out = []
    for i, b in enumerate(V["ballots"]):
        hb = (he_v.get("ballots") or [{}] * 6)[i] if LANG == "he" else {}
        out.append(f'<article class="ballot-card"><h3>{e(hb.get("q", b["q"]))}</h3>{ballot(b["ruling"], "ruling")}{ballot(b["itself"], "itself")}</article>')
    key = (f'<p class="fig-note"><span class="key-inline"><i class="full"></i>{tr("yes", "כן")}</span><span class="key-inline"><i class="half"></i>'
           f'{tr("in between", "באמצע")}</span><span class="key-inline"><i class="empty"></i>{tr("no", "לא")}</span></p>')
    return key + f'<div class="ballots">{"".join(out)}</div>'


def render_chart(spec: str) -> str:
    name, _, arg = spec.partition(":")
    if name == "board":
        return mini_board([x.strip() for x in arg.split("|") if x.strip()] or None)
    if name == "by-paper":
        return by_paper_table(DATA["P"])
    if name == "tokens":
        return chart_tokens()
    if name in ("poskim-map", "citations-map"):
        return chart_map("poskim" if name == "poskim-map" else "citations")
    if name == "style":
        return chart_style()
    if name == "radar":
        return radar(DATA["K"])
    if name == "heatmap":
        return heatmap(DATA["K"])
    if name == "sephardi-shift":
        return chart_sephardi_shift()
    if name == "sephardi-ovadia":
        return chart_ovadia()
    if name == "ballots":
        return chart_ballots()
    if name == "dumbbells":
        return dumbbells(DATA["V"])
    raise SystemExit(f"unknown chart shortcode: {spec}")


def render_shortcodes(html_body: str) -> str:
    def sub(m):
        spec, _, cap = m.group(1).partition("||")
        return fig(render_chart(spec.strip()), html.unescape(cap.strip()))
    return re.sub(r"<p>\s*\{\{chart:(.+?)\}\}\s*</p>", sub, html_body)


# --------------------------------------------------------------------------- pages


def build_home(H, K, V, F):
    lead = H["models"][0]
    top = H["models"][:10]
    rows = "".join(f"""<li data-tip="{e(m['name'] + nl(tr(f"{m['score']:.1f} (95% interval {m['lo']:.1f} to {m['hi']:.1f})", f"{m['score']:.1f} (רווח סמך {m['lo']:.1f} עד {m['hi']:.1f})")))}" tabindex="0" style="--d:{i * 60}ms">
<span class="h-rank">{m['rank']}</span><span class="h-name"><bdi>{e(m['name'])}</bdi><small>{e(m['lab'])}</small></span>
{score_track(m, big=True, lo=50)}<span class="h-score">{m['score']:.1f}</span></li>""" for i, m in enumerate(top))
    hk = sorted(K["models"], key=lambda m: -m["s"])
    strip = "".join(f'<i class="dot {lab_cls(m["lab"])}" style="left:{pct(m["s"], .35, .6):.2f}%" data-tip="{e(m["name"])}: {m["s"]:.2f}" tabindex="0"></i>' for m in hk)
    latest = "".join(
        f'<li><a href="{u("/findings/" + f["slug"] + "/")}"><time datetime="{f["date"].isoformat()}">{short_date(f["date"])}</time>'
        f'<span{" lang=\"en\" dir=\"ltr\"" if LANG == "he" and f.get("lang") == "en" else ""}>{e(f["title"])}</span></a></li>'
        for f in F[:4])
    top3 = "".join(f'<li>{chip(m["lab"])}<bdi>{e(m["name"])}</bdi><b>{m["score"]:.1f}</b></li>' for m in H["models"][:3])
    n = len(H["models"])
    s1, s2 = V["headline"]["asked_twice_same"], V["headline"]["own_vs_ruling_same"]
    body = f"""
<section class="hero">
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <h1 class="tagline">{tr(SITE["tagline_en"], SITE["tagline_he"])}</h1>
      <p class="lede">{tr("How well do AI models know halacha? We test them on real semicha exam questions from Israel's Chief Rabbinate, in Hebrew, with no books and no internet.",
                          "כמה הלכה יודעת הבינה המלאכותית? אנחנו בוחנים אותה על שאלות אמיתיות ממבחני הסמיכה של הרבנות הראשית, בעברית, בלי ספרים ובלי אינטרנט.")}</p>
      <p class="hero-links"><a class="btn" href="{u('/halachabench/')}">{tr(f"See all {n} models", f"לכל {n} המודלים")}</a>
      <a class="plain-link" href="{u('/method/')}">{tr("How grading works", "איך בודקים")}</a></p>
    </div>
    <figure class="hero-board">
      <figcaption><span class="cap">{tr("Top ten, score out of 100", "עשרת הראשונים, ציון מתוך 100")}</span><span class="h-axis"><span></span><span></span>{axis([50, 60, 70, 80, 90, 100], lambda v: f"{v:g}", 50, 100)}<span></span></span></figcaption>
      <ol>{rows}</ol>
      <p class="fig-note">{tr("Provisional: one AI judge, no rabbi has graded yet. Lines show 95% intervals.",
                              "זמני: שופט ממוחשב אחד, ואף רב עדיין לא בדק. הקווים הם רווחי סמך של 95%.")}</p>
    </figure>
  </div>
</section>

<section class="studies wrap" aria-label="{tr('The three studies', 'שלושת המחקרים')}">
  <article>
    <h2><a href="{u('/halachabench/')}">{tr("The semicha exam", "מבחן הסמיכה")}</a></h2>
    <ol class="top3">{top3}</ol>
    <a class="plain-link" href="{u('/halachabench/')}">{tr("Leaderboard", "טבלת התוצאות")}</a>
  </article>
  <article>
    <h2><a href="{u('/hashkafabench/')}">{tr("Stringent or lenient?", "מחמיר או מקל?")}</a></h2>
    <div class="mini-strip" aria-label="{tr(f'Stringency of {len(hk)} models on one line', f'רמת החומרה של {len(hk)} מודלים על קו אחד')}"><span class="ms-track">{strip}</span>
    <span class="ms-ends"><span>{tr("lenient", "מקל")}</span><span>{tr("stringent", "מחמיר")}</span></span></div>
    <a class="plain-link" href="{u('/hashkafabench/')}">{tr("Stringency by area", "חומרה לפי תחום")}</a>
  </article>
  <article>
    <h2><a href="{u('/values/')}">{tr("Halacha vs. own values", "הלכה מול ערכים")}</a></h2>
    <div class="pair"><div><b>{s1:.0%}</b><small>{tr("same ruling, asked twice", "אותה פסיקה, פעמיים")}</small></div>
    <div><b class="b2">{s2:.0%}</b><small>{tr("ruling matches its own choice", "הפסיקה תואמת את בחירתו")}</small></div></div>
    <a class="plain-link" href="{u('/values/')}">{tr("Where they part ways", "איפה הם נפרדים")}</a>
  </article>
</section>

<section class="wrap home-lower">
  <div>
    <h2 class="sec-title">{tr("Latest findings", "ממצאים אחרונים")}</h2>
    <ol class="f-titles">{latest}</ol>
    <a class="plain-link" href="{u('/findings/')}">{tr("Every finding", "כל הממצאים")}</a>
  </div>
  <aside class="trust">
    <h2 class="sec-title">{tr("Built to be checked", "בנוי כדי שאפשר יהיה לבדוק")}</h2>
    <p>{tr("Rubrics sealed before grading, every step pre-registered, exam text kept private.",
           "המחוונים נחתמו לפני הבדיקה, כל שלב נרשם מראש, ונוסח המבחן נשאר פרטי.")} <a href="{u('/method/')}">{tr("Method", "השיטה")}</a></p>
    <a class="sefaria-badge" href="https://www.sefaria.org">
      <img class="on-light" src="/assets/img/powered-by-sefaria-navy.png" alt="Powered by Sefaria" width="132" height="69">
      <img class="on-dark" src="/assets/img/powered-by-sefaria-white.png" alt="Powered by Sefaria" width="132" height="69">
    </a>
  </aside>
</section>"""
    page("/", "HalachaBench", body, active="/", stat=f"{H['models'][0]['score']:.1f}")


HEB_LETTERS = "אבגדהוזחטי"


def build_daf(H, K, V, F):
    n = len(H["models"])
    top = H["models"][:10]
    s1, s2 = V["headline"]["asked_twice_same"], V["headline"]["own_vs_ruling_same"]
    sp = K["sephardi"]["overall"]

    def rashi_entry(m):
        place = {1: tr("First place. ", "במקום הראשון. "), 2: tr("Second. ", "שני. "), 3: tr("Third. ", "שלישי. ")}.get(m["rank"], "")
        txt = tr(f"{place}Scores {m['score']:.1f}, its 95% interval {m['lo']:.1f} to {m['hi']:.1f}.",
                 f"{place}ציונו {m['score']:.1f}, ורווח הסמך שלו בין {m['lo']:.1f} ל-{m['hi']:.1f}:")
        return (f'<span class="cm" data-tip="{e(m["name"])}{nl(m["lab"])}" tabindex="0"><b class="dh">{chip(m["lab"])}<bdi>{e(m["name"])}</bdi>.</b> '
                f'{txt}</span> ')

    rashi_top = "".join(rashi_entry(m) for m in top[:5])
    rashi_bot = "".join(rashi_entry(m) for m in top[5:]) + (
        f'<span class="cm"><b class="dh">{tr("And all of these", "וכל אלו")}.</b> '
        + tr(f"are provisional: one AI judge has graded them, and no rabbi has yet. The full table has all {n} models, with intervals and notes.",
             f"זמניים הם: שופט ממוחשב אחד בדק אותם, ועדיין לא בדק אותם רב. בטבלה המלאה כל {n} המודלים, עם רווחי סמך והערות:")
        + f' <a href="{u("/halachabench/")}">{tr("To the leaderboard", "לטבלת התוצאות")}</a></span>')

    tos_top = (
        f'<span class="cm"><b class="dh"><a href="{u("/hashkafabench/")}">{tr("Stringent or lenient", "מחמיר או מקל")}</a>.</b> '
        + tr("Asked everyday questions in seven areas of halacha, Claude's models rule most leniently, and GPT, Gemini and Grok cannot be told apart. Within one lab the spread can exceed the gap between labs.",
             "בשאלות יומיומיות בשבעה תחומי הלכה, המודלים של Claude פוסקים לקולא יותר מכולם, ובין GPT, Gemini ו-Grok אין הבדל מובהק. ובתוך חברה אחת הפער יכול לעלות על הפער שבין החברות:")
        + "</span> "
        f'<span class="cm"><b class="dh"><a href="{u("/values/")}">{tr("Halacha against its own values", "הלכה מול ערכים")}</a>.</b> '
        + tr(f"Asked the same halachic question twice, a model gives the same ruling {s1:.0%} of the time. Asked what it would do itself, it matches its own ruling only {s2:.0%} of the time.",
             f"כששואלים מודל את אותה שאלה הלכתית פעמיים, הוא פוסק אותו דבר ב-{s1:.0%} מהמקרים. כששואלים מה היה עושה בעצמו, תשובתו תואמת את פסיקתו רק ב-{s2:.0%}:")
        + "</span>")
    latest = "; ".join(f'<a href="{u("/findings/" + f["slug"] + "/")}"{" lang=\"en\" dir=\"ltr\"" if LANG == "he" and f.get("lang") == "en" else ""}>{e(f["title"])}</a>' for f in F[:4])
    tos_bot = (
        f'<span class="cm"><b class="dh"><a href="{u("/findings/sephardi-asker/")}">{tr("When the asker is Sephardi", "כשהשואל ספרדי")}</a>.</b> '
        + tr(f"rulings grow {abs(sp['diff']):.2f} more lenient on average, almost all of it in Shabbat, Yom Tov, kashrut and fasts, where the traditions differ.",
             f"הפסיקות מקלות ב-{abs(sp['diff']):.2f} בממוצע, וכמעט כל ההבדל בשבת, ביום טוב, בכשרות ובצומות, ששם המנהגים חלוקים:")
        + "</span> "
        f'<span class="cm"><b class="dh"><a href="{u("/halachabench/")}#papers">{tr("The hardest paper", "השאלון הקשה")}</a>.</b> '
        + tr("Chuppah v'Kiddushin and Niddah, for nearly every model; Mitzvot HaTeluyot BaAretz is the easiest.",
             "חופה וקידושין ונידה, כמעט לכל מודל; והקל שבהם מצוות התלויות בארץ:")
        + "</span> "
        f'<span class="cm"><b class="dh">{tr("Lately", "ולאחרונה")}.</b> {latest}{"" if F[3]["title"].rstrip().endswith((".", "?", "!")) else "."} '
        f'<a href="{u("/findings/")}">{tr("Every finding", "כל הממצאים")}</a></span>')

    notes = [(tr("The data", "הנתונים"), "https://github.com/halachabench/halacha-bench-results"),
             (tr("How it is graded", "שיטת הבדיקה"), u("/method/")),
             (tr("Proof bundle", "חבילת ההוכחות"), u("/method/") + "#bundle"),
             (tr("Cite", "ציטוט"), u("/method/") + "#cite"),
             ("@HalachaBench", "https://x.com/HalachaBench")]
    note_html = "".join(
        f'<li><span class="nm">{HEB_LETTERS[i] if LANG == "he" else "abcdefghij"[i]}</span><a href="{href}">{e(t)}</a></li>'
        for i, (t, href) in enumerate(notes))

    opener = tr("How", "כמה")
    main = tr(f"well do AI models know halacha? We gave them the real semicha exams of Israel's Chief Rabbinate: five papers of the Cheshvan 5787 sitting, in Hebrew, with no seforim and no internet, three attempts at every question. Every answer was graded against a rubric sealed before grading began, and the scores are set out here, with the measure of their doubt beside them.",
              f"הלכה יודעת הבינה המלאכותית? נתנו לה את מבחני הסמיכה האמיתיים של הרבנות הראשית לישראל: חמישה שאלונים ממועד חשוון תשפ\"ז, בעברית, בלי ספרים ובלי אינטרנט, שלושה ניסיונות לכל שאלה. כל תשובה נבדקה מול מחוון שנחתם קודם שהתחילה הבדיקה, והציונים מובאים כאן, ולצדם מידת הספק שבהם.")

    body = f"""
<section class="daf2 wrap" aria-label="{tr('Overview', 'סקירה')}">
  <header class="d-head">
    <span class="d-folio">{tr("Folio 2a", "דף ב.")}</span>
    <span class="d-masechet">HalachaBench</span>
    <span class="d-perek">{tr("Chapter one: the semicha exam", "פרק ראשון: מבחן הסמיכה")}</span>
  </header>
  <div class="d-grid">
    <aside class="d-notes" aria-label="{tr('Sources', 'מקורות')}"><p class="d-label">{tr("Sources", "מקורות")}</p><ol>{note_html}</ol></aside>
    <div class="d-main">
      <p><span class="opener">{opener}</span> {main}</p>
      <p class="d-cta"><a class="btn" href="{u('/halachabench/')}">{tr(f"See all {n} models", f"לכל {n} המודלים")}</a></p>
    </div>
    <div class="d-rashi d-cm"><p class="d-label">{tr("The scores", "הציונים")}</p><p>{rashi_top}</p></div>
    <div class="d-rashi-b d-cm"><p>{rashi_bot}</p></div>
    <div class="d-tos d-cm"><p class="d-label">{tr("The studies", "המחקרים")}</p><p>{tos_top}</p></div>
    <div class="d-tos-b d-cm"><p>{tos_bot}</p></div>
  </div>
</section>

<p class="wrap daf-back"><a class="plain-link" href="{u('/')}">{tr("Back to the regular view", "חזרה לתצוגה הרגילה")}</a></p>
<section class="wrap home-lower slim">
  <aside class="trust">
    <p>{tr("Rubrics sealed before grading, every step pre-registered, exam text kept private.",
           "המחוונים נחתמו לפני הבדיקה, כל שלב נרשם מראש, ונוסח המבחן נשאר פרטי.")} <a href="{u('/method/')}">{tr("Method", "השיטה")}</a></p>
    <a class="sefaria-badge" href="https://www.sefaria.org">
      <img class="on-light" src="/assets/img/powered-by-sefaria-navy.png" alt="Powered by Sefaria" width="132" height="69">
      <img class="on-dark" src="/assets/img/powered-by-sefaria-white.png" alt="Powered by Sefaria" width="132" height="69">
    </a>
  </aside>
</section>"""
    page("/daf/", tr("HalachaBench, as a daf", "HalachaBench, כדף גמרא"), body,
         desc=tr("The HalachaBench results set out like a page of Gemara.", "תוצאות HalachaBench, ערוכות כדף גמרא."),
         stat=f"{H['models'][0]['score']:.1f}")


def build_halacha(H):
    lead = H["models"][0]
    P = json.loads((CONTENT / "by_paper.json").read_text(encoding="utf-8"))
    he_p = CONTENT / "he" / "by_paper.he.json"
    P["papers_he"] = json.loads(he_p.read_text(encoding="utf-8"))["papers"] if he_p.exists() else P["papers"]
    notes_src = H["notes_he"] if LANG == "he" else H["notes"]
    notes = "".join(f'<li id="note-{k}"><span class="fn-mark">{SUP[int(k)]}</span>{md_inline(notes_src.get(k, v))}</li>' for k, v in sorted(H["notes"].items()))
    comp = markdown.markdown(H["sec_he"]["comparisons"] if LANG == "he" else H["comparisons"])
    upd = H["updates_he"] if LANG == "he" else {}
    log = "".join(f'<li><time>{fmt_date(u_["date"])}</time><span>{md_inline(upd.get(u_["date"].isoformat(), u_["text"]))}</span></li>'
                  for u_ in sorted(H["updates"], key=lambda u_: u_["date"], reverse=True))
    first = sum(1 for m in H["models"] if not m["added_later"])
    n = len(H["models"])
    body = f"""
<section class="page-head wrap">
  <h1>{tr("The semicha exam leaderboard", "טבלת התוצאות של מבחן הסמיכה")}</h1>
  <p class="lede">{tr(f"{n} AI models answered the 60 questions of five Chief Rabbinate semicha papers from the Cheshvan 5787 sitting: three times each, in Hebrew, closed-book. {e(lead['name'])} leads with {lead['score']:.1f}.",
                      f"{n} מודלים של בינה מלאכותית ענו על 60 השאלות של חמישה שאלוני סמיכה של הרבנות הראשית ממועד חשוון תשפ\"ז: שלוש פעמים כל אחד, בעברית, בלי ספרים ובלי אינטרנט. <bdi>{e(lead['name'])}</bdi> מוביל עם {lead['score']:.1f}.")}</p>
  <dl class="facts">
    <div><dt>{tr("Papers", "שאלונים")}</dt><dd>{tr("Niddah, Chuppah v'Kiddushin, Mitzvot HaTeluyot BaAretz, Mikvaot, Tefillah u'Brachot", "נידה, חופה וקידושין, מצוות התלויות בארץ, מקוואות, תפילה וברכות")}</dd></div>
    <div><dt>{tr("Judge", "שופט")}</dt><dd>{tr("GPT-6 Astra, effort high", "<bdi>GPT-6 Astra</bdi>, מאמץ גבוה")}</dd></div>
    <div><dt>{tr("Data", "נתונים")}</dt><dd>{tr(f"{e(H['manifest']['stage'].capitalize())} bundle of {fmt_date(H['manifest_date'])}, <a href=\"https://github.com/halachabench/halacha-bench-results\">on GitHub</a>",
                                                f"חבילת ביניים מ-{fmt_date(H['manifest_date'])}, <a href=\"https://github.com/halachabench/halacha-bench-results\">ב-GitHub</a>")}</dd></div>
  </dl>
</section>
<div class="wrap">
{provisional_note()}
<section class="block">
{leaderboard(H)}
<p class="fig-note">{tr("Score: how much of the rubric an answer achieves, 0 to 100, averaged over 60 questions and 3 attempts. Worst of 3: each question's lowest-scoring attempt, averaged. The 95% intervals come from a bootstrap over questions (10,000 replicates) and cover only the choice of questions, not judge or rubric error. Select a column heading to sort.",
                       "ציון: כמה מהמחוון התשובה משיגה, מ-0 עד 100, בממוצע על 60 שאלות ו-3 ניסיונות. הגרוע מ-3: הניסיון החלש ביותר בכל שאלה, בממוצע. רווחי הסמך (95%) מחושבים בבוטסטרפ על השאלות (10,000 חזרות) ומשקפים רק את בחירת השאלות, לא טעויות של השופט או של המחוון. לחיצה על כותרת עמודה ממיינת לפיה.")}</p>
</section>
<section class="block two-col">
  <div>
    <h2 class="sec-title" id="papers">{tr("Which paper is hardest?", "איזה שאלון הכי קשה?")}</h2>
    <p class="section-sub">{tr("Mean score per paper for the eight models scored on 1 November. Chuppah v'Kiddushin and Niddah are hardest for almost every model.",
                               "הציון הממוצע בכל שאלון לשמונת המודלים שנבדקו ב-1 בנובמבר. חופה וקידושין ונידה הם הקשים ביותר כמעט לכל מודל.")}</p>
    {by_paper_table(P)}
  </div>
</section>
<section class="block prose">
<h2 id="apart">{tr("Which models are clearly apart?", "אילו מודלים נבדלים בבירור?")}</h2>
<p>{tr("Overlapping intervals do not by themselves mean two models are tied, so models were also compared question by question.",
       "רווחי סמך חופפים אינם אומרים בעצמם ששני מודלים שקולים, ולכן המודלים הושוו גם שאלה מול שאלה.")}</p>
{comp}
</section>
<section class="block prose">
<h2 id="notes">{tr("Notes on individual runs", "הערות על הרצות מסוימות")}</h2>
<ol class="notes">{notes}</ol>
</section>
<section class="block prose">
<h2 id="updates">{tr("Changelog", "יומן שינויים")}</h2>
<ol class="changelog wide">{log}<li><time>{fmt_date(date(2026, 11, 1))}</time><span>{tr(f"First results: {first} models.", f"התוצאות הראשונות: {first} מודלים.")}</span></li></ol>
<p><a href="{u('/method/')}">{tr("How the exam is run and graded", "איך המבחן מורץ ונבדק")}</a>. <a href="{u('/findings/grok-checks/')}">{tr("Checks on the Grok results", "בדיקות על התוצאות של Grok")}</a>.</p>
</section>
</div>"""
    page("/halachabench/", tr("Semicha exam leaderboard", "טבלת מבחן הסמיכה"), body,
         desc=tr(f"{n} AI models on real Chief Rabbinate semicha exam questions. {lead['name']} leads with {lead['score']:.1f}.",
                 f"{n} מודלים של בינה מלאכותית על שאלות אמיתיות ממבחני הסמיכה של הרבנות הראשית. {lead['name']} מוביל עם {lead['score']:.1f}."),
         active="/halachabench/", stat=f"{lead['score']:.1f}")


def build_hashkafa(K):
    sp = K["sephardi"]["overall"]
    d, ml, ms_ = abs(sp['diff']), sp['more_lenient'], sp['more_stringent']
    body = f"""
<section class="page-head wrap">
  <h1>{tr("Is your AI stringent or lenient?", "הבינה המלאכותית שלך מחמירה או מקלה?")}</h1>
  <p class="lede">{tr("Religious Jews already ask AI models everyday halachic questions. HashkafaBench measures which way each model leans, machmir or maikel, in seven areas of halacha.",
                      "יהודים שומרי מצוות כבר שואלים מודלים של בינה מלאכותית שאלות הלכתיות יומיומיות. HashkafaBench מודד לאיזה כיוון נוטה כל מודל, להחמיר או להקל, בשבעה תחומי הלכה.")}</p>
  <dl class="facts">
    <div><dt>{tr("Questions", "שאלות")}</dt><dd>{tr("288 everyday questions, asked in English as an Ashkenazi Jew", "288 שאלות יומיומיות, שנשאלו באנגלית בשם יהודי אשכנזי")}</dd></div>
    <div><dt>{tr("Judge", "שופט")}</dt><dd>{tr("Claude Opus 5.5; GPT-6 Astra re-graded 15% (91% exact agreement)", "<bdi>Claude Opus 5.5</bdi>; <bdi>GPT-6 Astra</bdi> בדק מחדש 15% (התאמה מלאה ב-91%)")}</dd></div>
    <div><dt>{tr("Data", "נתונים")}</dt><dd>{tr("Results of 6 November 2026, <a href=\"https://github.com/halachabench/hashkafa-bench-results\">on GitHub</a>", "תוצאות מ-6 בנובמבר 2026, <a href=\"https://github.com/halachabench/hashkafa-bench-results\">ב-GitHub</a>")}</dd></div>
  </dl>
</section>
<div class="wrap">
{provisional_note('hashkafa')}
<section class="block">
<h2 class="sec-title">{tr("Overall stringency", "רמת החומרה הכללית")}</h2>
{stringency_strip(K)}
<p class="fig-note">{tr("Adjusted stringency from a mixed model (model and question), Opus judge. Claude Fable 5.2 was added on 9 November, after the pre-registered comparisons, so it is exploratory and left out of the lab averages.",
                       "חומרה מתוקננת ממודל מעורב (מודל ושאלה), בשיפוט Opus. <bdi>Claude Fable 5.2</bdi> נוסף ב-9 בנובמבר, אחרי ההשוואות שנרשמו מראש, ולכן הוא בגדר גישוש ואינו נכלל בממוצעי החברות.")}</p>
</section>
<section class="block">
<h2 class="sec-title">{tr("Where each lab leans", "לאן נוטה כל חברה")}</h2>
<p class="section-sub">{tr("Mean rubric position in each area of halacha.", "העמדה הממוצעת על המחוון בכל תחום הלכה.")}</p>
{radar(K)}
</section>
<section class="block">
<h2 class="sec-title">{tr("Every model, every area", "כל מודל, כל תחום")}</h2>
<p class="section-sub">{tr("Blue is more lenient than the midpoint, red more stringent. * exploratory.", "כחול מקל יותר מהאמצע, אדום מחמיר יותר. * גישוש.")}</p>
{heatmap(K)}
</section>
<section class="block prose">
<h2>{tr("What the pre-selected comparisons show", "מה מראות ההשוואות שנקבעו מראש")}</h2>
<p>{tr("21 lab-against-lab comparisons were fixed before the answers were collected, paired by question, with 95% bootstrap intervals and Holm-corrected p-values. Only those 21 are confirmatory.",
       "21 השוואות בין חברות נקבעו לפני שנאספו התשובות, בזוגות לפי שאלה, עם רווחי סמך של 95% בבוטסטרפ וערכי p מתוקנים בשיטת הולם. רק 21 ההשוואות האלה הן ממצאים מאששים.")}</p>
<ul>
<li>{tr("<strong>Claude is the most lenient lab.</strong> Claude's models average about 0.07 below GPT, Gemini and Grok; all three gaps survive correction. The largest is Claude against Grok on Shabbat (0.18).",
        "<strong>Claude היא החברה המקלה ביותר.</strong> המודלים של Claude נמוכים בכ-0.07 בממוצע מ-GPT, Gemini ו-Grok; שלושת הפערים נשארים מובהקים אחרי התיקון. הפער הגדול ביותר: Claude מול Grok בהלכות שבת (0.18).")}</li>
<li>{tr("<strong>GPT, Gemini and Grok cannot be told apart</strong> overall.", "<strong>בין GPT, Gemini ו-Grok אין הבדל מובהק</strong> בסך הכול.")}</li>
<li>{tr("<strong>Bein adam lachavero: no lab difference.</strong> All four labs average 0.53 to 0.57.", "<strong>בין אדם לחברו: אין הבדל בין החברות.</strong> הממוצע של כל ארבע החברות בין 0.53 ל-0.57.")}</li>
</ul>
<h2>{tr("More from HashkafaBench", "עוד מ-HashkafaBench")}</h2>
<p><a href="{u('/findings/poskim/')}">{tr("Which poskim are the models closest to?", "לאילו פוסקים המודלים הכי קרובים?")}</a> {tr("Claude and the Geminis sit near R. Ovadia Yosef and R. Shlomo Zalman Auerbach; the GPT models cluster with the Shulchan Aruch and Rema.",
   "Claude ומודלי Gemini קרובים להרב עובדיה יוסף ולהרב שלמה זלמן אויערבך; מודלי GPT מתקבצים ליד השולחן ערוך והרמ\"א.")}</p>
<p><a href="{u('/findings/sephardi-asker/')}">{tr("Tell the AI you're Sephardi.", "תגידו לבינה המלאכותית שאתם ספרדים.")}</a> {tr(f"Rulings get {d:.2f} more lenient on average ({ml} questions more lenient, {ms_} stricter), almost all in ritual law, where the traditions differ.",
   f"הפסיקות מקלות יותר ב-{d:.2f} בממוצע ({ml} שאלות מקלות יותר, {ms_} מחמירות יותר), כמעט כולן באיסור והיתר ובמועדים, שם המסורות באמת שונות.")}</p>
<h2>{tr("Limits", "מגבלות")}</h2>
<p>{tr("One answer per model per question. Most questions were kept because an earlier panel of models disagreed on them, so the bank is built to find differences, not to be a random sample. Rubric positions are not yet reviewed by rabbis. The question bank and answers are not published, to keep them out of training data.",
       "תשובה אחת לכל מודל בכל שאלה. רוב השאלות נבחרו משום שפאנל מוקדם של מודלים נחלק עליהן, כך שמאגר השאלות בנוי כדי למצוא הבדלים, ואינו מדגם אקראי. העמדות במחוונים עדיין לא נבדקו בידי רבנים. מאגר השאלות והתשובות אינם מתפרסמים, כדי שלא ייכנסו לנתוני האימון.")}
<a href="https://github.com/halachabench/hashkafa-bench-results/tree/main/data">{tr("Every table as CSV", "כל הטבלאות כקובצי CSV")}</a>.</p>
</section>
</div>"""
    page("/hashkafabench/", "HashkafaBench", body,
         desc=tr("Which way do AI models lean on everyday halachic questions? Stringency by model, lab and area of halacha.",
                 "לאיזה כיוון נוטים מודלים של בינה מלאכותית בשאלות הלכתיות יומיומיות? רמת החומרה לפי מודל, חברה ותחום הלכה."),
         image="/assets/hashkafa/labs-radar.png", active="/hashkafabench/")


def build_values(V):
    h = V["headline"]
    he_v = V.get("he") or {}
    bl = []
    for i, b in enumerate(V["ballots"]):
        hb = (he_v.get("ballots") or [{}] * 6)[i] if LANG == "he" else {}
        q, note = hb.get("q", b["q"]), hb.get("note", b["note"])
        bl.append(f"""<article class="ballot-card"><h3>{e(q)}</h3>{ballot(b['ruling'], 'ruling')}{ballot(b['itself'], 'itself')}<p>{e(note)}</p></article>""")
    posted = datetime.strptime(V["posted"], "%Y-%m-%d").date()
    mn, qn = V["models_n"], V["questions_n"]
    body = f"""
<section class="page-head wrap">
  <h1>{tr("AI knows the halacha. Its own choices land elsewhere.", "הבינה המלאכותית יודעת את ההלכה. הבחירות שלה נוחתות במקום אחר.")}</h1>
  <p class="lede">{tr(f'We asked {mn} AI models {qn} everyday bein adam lachavero questions twice: once for a halachic ruling, and once as "you\'re in this situation, what would you do?", with no mention of Judaism.',
                      f'שאלנו {mn} מודלים של בינה מלאכותית {qn} שאלות יומיומיות בבין אדם לחברו, פעמיים: פעם אחת כשאלה הלכתית, ופעם אחת כ"אתה במצב הזה, מה היית עושה?", בלי להזכיר יהדות.')}</p>
  <dl class="facts">
    <div><dt>{tr("Grader", "בודק")}</dt><dd>{tr(f"{e(V['grader'])}, against the halachic rubric", f"<bdi>{e(V['grader'])}</bdi>, מול המחוון ההלכתי")}</dd></div>
    <div><dt>{tr("Published", "פורסם")}</dt><dd>{fmt_date(posted)}, <a href="{e(V['x'])}">{tr("thread on X", "השרשור ב-X")}</a></dd></div>
  </dl>
</section>
<div class="wrap">
<section class="block versus">
  <div><b>{h['asked_twice_same']:.0%}</b><p>{tr(f"Ask the same halachic question twice: the same ruling. A full flip from yes to no: {h['asked_twice_flip']:.0%}.",
                                              f"שואלים את אותה שאלה הלכתית פעמיים: אותה פסיקה. היפוך מלא מכן ללא: {h['asked_twice_flip']:.0%}.")}</p></div>
  <div class="vs-2"><b>{h['own_vs_ruling_same']:.0%}</b><p>{tr(f"Compare its ruling with what it would do itself: the same answer. A full flip: {h['own_vs_ruling_flip']:.0%}.",
                                                            f"משווים את הפסיקה שלו למה שהיה עושה בעצמו: אותה תשובה. היפוך מלא: {h['own_vs_ruling_flip']:.0%}.")}</p></div>
</section>
<section class="block">
<h2 class="sec-title">{tr("Every model drifts from its own ruling", "כל המודלים סוטים מהפסיקה של עצמם")}</h2>
<p class="section-sub">{tr("How far each model's own choice sits from its halachic ruling, against the noise of asking the halachic question twice.",
                           "כמה רחוקה הבחירה האישית של כל מודל מהפסיקה ההלכתית שלו, לעומת הרעש שבשאילת אותה שאלה הלכתית פעמיים.")}</p>
{dumbbells(V)}
</section>
<section class="block">
<h2 class="sec-title">{tr("Six questions, two answers", "שש שאלות, שתי תשובות")}</h2>
<p class="section-sub">{tr(f"Each circle is one of the {mn} models.", f"כל עיגול הוא אחד מ-{mn} המודלים.")}
<span class="key-inline"><i class="full"></i>{tr("yes", "כן")}</span><span class="key-inline"><i class="half"></i>{tr("in between, or only with a condition", "באמצע, או רק בתנאי")}</span><span class="key-inline"><i class="empty"></i>{tr("no", "לא")}</span></p>
<div class="ballots">{''.join(bl)}</div>
</section>
<section class="block prose">
<h2>{tr("The pattern", "הדפוס")}</h2>
<p>{tr("The models' own values put honesty and consent first. Halacha puts dignity, peace and honor first, and lets the literal truth give way to peace. It isn't that AI is more lenient or stricter: it runs on a different moral system.",
       "בערכים של המודלים עצמם, יושר והסכמה קודמים לכול. ההלכה מעמידה בראש כבוד, שלום ויקר, ומתירה לשנות מן האמת המילולית מפני השלום. לא שהבינה המלאכותית מקלה או מחמירה יותר: היא פועלת לפי מערכת מוסרית אחרת.")}</p>
<h2>{tr("How it was kept blind", "איך נשמר העיוורון")}</h2>
<p>{tr('No Jewish or religious terms appear in any "what would you do?" question (a Shabbat meal became a dinner party), and a probe confirmed no model was told who was asking. One answer per question each way.',
       'בשאלות "מה היית עושה?" אין אף מונח יהודי או דתי (סעודת שבת הפכה לארוחת ערב עם חברים), ובדיקה אישרה שאף מודל לא ידע מי שואל. תשובה אחת לכל שאלה בכל אחד מהניסוחים.')}</p>
<h2>{tr("Next", "מה הלאה")}</h2>
<p>{tr("Questions where Jewish and secular Western ethics are known to disagree, to see which side each model's own values fall on.",
       "שאלות שבהן ידוע שהמוסר היהודי והמוסר המערבי החילוני חלוקים, כדי לראות לאיזה צד נופלים הערכים של כל מודל.")}</p>
</section>
</div>"""
    page("/values/", tr("Halacha vs. own values", "הלכה מול ערכים"), body,
         desc=tr("AI models give the halachic ruling, then decide differently for themselves. 13 models, 53 bein adam lachavero questions.",
                 "מודלים של בינה מלאכותית נותנים את הפסיקה ההלכתית, ואז מחליטים אחרת בשביל עצמם. 13 מודלים, 53 שאלות בבין אדם לחברו."),
         image="/assets/img/beinadam-personal-gap.png", active="/values/", stat=f"{h['asked_twice_same']:.0%}→{h['own_vs_ruling_same']:.0%}")


def build_findings(F):
    rows = "".join(finding_row(f) for f in F)
    studies = sorted({f["study"] for f in F})
    chips = "".join(f'<button type="button" data-study="{e(s)}" aria-pressed="false">{e(STUDY_HE.get(s, s) if LANG == "he" else s)}</button>' for s in studies)
    page("/findings/", tr("Findings", "ממצאים"), f"""
<section class="page-head wrap"><h1>{tr("Findings", "ממצאים")}</h1>
<p class="lede">{tr("Every result we have published, newest first, each with the data behind it.", "כל תוצאה שפרסמנו, מהחדשה לישנה, ולכל אחת הנתונים שמאחוריה.")}</p></section>
<div class="wrap"><div class="controls"><div class="seg" role="group" aria-label="{tr('Study', 'מחקר')}">
<button type="button" data-study="" aria-pressed="true">{tr("All", "הכול")}</button>{chips}</div></div>
<ol class="f-list big" id="findings">{rows}</ol></div>""",
         desc=tr("Every HalachaBench and HashkafaBench finding, newest first.", "כל הממצאים של HalachaBench ו-HashkafaBench, מהחדש לישן."),
         active="/findings/")
    for i, f in enumerate(F):
        newer = F[i - 1] if i > 0 else None
        older = F[i + 1] if i + 1 < len(F) else None
        x = f'<a class="plain-link" href="{e(f["x"])}">{tr("Read the thread on X", "לשרשור ב-X")}</a>' if f.get("x") else ""
        pager = "".join([
            f'<a class="pg prev" href="{u("/findings/" + older["slug"] + "/")}"><small>{tr("Older", "קודם")}</small>{e(older["title"])}</a>' if older else "<span></span>",
            f'<a class="pg next" href="{u("/findings/" + newer["slug"] + "/")}"><small>{tr("Newer", "הבא")}</small>{e(newer["title"])}</a>' if newer else "<span></span>",
        ])
        en_note = (f'<p class="lang-note">{tr("", "עמוד זה עדיין לא תורגם לעברית.")}</p>' if LANG == "he" and f.get("lang") == "en" else "")
        art_attr = ' lang="en" dir="ltr"' if LANG == "he" and f.get("lang") == "en" else ""
        data = f.get("data", "/halachabench/")
        lead = fig(render_chart(f["lead"]), "", "lead") if f.get("lead") else ""
        body_html = lead + render_shortcodes(f["body"])
        page(f"/findings/{f['slug']}/", f["title"], f"""
<article class="post"{art_attr}>
<header class="page-head wrap narrow">
<p class="crumbs"><a href="{u('/findings/')}">{tr("Findings", "ממצאים")}</a> {study_tag(f['study'])}
<time datetime="{f['date'].isoformat()}">{fmt_date(f['date'])}</time></p>{en_note}
<h1>{e(f['title'])}</h1><p class="lede">{e(f['summary'])}</p>
</header>
<div class="wrap narrow prose">{body_html}
<p class="post-links">{x}<a class="plain-link" href="{e(data if data.startswith('/he/') else u(data))}">{tr("See the data", "לנתונים")}</a></p>
<nav class="pager" aria-label="{tr('More findings', 'עוד ממצאים')}">{pager}</nav></div></article>""", desc=f["summary"],
             image=f.get("image") or "/assets/og.png", active="/findings/",
             stat=f.get("stat", ""))


def build_method(H):
    S = H["sec_he"] if LANG == "he" else {"how-it-works": H["sections"]["How it works"], "scoring": H["sections"]["Scoring"],
                                          "caveats": H["sections"]["Caveats"], "bundle": H["sections"]["The bundle"]}
    bundle_md = S["bundle"].replace("](bundle/)", "](https://github.com/halachabench/halacha-bench-results/tree/main/bundle)")
    bib = f"""@misc{{halachabench2026,
  title        = {{HalachaBench: AI models on real semicha exam questions}},
  author       = {{{{HalachaBench}}}},
  year         = {{2026}},
  howpublished = {{\\url{{https://{SITE['domain']}}}}},
  note         = {{v1, provisional results, {H['manifest']['stage']} bundle of {H['manifest_date'].isoformat()}}}
}}"""
    files = "".join(f"<tr><td><code>{e(k)}</code></td><td><code class='hash'>{e(v)}</code></td></tr>"
                    for k, v in H["manifest"]["files"].items())
    page("/method/", tr("Method", "שיטה"), f"""
<section class="page-head wrap narrow"><h1>{tr("How the exam is run and graded", "איך המבחן מורץ ונבדק")}</h1>
<p class="lede">{tr("Real questions, closed-book answers, rubrics sealed before grading, and a public record that any later change can be checked against.",
                    "שאלות אמיתיות, תשובות בלי ספרים ובלי אינטרנט, מחוונים שנחתמו לפני הבדיקה, ותיעוד פומבי שאפשר לבדוק מולו כל שינוי מאוחר.")}</p></section>
<div class="wrap narrow prose">
<ol class="steps">
<li><h3>{tr("Questions", "שאלות")}</h3><p>{tr("60 questions from five Chief Rabbinate semicha papers, Cheshvan 5787.", "60 שאלות מחמישה שאלוני סמיכה של הרבנות הראשית, חשוון תשפ\"ז.")}</p></li>
<li><h3>{tr("Answers", "תשובות")}</h3><p>{tr("Every model answers every question three times, in Hebrew, closed-book, each in a fresh process.", "כל מודל עונה על כל שאלה שלוש פעמים, בעברית, בלי ספרים ובלי אינטרנט, כל פעם בתהליך חדש.")}</p></li>
<li><h3>{tr("Rubrics", "מחוונים")}</h3><p>{tr("Drafted, critiqued and cross-reviewed by models from three labs, then sealed on 29 October 2026.", "נוסחו, נבקרו ונבדקו בידי מודלים משלוש חברות, ונחתמו ב-29 באוקטובר 2026.")}</p></li>
<li><h3>{tr("Grading", "בדיקה")}</h3><p>{tr("A judge model checks every criterion of every answer under one fixed protocol.", "מודל שופט בודק כל סעיף בכל תשובה לפי פרוטוקול קבוע אחד.")}</p></li>
</ol>
{markdown.markdown(S['how-it-works'])}
<h2>{tr("Scoring", "חישוב הציון")}</h2>{markdown.markdown(S['scoring'])}
<h2 id="caveats">{tr("Caveats", "הסתייגויות")}</h2>{markdown.markdown(S['caveats'])}
<h2 id="bundle">{tr("The proof bundle", "חבילת ההוכחות")}</h2>
{markdown.markdown(bundle_md, extensions=['tables'])}
<h3>{tr("Current bundle hashes", "הגיבובים של החבילה הנוכחית")}</h3>
<p class="fig-note">{tr(f"Stage {e(H['manifest']['stage'])}, created {e(H['manifest']['createdAt'])}, SHA-256.", f"שלב {e(H['manifest']['stage'])}, נוצרה ב-<bdi>{e(H['manifest']['createdAt'])}</bdi>, SHA-256.")}</p>
<div class="table-wrap" dir="ltr"><table class="hashes"><tbody>{files}</tbody></table></div>
<h2 id="cite">{tr("Cite", "ציטוט")}</h2>
<div class="code-block" dir="ltr"><button type="button" class="copy" data-copy="bibtex">Copy</button><pre id="bibtex">{e(bib)}</pre></div>
</div>""", desc=tr("How HalachaBench questions are answered, how rubrics are sealed, and how answers are graded.",
                   "איך המודלים עונים על שאלות HalachaBench, איך נחתמים המחוונים ואיך נבדקות התשובות."),
         active="/method/")


def build_about():
    mail = f'<a href="mailto:{SITE["email"]}" dir="ltr">{SITE["email"]}</a>'
    page("/about/", tr("About", "אודות"), f"""
<section class="page-head wrap narrow"><h1>{tr("About HalachaBench", "על HalachaBench")}</h1>
<p class="lede">{tr("An independent project measuring how well AI models know halacha, and how they reason when they rule.",
                    "מיזם עצמאי שמודד כמה הלכה יודעים מודלים של בינה מלאכותית, ואיך הם חושבים כשהם פוסקים.")}</p></section>
<div class="wrap narrow prose">
<h2>{tr("What we publish", "מה אנחנו מפרסמים")}</h2>
<p>{tr("Scores, charts, statistics and the hashes that fix them. We do not publish the exam questions, the models' answers or the rubric text, so they stay out of future training data and the test stays useful.",
       "ציונים, תרשימים, סטטיסטיקה והגיבובים שמקבעים אותם. איננו מפרסמים את שאלות המבחן, את תשובות המודלים או את נוסח המחוונים, כדי שלא ייכנסו לנתוני אימון עתידיים והמבחן יישאר שימושי.")}</p>
<h2>{tr("For rabbis", "לרבנים")}</h2>
<p>{tr(f"Rabbis are invited to review the rubrics and grade a random sample of answers. Their grades will correct the AI scores, and the results will be called validated only if the AI judges agree with them well enough. To take part, write to {mail}; each reviewer receives a private review packet.",
       f"רבנים מוזמנים לעבור על המחוונים ולבדוק מדגם אקראי של תשובות. הציונים שלהם יתקנו את ציוני הבינה המלאכותית, והתוצאות ייקראו מאומתות רק אם השופטים הממוחשבים יסכימו איתם במידה מספקת. כדי להשתתף כתבו אל {mail}; כל בודק מקבל חבילת בדיקה פרטית.")}</p>
<h2>{tr("For researchers", "לחוקרים")}</h2>
<p>{tr('Approved researchers can run their own model on the exam under a written agreement and send back a submission, which we grade with the official judge and publish marked "run by the submitter". Write to us to ask.',
       'חוקרים מאושרים יכולים להריץ את המודל שלהם על המבחן לפי הסכם בכתב ולשלוח אלינו הגשה, שנבדוק עם השופט הרשמי ונפרסם בציון "הורץ בידי המגיש". כתבו אלינו לפרטים.')}</p>
<h2>{tr("Collaborate", "שיתופי פעולה")}</h2>
<p>{tr(f"If you would like to help expand the test, with more papers, more models or more rabbinic review, write to {mail}.",
       f"מי שרוצה לעזור להרחיב את המבחן, בעוד שאלונים, בעוד מודלים או בעוד בדיקה של רבנים, מוזמן לכתוב אל {mail}.")}</p>
<h2>{tr("Independence", "עצמאות")}</h2>
<p>{tr("HalachaBench is not connected to or endorsed by the Chief Rabbinate of Israel or by any model developer; model names are their owners' trademarks. Nothing here is psak, and no model's score is authority to rule on halacha.",
       "ל-HalachaBench אין קשר לרבנות הראשית לישראל או לאף חברה שמפתחת מודלים, והוא אינו פועל מטעמן; שמות המודלים הם סימני מסחר של בעליהם. אין כאן פסק הלכה, וציון של מודל אינו היתר לפסוק על פיו.")}</p>
<p><a href="https://x.com/HalachaBench">{tr("@HalachaBench on X", "‎@HalachaBench ב-X")}</a>. <a href="https://github.com/halachabench" dir="ltr">github.com/halachabench</a>.</p>
</div>""", active="/about/")


def build_404():
    page("/404.html", tr("Not found", "הדף לא נמצא"), f"""<section class="page-head wrap narrow"><h1>{tr("Page not found", "הדף לא נמצא")}</h1>
<p class="lede">{tr("That page doesn't exist.", "הדף הזה לא קיים.")} <a href="{u('/')}">{tr("Go to the home page", "לדף הבית")}</a>.</p></section>""")


def load_hebrew(H, V):
    """Hebrew texts for README-derived sections, with a staleness check against the current English."""
    he = CONTENT / "he" / "sections"
    en_now = {"how-it-works": H["sections"]["How it works"], "scoring": H["sections"]["Scoring"],
              "caveats": H["sections"]["Caveats"], "bundle": H["sections"]["The bundle"], "comparisons": H["comparisons"]}
    H["sec_he"] = {}
    for k, en_text in en_now.items():
        p = he / f"{k}.md"
        if not p.exists():
            STALE.append(f"no Hebrew for section {k} (English shown)")
            H["sec_he"][k] = en_text
            continue
        t = p.read_text(encoding="utf-8")
        m = re.match(r"<!--\s*source_sha:\s*([0-9a-f]+)\s*-->\s*\n?", t)
        if m:
            if not _sha_ok(m.group(1), en_text):
                STALE.append(f"Hebrew section {k} was translated from an older English version")
            t = t[m.end():]
        H["sec_he"][k] = t
    def jload(name, en_text, key):
        p = he / name
        if not p.exists():
            STALE.append(f"no Hebrew {name}")
            return {}
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("source_sha") and not _sha_ok(d["source_sha"], en_text):
            STALE.append(f"Hebrew {name} was translated from an older English version")
        return d.get(key, {})
    notes_en = "\n\n".join(f"NOTE {k}: {v}" for k, v in sorted(H["notes"].items()))
    upd_en = "\n\n".join(f"UPDATE {x['date'].isoformat()}: {x['text']}" for x in H["updates"])
    H["notes_he"] = jload("notes.json", notes_en, "notes")
    H["updates_he"] = jload("updates.json", upd_en, "updates")
    vp = CONTENT / "he" / "values.he.json"
    V["he"] = json.loads(vp.read_text(encoding="utf-8")) if vp.exists() else {}


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
    global LANG
    if OUT.exists():
        for p in OUT.iterdir():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    OUT.mkdir(exist_ok=True)
    H = parse_halacha()
    H["manifest_date"] = datetime.fromisoformat(H["manifest"]["createdAt"]).date()
    K = parse_hashkafa()
    V = json.loads((CONTENT / "values.json").read_text(encoding="utf-8"))
    load_hebrew(H, V)
    P = json.loads((CONTENT / "by_paper.json").read_text(encoding="utf-8"))
    P["papers_he"] = json.loads((CONTENT / "he" / "by_paper.he.json").read_text(encoding="utf-8"))["papers"]
    rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8")))
    sty = list(csv.reader(open(HK / "data" / "style_delta.csv", encoding="utf-8")))
    DATA.update(H=H, K=K, V=V, P=P,
                tokens=json.loads((CONTENT / "tokens.json").read_text(encoding="utf-8"))["tokens"],
                poskim=rd(HK / "data" / "poskim_map.csv"), citations=rd(HK / "data" / "citations_ca.csv"),
                style=(sty[0][1:], [[float(x) for x in r[1:]] for r in sty[1:]]),
                sephardi={"by_category": rd(HK / "data" / "sephardi" / "by_category.csv"),
                          "by_vendor": rd(HK / "data" / "sephardi" / "by_vendor.csv"),
                          "citations_by_vendor": rd(HK / "data" / "sephardi" / "citations_by_vendor.csv")})
    FL = {"en": parse_findings("en"), "he": parse_findings("he")}
    SITE["_updated"] = max([H["manifest_date"]] + [f["date"] for f in FL["en"]])
    SITE["build"] = datetime.now().strftime("%Y%m%d%H%M")
    a = OUT / "assets"
    (a / "img").mkdir(parents=True)
    (a / "hashkafa").mkdir()
    for p in STATIC.iterdir():
        shutil.copytree(p, a / p.name) if p.is_dir() else shutil.copy2(p, a / p.name)
    for p in (CONTENT / "images").iterdir():
        shutil.copy2(p, a / "img" / p.name)
    for p in (HK / "charts").glob("*.png"):
        shutil.copy2(p, a / "hashkafa" / p.name)
    shutil.copy2(HB / "results.png", a / "img" / "halachabench-results.png")
    shutil.copy2(HB / "results.png", a / "og.png")
    for LANG in ("en", "he"):
        F = FL[LANG]
        build_home(H, K, V, F)
        build_daf(H, K, V, F)
        build_halacha(H)
        build_hashkafa(K)
        build_values(V)
        build_findings(F)
        build_method(H)
        build_about()
        build_404()
    LANG = "en"
    render_cards()
    write_csv(H, K)
    if not PREVIEW:
        (OUT / "CNAME").write_text(SITE["domain"] + "\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    base = ["/", "/daf/", "/halachabench/", "/hashkafabench/", "/values/", "/findings/", "/method/", "/about/"] + \
           [f"/findings/{f['slug']}/" for f in FL["en"]]
    urls = base + ["/he" + x for x in base]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
        "".join(f"  <url><loc>https://{SITE['domain']}{x}</loc></url>\n" for x in urls) + "</urlset>\n", encoding="utf-8")
    robots = ("User-agent: *\nDisallow: /\n" if PREVIEW
              else f"User-agent: *\nAllow: /\nSitemap: https://{SITE['domain']}/sitemap.xml\n")
    (OUT / "robots.txt").write_text(robots, encoding="utf-8")
    print(f"built {len(urls)} pages ({len(base)} per language), {len(H['models'])} HalachaBench models, "
          f"{len(K['models'])} HashkafaBench models, {len(FL['en'])} findings")
    for w in STALE:
        print("TRANSLATION:", w)


if __name__ == "__main__":
    main()
