---
title: We gave AI a semicha exam
date: 2026-11-01
study: HalachaBench
summary: Real Chief Rabbinate semicha questions, in Hebrew, with no books and no internet. The best model scored 80 out of 100; many scored under 11.
x: https://x.com/HalachaBench/status/2116997953785413996
image: /assets/img/halachabench-results.png
data: /halachabench/
---

We gave AI models from the makers of ChatGPT, Claude, Gemini and others the real questions of five semicha papers from
Israel's Chief Rabbinate, from the Cheshvan 5787 sitting, which began on 12 October 2026: Niddah, Chuppah v'Kiddushin,
Mitzvot HaTeluyot BaAretz, Mikvaot and Tefillah u'Brachot. 60 questions in all.

Each model answered every question three times, in Hebrew, closed-book: no seforim, no web search, no tools. Every
answer was graded against a rubric written the way a rabbi would write one (sources, Rishonim, the ruling, other
accepted views, common errors) and sealed with a cryptographic commitment before any answer was graded.

## What we found

- **The best model scored 80 out of 100.** Claude Fable 5.1 led the first 22 models with 79.7, ahead of GPT-6 Astra
  (73.3) and GPT-6.1 Sol (72.8).
- **The spread is enormous.** Many models, including every open-weight model we could run on our own hardware,
  scored under 11.
- **Newer and bigger is not always better.** Within a single lab, models are 60 points and more apart.

![HalachaBench results: the models' scores with 95% intervals](/assets/img/halachabench-results.png)

The chart above is the current board. Since launch, more models have been added, each recorded as an amendment to the
pre-registration before its answers were collected, and graded with the same sealed rubrics and judge.

## What the scores are not

These results are provisional. One AI judge has graded the answers so far, the rubrics were written and reviewed by AI
models, and no rabbi has graded an answer yet. A score of 80 does not mean a model would pass the semicha exam, and no
score here is authority to pasken. Rabbis are invited to review the rubrics and grade a sample of answers; their
grades will correct the AI scores.

We also posted the launch [in Hebrew](https://x.com/HalachaBench/status/2117005966969536974).
