/**
 * Facts Contract
 * Input: same array of questionnaire items emitted by the Python preprocessor
 * Output: [{ json: { facts, metadata } }]
 * 
 * Improvements:
 * 1. Uses all timepoints to analyze trajectory 
 * 2. Clinically meaningful thresholds per instrument
 * 3. Trend confidence based on number of timepoints
 * 4. Recency weighting for recent trend detection
 * 5. Domain-aligned risk calculation (per-domain + global)
 * 6. Track worst severity with timing information
 * 7. Separate severity vs clinical flags analysis
 */

// =============================================================================
// CONFIGURATION
// =============================================================================

const DOMAIN_CONFIG = {
  depression: [
    { matcher: 'phq-9', label: 'PHQ-9', direction: 'higher worse', scoreField: 'raw_total' },
    { matcher: 'promis-depression', label: 'PROMIS Depression', direction: 'higher worse', scoreField: 'derived.t_score' },
    { matcher: 'ces-dc', label: 'CES-DC', direction: 'higher worse', scoreField: 'raw_total' }
  ],
  anxiety_general: [
    { matcher: 'gad-7', label: 'GAD-7', direction: 'higher worse', scoreField: 'raw_total' },
    { matcher: 'promis-anxiety', label: 'PROMIS Anxiety', direction: 'higher worse', scoreField: 'derived.t_score' }
  ],
  anxiety_panic: [
    { matcher: 'scared', label: 'SCARED Panic', direction: 'higher worse', scoreField: 'derived.subscales.Panic.total' }
  ],
  anxiety_separation: [
    { matcher: 'scared', label: 'SCARED Separation', direction: 'higher worse', scoreField: 'derived.subscales.Separation.total' }
  ],
  wellbeing: [
    { matcher: 'who-5', label: 'WHO-5', direction: 'lower worse', scoreField: 'derived.index_score' },
    { matcher: 'pedsql', label: 'PedsQL', direction: 'lower worse', scoreField: 'derived.total_score' },
    { matcher: 'promis-life', label: 'PROMIS Life Satisfaction', direction: 'lower worse', scoreField: 'derived.t_score' }
  ],
  behavior_externalizing: [
    { matcher: 'psc-17', label: 'PSC Externalizing', direction: 'higher worse', scoreField: 'derived.subscales.Externalizing.total' },
    { matcher: 'sdq', label: 'SDQ Conduct', direction: 'higher worse', scoreField: 'derived.raw_scores.conduct' },
    { matcher: 'sdq', label: 'SDQ Hyperactivity', direction: 'higher worse', scoreField: 'derived.raw_scores.hyperactivity' }
  ],
  behavior_internalizing: [
    { matcher: 'psc-17', label: 'PSC Internalizing', direction: 'higher worse', scoreField: 'derived.subscales.Internalizing.total' },
    { matcher: 'sdq', label: 'SDQ Emotional', direction: 'higher worse', scoreField: 'derived.raw_scores.emotional' }
  ],
  attention: [
    { matcher: 'psc-17', label: 'PSC Attention', direction: 'higher worse', scoreField: 'derived.subscales.Attention.total' },
    { matcher: 'sdq', label: 'SDQ Hyperactivity', direction: 'higher worse', scoreField: 'derived.raw_scores.hyperactivity' }
  ],
  self_esteem: [
    { matcher: 'rosenberg', label: 'RSES', direction: 'lower worse', scoreField: 'raw_total' }
  ],
  prosocial_strengths: [
    { matcher: 'sdq', label: 'SDQ Prosocial', direction: 'higher better', scoreField: 'derived.raw_scores.prosocial' }
  ]
};

// Clinically meaningful change thresholds per instrument
// These represent the minimum change that is clinically significant
const TREND_THRESHOLDS = {
  'phq-9': 5,           // PHQ-9: 5 points is clinically meaningful (0-27 scale)
  'phq': 5,
  'gad-7': 4,           // GAD-7: 4 points is clinically meaningful (0-21 scale)
  'gad': 4,
  'who-5': 10,          // WHO-5: 10 points on 0-100 index
  'who': 10,
  'promis': 5,          // PROMIS T-scores: 5 points (half SD)
  'pedsql': 8,          // PedsQL: ~8 points is meaningful (0-100 scale)
  'ces-dc': 5,          // CES-DC: 5 points (0-60 scale)
  'ces': 5,
  'scared': 5,          // SCARED: 5 points (0-82 scale)
  'sdq': 3,             // SDQ subscales: 3 points (0-10 each)
  'psc': 3,             // PSC-17 subscales: 3 points
  'rses': 3,            // RSES: 3 points (0-30 scale)
  'rosenberg': 3,
  'default': 2          // Fallback for unknown instruments
};

// Severity ranking for determining "worst" severity
// ORDERED from most specific to least specific to ensure correct matching
// (e.g., "moderately severe" must be checked before "moderate" or "severe")
const SEVERITY_LEVELS_ORDERED = [
  // Most specific multi-word phrases first
  ['moderately severe', 5],
  ['significantly impaired', 6],
  ['high risk', 7],
  ['below screening threshold', 2],
  ['below risk threshold', 2],
  ['below threshold', 2],
  ['within normal limits', 2],
  ['typical range', 2],
  // Single severe/critical words (high priority)
  ['critical', 7],
  ['severe', 6],
  // Moderate level
  ['moderate', 4],
  ['reduced', 4],
  ['noticeably below', 4],
  // Mild/low level
  ['mild', 2],
  ['slightly below', 2],
  ['low', 2],
  // Normal/minimal level
  ['minimal', 1],
  ['normal', 2],
  ['adequate', 3],
  ['average', 3]
];

// Keywords that indicate severe/critical status
const SEVERE_KEYWORDS = ['severe', 'critical', 'impaired', 'high risk'];

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================

function parseNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

function getPath(obj, path) {
  if (!path) return null;
  return path.split('.').reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : null), obj);
}

function average(arr) {
  const valid = arr.filter(v => v !== null && Number.isFinite(v));
  if (valid.length === 0) return null;
  return valid.reduce((sum, v) => sum + v, 0) / valid.length;
}

function compareAssessments(a, b) {
  const tpA = parseNumber(a.timepoint);
  const tpB = parseNumber(b.timepoint);
  if (tpA !== null && tpB !== null && tpA !== tpB) return tpA - tpB;

  const dateA = a.date || '';
  const dateB = b.date || '';
  if (dateA && dateB && dateA !== dateB) return dateA.localeCompare(dateB);

  return (a.__index || 0) - (b.__index || 0);
}

// =============================================================================
// THRESHOLD FUNCTION
// =============================================================================

function getTolerance(instrumentLabel) {
  const key = (instrumentLabel || '').toLowerCase();
  for (const [pattern, tol] of Object.entries(TREND_THRESHOLDS)) {
    if (pattern !== 'default' && key.includes(pattern)) return tol;
  }
  return TREND_THRESHOLDS.default;
}

// =============================================================================
// ENHANCED SEVERITY DETECTION
// =============================================================================

/**
 * Check if text contains any severe keywords
 */
function containsSevereKeyword(text) {
  const lower = String(text || '').toLowerCase();
  return SEVERE_KEYWORDS.some(keyword => lower.includes(keyword));
}

/**
 * Get severity rank for comparison (higher = worse)
 * Uses ordered list to check more specific phrases first
 * (e.g., "moderately severe" before "moderate" or "severe")
 */
function getSeverityRank(severityText) {
  const lower = String(severityText || '').toLowerCase();
  
  // Check each ranked severity level in order (most specific first)
  for (const [level, rank] of SEVERITY_LEVELS_ORDERED) {
    if (lower.includes(level)) {
      return { level, rank };
    }
  }
  
  // Check for severe keywords if no exact match
  if (containsSevereKeyword(lower)) {
    return { level: lower, rank: 6 };
  }
  
  return { level: lower || 'unknown', rank: 0 };
}

/**
 * Analyze risk markers for a single record
 * Separates severity field from clinical flags
 */
function analyzeRecordRisk(rec) {
  const severityText = String(rec.severity || rec?.derived?.severity_level || '');
  const flags = Array.isArray(rec.clinical_flags) ? rec.clinical_flags : [];
  
  const severityIsSevere = containsSevereKeyword(severityText);
  const severeFlags = flags.filter(f => containsSevereKeyword(f));
  const flagsContainRisk = severeFlags.length > 0;
  
  return {
    severityText,
    severityIsSevere,
    severityRank: getSeverityRank(severityText),
    flagsContainRisk,
    severeFlags,
    hasSevereMarker: severityIsSevere || flagsContainRisk,
    timepoint: rec.timepoint,
    date: rec.date
  };
}

/**
 * Find the worst severity across all records for a domain
 */
function findWorstSeverity(allRecords) {
  let worst = null;
  
  for (const rec of allRecords) {
    const risk = analyzeRecordRisk(rec);
    const { rank } = risk.severityRank;
    
    if (!worst || rank > worst.rank) {
      worst = {
        level: risk.severityText,
        rank,
        timepoint: rec.timepoint,
        date: rec.date,
        severityWasSevere: risk.severityIsSevere,
        flagsIndicatedRisk: risk.flagsContainRisk,
        severeFlags: risk.severeFlags
      };
    }
  }
  
  return worst;
}

/**
 * Analyze historical and current risk for a domain
 */
function analyzeDomainRisk(allRecords) {
  if (!allRecords || allRecords.length === 0) {
    return {
      historicalSevere: false,
      currentSevere: false,
      worstSeverity: null,
      latestRisk: null
    };
  }
  
  // Analyze all records
  const riskAnalyses = allRecords.map(analyzeRecordRisk);
  
  // Historical: was there EVER a severe marker?
  const historicalSevere = riskAnalyses.some(r => r.hasSevereMarker);
  
  // Current: is the LATEST record severe?
  const latestRisk = riskAnalyses[riskAnalyses.length - 1];
  const currentSevere = latestRisk.hasSevereMarker;
  
  // Find worst severity with details
  const worstSeverity = findWorstSeverity(allRecords);
  
  return {
    historicalSevere,
    currentSevere,
    worstSeverity,
    latestRisk: {
      severity: latestRisk.severityText,
      severityIsSevere: latestRisk.severityIsSevere,
      flagsContainRisk: latestRisk.flagsContainRisk,
      severeFlags: latestRisk.severeFlags
    }
  };
}

// =============================================================================
// SCORE EXTRACTION
// =============================================================================

function extractScore(record, cfg) {
  const candidates = [
    cfg?.scoreField ? getPath(record, cfg.scoreField) : null,
    record?.derived?.total_score,
    record?.derived?.total_scale_score,
    record?.derived?.index_score,
    record?.raw_total
  ];
  for (const val of candidates) {
    const num = Number(val);
    if (Number.isFinite(num)) return num;
  }
  return null;
}

function buildSnapshot(record, cfg) {
  if (!record) return null;
  return {
    timepoint: parseNumber(record.timepoint),
    date: record.date || null,
    score: extractScore(record, cfg),
    severity: record.severity || record?.derived?.severity_level || null
  };
}

// =============================================================================
// ENHANCED TREND ANALYSIS
// =============================================================================

function analyzeTrendFromAllTimepoints(allRecords, cfg, direction, instrumentLabel) {
  const scores = allRecords
    .map(r => extractScore(r, cfg))
    .filter(s => s !== null);

  if (scores.length < 2) {
    return {
      trend: 'unknown',
      trendConfidence: 'insufficient',
      isConsistent: null,
      recentTrend: 'unknown',
      timepointsUsed: scores.length
    };
  }

  const first = scores[0];
  const last = scores[scores.length - 1];
  const diff = last - first;
  const tol = getTolerance(instrumentLabel);
  const dir = (direction || 'higher worse').toLowerCase();

  // Count ups and downs to check consistency
  let ups = 0, downs = 0;
  for (let i = 1; i < scores.length; i++) {
    if (scores[i] > scores[i - 1]) ups++;
    else if (scores[i] < scores[i - 1]) downs++;
  }
  const isConsistent = (ups === 0 || downs === 0); // no reversals

  // Determine overall trend based on direction
  function interpretTrend(scoreDiff, tolerance, directionStr) {
    if (directionStr.includes('higher') && directionStr.includes('worse')) {
      if (scoreDiff <= -tolerance) return 'improving';
      if (scoreDiff >= tolerance) return 'worsening';
      return 'stable';
    }
    if (directionStr.includes('lower') && directionStr.includes('worse')) {
      if (scoreDiff >= tolerance) return 'improving';
      if (scoreDiff <= -tolerance) return 'worsening';
      return 'stable';
    }
    if (directionStr.includes('higher') && directionStr.includes('better')) {
      if (scoreDiff >= tolerance) return 'improving';
      if (scoreDiff <= -tolerance) return 'worsening';
      return 'stable';
    }
    return 'unknown';
  }

  const overallTrend = interpretTrend(diff, tol, dir);

  // Recent trend (last 3 vs first 3)
  let recentTrend = overallTrend;
  if (scores.length >= 4) {
    const recentScores = scores.slice(-3);
    const earlierScores = scores.slice(0, 3);
    const recentAvg = average(recentScores);
    const earlierAvg = average(earlierScores);
    if (recentAvg !== null && earlierAvg !== null) {
      const recentDiff = recentAvg - earlierAvg;
      recentTrend = interpretTrend(recentDiff, tol, dir);
    }
  }

  // Confidence based on number of timepoints
  let trendConfidence;
  if (scores.length >= 6) {
    trendConfidence = 'high';
  } else if (scores.length >= 4) {
    trendConfidence = 'moderate';
  } else {
    trendConfidence = 'low';
  }

  // Adjust confidence if trajectory is inconsistent (volatile)
  if (!isConsistent && scores.length >= 3) {
    if (trendConfidence === 'high') trendConfidence = 'moderate';
    else if (trendConfidence === 'moderate') trendConfidence = 'low';
  }

  return {
    trend: overallTrend,
    trendConfidence,
    isConsistent,
    recentTrend,
    timepointsUsed: scores.length
  };
}

// =============================================================================
// MAIN PROCESSING
// =============================================================================

const records = (items || [])
  .map((item, idx) => ({ ...(item?.json || {}), __index: idx }))
  .filter(rec => !!String(rec.questionnaire || '').trim());

if (!records.length) {
  return [{
    json: {
      facts: {
        domains: {},
        risk: {
          historicalSevere: false,
          currentSevere: false,
          worstSeverity: null,
          domainRiskSummary: {}
        }
      },
      metadata: { generatedAt: new Date().toISOString(), note: 'No questionnaire data available' }
    }
  }];
}

// Group records by questionnaire
const grouped = {};
for (const rec of records) {
  const key = String(rec.questionnaire).trim().toLowerCase();
  if (!grouped[key]) grouped[key] = { name: rec.questionnaire, records: [] };
  grouped[key].records.push(rec);
}
Object.values(grouped).forEach(entry => entry.records.sort(compareAssessments));

function findQuestionnaire(matcher) {
  const needle = matcher.toLowerCase();
  for (const key of Object.keys(grouped)) {
    if (key.includes(needle)) return grouped[key];
  }
  return null;
}

/**
 * Build domain facts with enhanced trend and risk analysis
 */
function buildDomainFacts(domainKey) {
  const configs = DOMAIN_CONFIG[domainKey] || [];
  for (const cfg of configs) {
    const entry = findQuestionnaire(cfg.matcher);
    if (!entry || !entry.records.length) continue;

    const allRecords = entry.records;
    const baseline = buildSnapshot(allRecords[0], cfg);
    const latest = buildSnapshot(allRecords[allRecords.length - 1], cfg);
    const direction = cfg.direction || allRecords[0]?.scale_info?.direction || 'higher worse';
    const instrumentLabel = cfg.label || entry.name;

    // Enhanced trend analysis
    const trendAnalysis = analyzeTrendFromAllTimepoints(allRecords, cfg, direction, instrumentLabel);
    
    // Domain-specific risk analysis
    const domainRisk = analyzeDomainRisk(allRecords);

    return {
      instrument: instrumentLabel,
      baseline,
      latest,
      // Trend info
      trend: trendAnalysis.trend,
      trendConfidence: trendAnalysis.trendConfidence,
      recentTrend: trendAnalysis.recentTrend,
      isConsistent: trendAnalysis.isConsistent,
      timepointsUsed: trendAnalysis.timepointsUsed,
      thresholdUsed: getTolerance(instrumentLabel),
      // Domain-specific risk info
      risk: {
        historicalSevere: domainRisk.historicalSevere,
        currentSevere: domainRisk.currentSevere,
        worstSeverity: domainRisk.worstSeverity,
        latestRisk: domainRisk.latestRisk
      }
    };
  }
  return null;
}

// Build facts object
const facts = { domains: {} };
const domainKeys = Object.keys(DOMAIN_CONFIG);

domainKeys.forEach(domainKey => {
  const domainFacts = buildDomainFacts(domainKey);
  if (domainFacts) facts.domains[domainKey] = domainFacts;
});

// =============================================================================
// GLOBAL RISK SUMMARY
// =============================================================================

// Aggregate risk across all domains
const domainRiskSummary = {};
let globalHistoricalSevere = false;
let globalCurrentSevere = false;
let globalWorstSeverity = null;

for (const [domainKey, domainFacts] of Object.entries(facts.domains)) {
  const risk = domainFacts.risk;
  
  domainRiskSummary[domainKey] = {
    historicalSevere: risk.historicalSevere,
    currentSevere: risk.currentSevere
  };
  
  // Update global flags
  if (risk.historicalSevere) globalHistoricalSevere = true;
  if (risk.currentSevere) globalCurrentSevere = true;
  
  // Track global worst severity
  if (risk.worstSeverity) {
    if (!globalWorstSeverity || risk.worstSeverity.rank > globalWorstSeverity.rank) {
      globalWorstSeverity = {
        ...risk.worstSeverity,
        domain: domainKey,
        instrument: domainFacts.instrument
      };
    }
  }
}

// Set global risk
facts.risk = {
  historicalSevere: globalHistoricalSevere,
  currentSevere: globalCurrentSevere,
  worstSeverity: globalWorstSeverity,
  domainRiskSummary
};

return [{
  json: {
    facts,
    metadata: {
      generatedAt: new Date().toISOString(),
      totalAssessments: records.length,
      domainsPopulated: Object.keys(facts.domains).length,
      enhancedTrendAnalysis: true,
      enhancedRiskAnalysis: true
    }
  }
}];
