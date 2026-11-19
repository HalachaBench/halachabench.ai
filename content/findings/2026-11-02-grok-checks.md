---
title: Checks on the Grok results
date: 2026-11-02
study: HalachaBench
summary: Grok 4.7 scored 29.9, far below the leaders. We checked the result five ways and it holds up. Its answers are short.
x: https://x.com/HalachaBench/status/2117067063541797020
image: /assets/img/halachabench-results.png
data: /halachabench/
---

Grok 4.7 scores well below the leaders, so its result was checked more than any other. In short: its answers are
short, and the low score holds up when the grading or the rubrics are changed.

- **Its answers were complete.** All 180 answers finished normally, in Hebrew, with no output limit set and none cut
  off; reasoning effort was high on every one.
- **It writes short answers.** Grok 4.7 thought at length (a median of about 18,000 reasoning tokens per answer) but
  wrote a median of 213 words, against 368 for Claude Sonnet 4.6 and 664 for Gemini 4 Argon. The rubrics give points
  for each source, step and ruling an answer gives, so a short answer that is right on the bottom line still scores low.
- **A blind second grader agreed with the judge.** Claude Opus 5.5, without knowing which model wrote which answer,
  re-graded 30 answers and agreed with GPT-6 Astra on 88% of criterion decisions, equally for both models. Astra was
  not harder on Grok.
- **The rubrics Grok disputed don't explain its score.** Grok 4.7 reviewed all 60 sealed rubrics and asked to change or
  remove 405 of their 661 criteria. Scored without the criteria it disputed, its score goes *down*, not up.

| Scored on | Grok 4.7 | Rank | Gemini 4 Argon | Rank |
|---|---|---|---|---|
| All criteria | 29.9 | 10 | 78.2 | 2 |
| Without the 274 criteria Grok said should go | 28.5 | 10 | 76.8 | 2 |
| Only the 256 criteria Grok accepted as written | 26.0 | 12 | 75.3 | 2 |

*Ranks among the 22 models scored on 2 November.*

- **Most of Grok's critique did not hold up.** Each point that would change a grade was checked against the sources on
  Sefaria. 24 were confirmed as real rubric errors, in 29 criteria; 11 were refuted. Scored without those 29 criteria,
  Grok 4.7 stays at 29.9, and no model moves by more than 0.7 points.
- **Grok as the judge gives the same result.** Grading with the same sealed rubrics, Grok 4.7 agreed with Astra on 92%
  of 1,937 criterion decisions and did not score its own answers higher.

None of this changes the scores: the rubrics stay as sealed. Any rubric error found is corrected for every model at
once, in the next version.
