// Compact preprocessor for Gemini summary node in n8n (JavaScript)
//
// Input: items from n8n_questionnaire_preprocessor:
//   [{ json: { questionnaire, timepoint, date, raw_total, severity, clinical_flags, derived, free_text, ... } }, ...]
//
// Output: one item with:
//   { json: { summary: { timepoints: [ { tp, date, q: [ { name, tot, sev, scale?, flags?, note? }, ... ] }, ... ] } } }

function safeStr(v) {
  return v == null ? '' : String(v);
}

function safeInt(v) {
  if (v == null || v === '') return 0;
  const n = Number(v);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}

function buildCompactOverview(items) {
  // Groups all questionnaires by (timepoint, date)
  const timepointMap = {}; // key: "tp|date" -> { tp, date, q: [] }

  for (const item of items) {
    const data = (item && item.json) || {};

    const tp = safeInt(data.timepoint ?? 0);
    const date = safeStr(data.date ?? '');
    const name = safeStr(data.questionnaire ?? '').trim();

    if (!name) continue;

    const tpKey = `${tp}|${date}`;
    if (!timepointMap[tpKey]) {
      timepointMap[tpKey] = {
        tp,
        date,
        q: []
      };
    }

    const derived = data.derived || {};

    const qEntry = {
      name,
      tot: safeInt(data.raw_total ?? derived.total_score),
      sev: safeStr(data.severity ?? '')
    };

    // Short scale descriptor
    const scaleInfo = safeStr(derived.scale ?? '');
    if (scaleInfo) {
      qEntry.scale = scaleInfo.slice(0, 80);
    }

    // Clinical flags (up to 4, each truncated)
    const flags = Array.isArray(data.clinical_flags) ? data.clinical_flags : [];
    if (flags.length > 0) {
      const compactFlags = [];
      for (const f of flags.slice(0, 4)) {
        let s = safeStr(f);
        if (s.length > 80) {
          s = s.slice(0, 77) + '...';
        }
        compactFlags.push(s);
      }
      if (compactFlags.length > 0) {
        qEntry.flags = compactFlags;
      }
    }

    // Short free-text note
    const freeText = safeStr(data.free_text ?? '');
    if (freeText) {
      qEntry.note = freeText.slice(0, 160);
    }

    timepointMap[tpKey].q.push(qEntry);
  }

  // Convert map to list, sorted by timepoint then date
  const timepoints = Object.values(timepointMap).sort((a, b) => {
    const tpDiff = safeInt(a.tp) - safeInt(b.tp);
    if (tpDiff !== 0) return tpDiff;
    return safeStr(a.date).localeCompare(safeStr(b.date));
  });

  return { timepoints };
}

function preprocessForGemini(items) {
  const summary = buildCompactOverview(items);
  return [
    {
      json: {
        summary
      }
    }
  ];
}

// n8n entrypoint
return preprocessForGemini(items);