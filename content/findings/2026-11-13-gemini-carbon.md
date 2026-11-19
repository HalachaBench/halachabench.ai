---
title: Gemini 4 Carbon climbs to second
date: 2026-11-13
study: HalachaBench
summary: 82.3, four points above Gemini 4 Argon and not clearly apart from Claude Fable 5.2. It thinks far longer than any other model, about 69,000 tokens per answer.
x: https://x.com/HalachaBench/status/2121254678205800572
image: /assets/img/efficiency-score-vs-tokens.png
data: /halachabench/
lead: board:Gemini 4 Carbon|Gemini 4 Argon|Claude Fable 5.2
stat: 82.3
---

Google's Gemini 4 Carbon scores **82.3** (95% interval 78.4 – 86.0), second on the board.

- **Clearly ahead of its sibling.** Carbon is 4.1 points above Gemini 4 Argon (1.8 to 6.4), and clearly ahead of
  GPT-6 Astra and every model below it.
- **Not clearly apart from the leader.** Claude Fable 5.2 is ahead by 3.5 points, but the 95% interval runs from −0.3
  to 7.1.
- **It just thinks… a lot.** A median of about 69,000 output tokens and 13 minutes per answer, against about 14,000 for
  Argon and about 6,000 for Fable 5.2. Two attempts at one question timed out after 30 minutes and were rerun under the
  registered retry rule; all 180 answers are scored.

{{chart:tokens||Score against tokens per answer. Carbon sits far to the right}}

Across the board, more thinking hasn't generally bought a better answer: Claude Fable 5.2, Fable 5.1 and GPT-6 Astra
reached the top with a few thousand tokens. Carbon is the exception, near the top at many times the cost.

During Carbon's grading the judge service began sending a new kind of status message. A recorded amendment let the
harness accept it, all of Carbon's answers were graded again from the start, and no other model's grades changed.
