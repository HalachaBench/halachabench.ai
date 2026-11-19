---
title: Is your AI stringent or lenient?
date: 2026-11-06
study: HashkafaBench
summary: 13 models, 288 everyday questions. Claude's models rule most leniently; GPT, Gemini and Grok can't be told apart. On bein adam lachavero, every lab agrees.
image: /assets/hashkafa/labs-radar.png
data: /hashkafabench/
order: 1
---

Religious Jews are already asking AI the questions they once brought to a rabbi: Shabbat, kashrut, mourning, how to
treat people. Nobody had measured which way these models lean. HashkafaBench does.

We asked 13 models from four labs 288 everyday questions in seven areas of halacha, in English, as an Ashkenazi Jew,
with no community or denomination stated. Each question has a written rubric of positions from 0 (most lenient) to 1
(most stringent), and a judge model places each answer on it.

{{chart:radar||Average stringency by lab, per category}}

## The pre-selected comparisons

21 lab-against-lab comparisons were fixed before any answer was collected. They show:

- **Claude is the most lenient lab,** about 0.07 below GPT, Gemini and Grok overall. All three gaps survive correction.
  The largest is Claude vs Grok on Shabbat (0.18).
- **GPT, Gemini and Grok are not distinguishable** from each other overall.
- **Bein adam lachavero: no lab difference.** All four labs average 0.53–0.57 on interpersonal questions.

## And descriptively

- **Where halacha and ordinary decency agree, the models agree.** Asked whether to tell a friend the bride is beautiful
  when you don't think so, 12 of 13 said yes, as Beis Hillel rules.
- **Where halacha gets specific, they split:** who pays for a windshield cracked while driving a borrowed car (7 vs 6);
  whether maaser can go to the Red Cross (7 no, 4 yes, 2 in between).
- **The question matters far more than the model.** A model's overall lean explains about 2% of the variation in
  positions; the question explains about 35%. All 13 models gave the same answer on fewer than 2% of questions.
- **Within a lab, the spread can exceed the gap between labs:** GPT-6 Luna is the most lenient model (0.39) and GPT-6
  Astra the most stringent (0.56).

{{chart:heatmap||Each model on every category}}

These results describe how models answer; they are not psak. Most questions were selected because models disagreed
on them, so the bank is built to find differences, not to be a random sample.
