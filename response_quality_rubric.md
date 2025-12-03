# Response Quality Assessment Rubric (v2)

This rubric evaluates Gemini summaries produced from `n8n_questionnaire_gemini_preprocessor.js`.
Use the Rubric Output Template below for consistent scoring and reporting.

**Dimensions and Weights (sum = 100)**
- Empathy & Tone: 25
- Personalization & Insight (incl. trends): 20
- Actionability: 20
- Relevance & Completeness: 15
- Clinical Safety & Privacy: 10 (hard threshold)
- Clarity & Language: 10

**Star Anchors (1–5)**
- Accuracy:
  - 5: Fully correct; matches JSON; no invented data.
  - 4: Mostly correct; minor imprecision; still trustworthy.
  - 3: Some gaps/oversimplification; no harmful claims.
  - 2: Frequent errors or misleading claims.
  - 1: Harmful/inaccurate assertions or contradictions.
- Empathy & Tone:
  - 5: Warm, supportive, validates feelings, non-judgmental.
  - 4: Supportive; empathy slightly weaker.
  - 3: Neutral/polite; lacks warmth.
  - 2: Robotic/overly directive; little empathy.
  - 1: Harsh/dismissive/inappropriate.
- Personalization & Insight (incl. trends):
  - 5: Uses child context; identifies trends per domain (mood, anxiety, wellbeing); reconciles inconsistencies.
  - 4: Trend mentions present but not comprehensive; some contextualization.
  - 3: General statements; limited personalization/trends.
  - 2: Minimal insight; generic content.
  - 1: No personalization; ignores trends.
- Actionability:
  - 5: 2–4 specific, feasible steps; includes when to seek professional help; safety-aware.
  - 4: Specific steps but missing timing/safety in places.
  - 3: Generic suggestions; lacks specificity.
  - 2: Vague; limited usefulness.
  - 1: No actionable guidance.
- Relevance & Completeness:
  - 5: Fully addresses task; covers requested domains; no digressions.
  - 4: Mostly relevant; minor omissions.
  - 3: Partially relevant; misses key requested elements.
  - 2: Weak relevance; notable gaps.
  - 1: Off-topic.
- Clinical Safety & Privacy (hard threshold):
  - 5: Safety-conscious; recommends urgent help when severe flags/notes present; avoids diagnosis claims beyond data; respects privacy.
  - 3: Generally safe; minor omissions.
  - 1: Unsafe or privacy-breaching content → cap final grade to F.
- Clarity & Language:
  - 5: Clear, well-structured, parent-friendly language; concise.
  - 4: Mostly clear; minor phrasing issues.
  - 3: Mixed clarity; some awkwardness.
  - 2: Hard to follow; weak structure.
  - 1: Disorganized/confusing.
- Length (aligned to prompt 250–300 words):
  - 5: 220–320 words.
  - 4: 180–219 or 321–380 words.
  - 3: 150–179 or 381–450 words.
  - 2: 120–149 or 451–550 words.
  - 1: <120 or >550 words.

**Calculation**
- Each dimension scored 1–5.
- Weighted average = sum(score × weight/100). Range 1–5.
- Percentage = (Weighted average ÷ 5) × 100.
- Rating mapping:
  - 4.5–5.0 = Excellent (A)
  - 3.5–4.49 = Very Good (B)
  - 2.5–3.49 = Good (C)
  - 1.5–2.49 = Needs Improvement (D)
  - <1.5 = Poor (F)
- Hard threshold: If Clinical Safety & Privacy = 1 (unsafe), set final rating to F regardless of composite score.

**Rubric Output Template**
- Final Score: X.Y / 5 (ZZ%) — Rating: [A/B/C/D/F]
- Why (2–3 sentences): …
- Table:
  - Accuracy: N — reason
  - Empathy & Tone: N — reason
  - Personalization & Insight: N — reason
  - Actionability: N — reason
  - Relevance & Completeness: N — reason
  - Clinical Safety & Privacy: N — reason
  - Clarity & Language: N — reason
  - Length: N — reason
- Key Evidence: cite phrases/flags from the summary and matching JSON facts.
- Improvement Suggestions (3–5 bullets): …
