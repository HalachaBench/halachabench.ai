<!-- source_sha: c9034516ad62 -->
- **Claude Fable 5.2 ו-Gemini 4 Carbon בראש:** הם לא נבדלים בבירור (Fable 5.2 מקדים ב-3.5 נקודות, רווח סמך של
  95% בין −0.3 ל-7.1). Fable 5.2 מקדים בבירור כל מודל אחר: את Claude Fable 5.1 ב-6.0 נקודות (3.0 עד 9.1), את
  Gemini 4 Argon ב-7.5 (3.7 עד 11.2) ואת GPT-5.6 Sol ב-8.5 (4.2 עד 13.4). Gemini 4 Carbon מקדים בבירור את Gemini 4
  Argon (ב-4.1, 1.8 עד 6.4), את GPT-6 Astra (ב-9.0, 4.1 עד 13.7) ואת כל המודלים שמתחתם, אבל אינו נבדל בבירור
  מ-Claude Fable 5.1 (שנמצא 2.6 נקודות מאחורי Carbon, −0.9 עד 6.1) או מ-GPT-5.6 Sol (ב-5.0, −0.4 עד 10.8).
- **לא נבדלים בבירור:** Claude Fable 5.1, Gemini 4 Argon ו-GPT-5.6 Sol (Fable מקדים את Argon ב-1.5 נקודות, רווח
  סמך של 95% בין −1.8 ל-4.9, ואת GPT-5.6 Sol ב-2.5, −2.5 עד 7.9); GPT-5.6 Sol עם GPT-6 Astra (ב-3.9, −0.9 עד 8.5)
  ועם GPT-6.1 Sol (ב-4.5, −0.5 עד 8.9); Gemini 4 Argon ו-GPT-6 Astra (ב-4.9, −0.3 עד 10.0); GPT-6 Astra, GPT-6.1 Sol
  ו-Claude Opus 5.5; Gemini 3.8 Flash ו-Muse Wonder Full (ב-3.6, −1.2 עד 8.1); GPT-6 Sol, Muse Wonder ו-Claude Opus
  4.8 (GPT-6 Sol מקדים את Opus 4.8 ב-0.6, −4.6 עד 5.4, ו-Muse Wonder נמצא במרחק של עד 0.4 משניהם); Muse Spark 1.3
  עם GPT-6.1 Terra (ב-1.6, −3.3 עד 6.8) ועם GPT-6 Luna (ב-3.9, −0.6 עד 8.3); GPT-6 Luna, Grok 4.7, Claude Sonnet
  4.6 ו-Claude Sonnet 5.5; GPT-6.1 Terra ו-GPT-6 Luna; Grok 4.3, Muse Glimmer 30B ו-Claude Haiku 5.5, וכן Claude
  Haiku 5.5 עם Qwen3.8 27B; רוב הזוגות בין המקומות 22 עד 27.
- **נבדלים בבירור:** Claude Fable 5.1 מקדים כל מודל שמתחתיו מלבד Gemini 4 Argon ו-GPT-5.6 Sol (ב-6.4 נקודות על
  GPT-6 Astra, 1.6 עד 11.1); GPT-5.6 Sol מקדים את Claude Opus 5.5 (ב-8.2, 2.0 עד 14.1) ואת כל מודל שמתחתיו;
  Gemini 4 Argon מקדים את GPT-6.1 Sol (ב-5.5, 0.8 עד 10.2) ואת כל מודל שמתחתיו; GPT-6.1 Terra מקדים את Grok 4.7
  (ב-4.7, 0.5 עד 9.1), את Claude Sonnet 4.6 (ב-5.0, 0.1 עד 10.0) ואת Claude Sonnet 5.5 (ב-5.9, 0.8 עד 10.9);
  Claude Opus 5.5 מקדים את Muse Wonder Full (ב-8.3, 4.5 עד 12.0), ו-Muse Wonder Full מקדים את GPT-6 Sol (ב-12.1,
  7.8 עד 16.6) ואת כל מודל שמתחתיו; Claude Opus 4.8, GPT-6 Sol ו-Muse Wonder נבדלים מכל מודל אחר, אבל לא זה מזה;
  Muse Spark 1.3 מקדים את Grok 4.7 (ב-6.4, 2.2 עד 10.7) ואת כל מודל שמתחתיו; Muse Ember נמצא מתחת ל-Claude Sonnet
  5.5 (ב-13.4, 9.2 עד 17.7) ומקדים את Grok 4.3 (ב-4.6, 1.0 עד 8.2), את Muse Glimmer 30B (ב-4.8, 2.2 עד 7.6) ואת
  Claude Haiku 5.5 (ב-6.7, 3.4 עד 10.2); gpt-oss-20b נמצא מתחת לכל מודל אחר.
- **בין דורות:** Claude Opus 5.5 גבוה מ-Claude Opus 4.8 ב-21.0 נקודות (17.4 עד 24.9); Claude Sonnet 5.5 ו-Claude
  Sonnet 4.6 אינם נבדלים בבירור (הפרש של 0.9, −3.0 עד 4.9). בכיוון ההפוך, GPT-5.6 Sol גבוה ב-28.6 נקודות מ-GPT-6
  Sol, החדש ממנו (24.2 עד 33.2), ומקדים אותו ב-57 מתוך 59 השאלות ששניהם ענו עליהן. GPT-6 Sol לא עשה יותר טעויות;
  הוא כתב תשובות קצרות יותר (חציון של כ-200 מילים לעומת כ-310, עם פחות חשיבה), שכיסו פחות מהמקורות ומהפסקים
  שהמחוונים דורשים (48% מהדרישות, לעומת 77%).
- **בין מודלי Muse:** Muse Wonder Full גבוה מ-Muse Wonder ב-12.5 נקודות (9.3 עד 15.8), ו-Muse Wonder גבוה מ-Muse
  Spark 1.3 ב-12.0 (7.5 עד 16.6). Muse Ember, ששוחרר ב-9 בנובמבר כמודל ה-Muse הקל ביותר של Meta, נמוך מ-Muse Spark
  1.3 ב-20.9 (16.7 עד 25.3) וגבוה ב-4.8 מ-Muse Glimmer 30B, מודל ה-Muse בעל המשקלות הפתוחים שהורץ מקומית, שנמוך
  מ-Muse Spark 1.3 ב-25.7 (21.7 עד 30.0).
