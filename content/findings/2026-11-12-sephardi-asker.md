---
title: Tell the AI you're Sephardi
date: 2026-11-12
study: HashkafaBench
summary: The models carry a detailed map of where Sephardi practice departs from Ashkenazi practice, and apply it when told who is asking: more lenient overall, but only where the traditions differ.
x: https://x.com/HalachaBench/status/2121001334379851866
image: /assets/hashkafa/sephardi-overlay-radar.png
data: /hashkafabench/
---

The same 13 models answered the question bank a second time with one line of the prompt changed: "The person asking is
Sephardi. Where Ashkenazi and Sephardi practice differ, rule for Sephardi practice."

![Same questions, same models, asker changed](/assets/hashkafa/sephardi-overlay-radar.png)

- **The Sephardi asker gets more lenient rulings overall:** mean stringency 0.064 lower (95% CI 0.045 to 0.083). More
  lenient on 239 questions, stricter on 128, the same on 165.
- **The shift is confined to ritual law:** Shabbat −0.13, Yom Tov −0.13, fasts and aveilut −0.13, kashrut −0.12, all
  significant. Tefillah, business and bein adam lachavero: no change.
- **Every lab shifts** (Gemini −0.09, GPT −0.07, Grok −0.06, Claude −0.04). With the Ashkenazi asker Claude is more
  lenient than GPT; with the Sephardi asker the two are indistinguishable.
- **Both directions.** One set of glass dishes for meat and dairy, waiting after hard cheese, kitniyot and wet wipes on
  Shabbat go lenient; glatt-only beef, bishul akum when a Jew lit the flame, kiddush over whiskey and Rabbeinu Tam
  tefillin go strict.
- **The sources change too.** With the Sephardi asker, R. Ovadia Yosef is named in 73% of Claude answers, 75% of
  Gemini, 40% of Grok and 16% of GPT.

![Which authorities the answers cite, Ashkenazi vs Sephardi asker](/assets/hashkafa/sephardi-citation-radar.png)

This comparison uses newer yes / in-between / no rubrics, not yet reviewed, so it is exploratory and separate from the
pre-registered results.
