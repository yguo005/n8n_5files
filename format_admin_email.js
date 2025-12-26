// Format Admin Notification Email - HTML Version
// Prepares a detailed HTML email for admin review when summary fails quality checks

const contactInfo = $('Set_Contact_Info').first().json;
const decision = $('final_decision').first().json;

// Try to get summary output for context
let summaryOutput = null;
try {
  const summaryNode = $('summary').first().json;
  if (typeof summaryNode.output === 'string') {
    try {
      summaryOutput = JSON.parse(summaryNode.output);
    } catch (e) {
      summaryOutput = { raw_text: summaryNode.output };
    }
  } else {
    summaryOutput = summaryNode.output;
  }
} catch (e) {
  summaryOutput = null;
}

// Helper function to format score with emoji and color
function scoreEmoji(score, threshold = 4) {
  if (score === null || score === undefined) return '<span style="color: #718096;">❓ N/A</span>';
  if (score >= threshold) return `<span style="color: #38a169;">✅ ${score}</span>`;
  if (score >= threshold - 1) return `<span style="color: #d69e2e;">⚠️ ${score}</span>`;
  return `<span style="color: #e53e3e;">❌ ${score}</span>`;
}

// Helper function to format boolean with emoji and color
function boolEmoji(value, trueIsGood = true) {
  if (value === null || value === undefined) return '<span style="color: #718096;">❓ N/A</span>';
  if (trueIsGood) {
    return value 
      ? '<span style="color: #38a169;">✅ Yes</span>' 
      : '<span style="color: #e53e3e;">❌ No</span>';
  } else {
    return value 
      ? '<span style="color: #e53e3e;">⚠️ Yes</span>' 
      : '<span style="color: #38a169;">✅ No</span>';
  }
}

// Format failure reasons as HTML list
function formatFailReasons(reasons) {
  if (!reasons || !Array.isArray(reasons) || reasons.length === 0) {
    return '<li style="color: #718096;">No specific reasons provided</li>';
  }
  return reasons.map(r => `<li style="margin-bottom: 8px;">${r}</li>`).join('');
}

// Format unsupported claims as HTML
function formatUnsupportedClaims(claims) {
  if (!claims || !Array.isArray(claims) || claims.length === 0) {
    return '<span style="color: #38a169;">None detected</span>';
  }
  return '<ul style="margin: 5px 0; padding-left: 20px;">' + 
    claims.map(c => `<li style="color: #e53e3e;">⚠️ ${c}</li>`).join('') + 
    '</ul>';
}

// Format missed critical info as HTML
function formatMissedInfo(info) {
  if (!info || !Array.isArray(info) || info.length === 0) {
    return '<span style="color: #38a169;">None detected</span>';
  }
  return '<ul style="margin: 5px 0; padding-left: 20px;">' + 
    info.map(i => `<li style="color: #e53e3e;">⚠️ ${i}</li>`).join('') + 
    '</ul>';
}

// Get severity banner HTML
function getSeverityBanner(decision) {
  const safetyOverride = decision.evaluation?.safety?.override;
  const currentSevere = decision.evaluation?.safety?.currentSevereFromFacts;
  const safetyCuePresent = decision.evaluation?.safety?.safetyCuePresent;
  
  if (safetyOverride || (currentSevere && !safetyCuePresent)) {
    return `
      <div style="background: linear-gradient(135deg, #c53030 0%, #9b2c2c 100%); color: white; padding: 25px; text-align: center; border-radius: 8px 8px 0 0;">
        <div style="font-size: 32px; margin-bottom: 10px;">🚨🚨🚨</div>
        <h1 style="margin: 0; font-size: 22px; font-weight: bold;">CRITICAL SAFETY CONCERN</h1>
        <p style="margin: 10px 0 0 0; font-size: 14px;">IMMEDIATE ATTENTION REQUIRED</p>
      </div>
      <div style="background: #fff5f5; border-left: 4px solid #c53030; padding: 15px; margin: 0;">
        <p style="margin: 0; color: #c53030; font-weight: bold;">
          ⚠️ Patient data indicates SEVERE symptoms but the generated summary does NOT contain required safety recommendations.
        </p>
        <p style="margin: 10px 0 0 0; color: #742a2a; font-weight: bold;">
          DO NOT send this summary to the parent without review.
        </p>
      </div>`;
  }
  
  if (decision.action === 'ESCALATE') {
    return `
      <div style="background: linear-gradient(135deg, #d69e2e 0%, #b7791f 100%); color: white; padding: 25px; text-align: center; border-radius: 8px 8px 0 0;">
        <div style="font-size: 32px; margin-bottom: 10px;">⚠️</div>
        <h1 style="margin: 0; font-size: 22px; font-weight: bold;">SUMMARY REQUIRES ADMIN REVIEW</h1>
        <p style="margin: 10px 0 0 0; font-size: 14px;">Quality checks failed - manual review needed before sending</p>
      </div>`;
  }
  
  return `
    <div style="background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%); color: white; padding: 25px; text-align: center; border-radius: 8px 8px 0 0;">
      <div style="font-size: 32px; margin-bottom: 10px;">📋</div>
      <h1 style="margin: 0; font-size: 22px; font-weight: bold;">SUMMARY REQUIRES REVIEW</h1>
      <p style="margin: 10px 0 0 0; font-size: 14px;">Please review before proceeding</p>
    </div>`;
}

// Build the email
const evaluation = decision.evaluation || {};
const factual = evaluation.factual || {};
const heuristic = evaluation.heuristic || {};
const safety = evaluation.safety || {};

const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      line-height: 1.6;
      color: #2d3748;
      max-width: 700px;
      margin: 0 auto;
      padding: 0;
      background: #f7fafc;
    }
    .container {
      background: white;
      border-radius: 8px;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
      overflow: hidden;
      margin: 20px;
    }
    .section {
      padding: 20px 25px;
      border-bottom: 1px solid #e2e8f0;
    }
    .section:last-child {
      border-bottom: none;
    }
    .section-title {
      font-size: 14px;
      font-weight: 600;
      color: #4a5568;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin: 0 0 15px 0;
      padding-bottom: 8px;
      border-bottom: 2px solid #e2e8f0;
    }
    .info-grid {
      display: table;
      width: 100%;
    }
    .info-row {
      display: table-row;
    }
    .info-label {
      display: table-cell;
      padding: 6px 15px 6px 0;
      color: #718096;
      font-size: 13px;
      width: 40%;
    }
    .info-value {
      display: table-cell;
      padding: 6px 0;
      font-size: 14px;
      font-weight: 500;
    }
    .score-table {
      width: 100%;
      border-collapse: collapse;
    }
    .score-table td {
      padding: 8px 12px;
      border-bottom: 1px solid #edf2f7;
    }
    .score-table tr:last-child td {
      border-bottom: none;
    }
    .score-label {
      color: #4a5568;
      font-size: 13px;
    }
    .score-value {
      text-align: right;
      font-weight: 500;
    }
    .action-card {
      background: #f7fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 12px 15px;
      margin-bottom: 10px;
    }
    .action-card:last-child {
      margin-bottom: 0;
    }
    .action-title {
      font-weight: 600;
      color: #2d3748;
      margin-bottom: 4px;
    }
    .action-desc {
      font-size: 13px;
      color: #718096;
      margin: 0;
    }
    .summary-box {
      background: #f7fafc;
      border-radius: 6px;
      padding: 15px;
      font-size: 13px;
      color: #4a5568;
    }
    .footer {
      background: #edf2f7;
      padding: 15px 25px;
      text-align: center;
      font-size: 12px;
      color: #718096;
    }
    ul {
      margin: 10px 0;
      padding-left: 20px;
    }
    li {
      margin-bottom: 5px;
    }
  </style>
</head>
<body>
  <div class="container">
    ${getSeverityBanner(decision)}
    
    <!-- Case Information -->
    <div class="section">
      <h2 class="section-title">📋 Case Information</h2>
      <div class="info-grid">
        <div class="info-row">
          <div class="info-label">Child Name</div>
          <div class="info-value">${contactInfo.child_name || 'Not specified'}</div>
        </div>
        <div class="info-row">
          <div class="info-label">Parent Name</div>
          <div class="info-value">${contactInfo.parent_name || 'Not specified'}</div>
        </div>
        <div class="info-row">
          <div class="info-label">Parent Email</div>
          <div class="info-value">${contactInfo.parent_email || 'Not specified'}</div>
        </div>
        <div class="info-row">
          <div class="info-label">Timestamp</div>
          <div class="info-value">${new Date(decision.decidedAt || Date.now()).toLocaleString()}</div>
        </div>
      </div>
    </div>
    
    <!-- Decision Summary -->
    <div class="section">
      <h2 class="section-title">🎯 Decision Summary</h2>
      <div class="info-grid">
        <div class="info-row">
          <div class="info-label">Overall Pass</div>
          <div class="info-value">${boolEmoji(decision.pass)}</div>
        </div>
        <div class="info-row">
          <div class="info-label">Decision</div>
          <div class="info-value"><strong>${decision.decision || 'N/A'}</strong></div>
        </div>
        <div class="info-row">
          <div class="info-label">Action</div>
          <div class="info-value"><strong>${decision.action || 'N/A'}</strong></div>
        </div>
      </div>
    </div>
    
    <!-- Failure Reasons -->
    ${decision.failReasons && decision.failReasons.length > 0 ? `
    <div class="section" style="background: #fff5f5;">
      <h2 class="section-title" style="color: #c53030;">❌ Failure Reasons</h2>
      <ol style="margin: 0; padding-left: 20px; color: #742a2a;">
        ${formatFailReasons(decision.failReasons)}
      </ol>
    </div>
    ` : ''}
    
    <!-- Factual QA Evaluation -->
    <div class="section">
      <h2 class="section-title">🔍 Factual QA Evaluation (LLM Judge)</h2>
      <div class="info-grid" style="margin-bottom: 15px;">
        <div class="info-row">
          <div class="info-label">Pass</div>
          <div class="info-value">${boolEmoji(factual.pass)}</div>
        </div>
        <div class="info-row">
          <div class="info-label">Minimum Score</div>
          <div class="info-value">${scoreEmoji(factual.minScore)}</div>
        </div>
      </div>
      
      <table class="score-table" style="background: #f7fafc; border-radius: 6px;">
        <tr>
          <td class="score-label">Alignment</td>
          <td class="score-value">${scoreEmoji(factual.scores?.alignment)}</td>
        </tr>
        <tr>
          <td class="score-label">Trend Accuracy</td>
          <td class="score-value">${scoreEmoji(factual.scores?.trendAccuracy)}</td>
        </tr>
        <tr>
          <td class="score-label">Severity Accuracy</td>
          <td class="score-value">${scoreEmoji(factual.scores?.severityAccuracy)}</td>
        </tr>
        <tr>
          <td class="score-label">Risk Accuracy</td>
          <td class="score-value">${scoreEmoji(factual.scores?.riskAccuracy)}</td>
        </tr>
        <tr>
          <td class="score-label">Domain Coverage</td>
          <td class="score-value">${scoreEmoji(factual.scores?.domainCoverage)}</td>
        </tr>
      </table>
      
      <div style="margin-top: 15px;">
        <p style="margin: 0 0 5px 0; font-size: 13px; color: #4a5568; font-weight: 600;">Unsupported Claims:</p>
        ${formatUnsupportedClaims(factual.unsupportedClaims)}
      </div>
      
      <div style="margin-top: 10px;">
        <p style="margin: 0 0 5px 0; font-size: 13px; color: #4a5568; font-weight: 600;">Missed Critical Info:</p>
        ${formatMissedInfo(factual.missedInfo)}
      </div>
    </div>
    
    <!-- Heuristic Evaluation -->
    <div class="section">
      <h2 class="section-title">📊 Heuristic Evaluation</h2>
      <div class="info-grid" style="margin-bottom: 15px;">
        <div class="info-row">
          <div class="info-label">Pass</div>
          <div class="info-value">${boolEmoji(heuristic.pass)}</div>
        </div>
        <div class="info-row">
          <div class="info-label">Final Score</div>
          <div class="info-value"><strong>${heuristic.finalScore?.toFixed(2) || 'N/A'}</strong> / 5.00</div>
        </div>
        <div class="info-row">
          <div class="info-label">Rating</div>
          <div class="info-value">
            <span style="background: ${heuristic.rating === 'A' ? '#38a169' : heuristic.rating === 'B' ? '#4299e1' : heuristic.rating === 'C' ? '#d69e2e' : '#e53e3e'}; color: white; padding: 2px 10px; border-radius: 4px; font-weight: bold;">
              ${heuristic.rating || 'N/A'}
            </span>
          </div>
        </div>
      </div>
      
      <table class="score-table" style="background: #f7fafc; border-radius: 6px;">
        <tr>
          <td class="score-label">Safety</td>
          <td class="score-value">${scoreEmoji(heuristic.allScores?.safety)}</td>
        </tr>
        <tr>
          <td class="score-label">Empathy</td>
          <td class="score-value">${scoreEmoji(heuristic.allScores?.empathy)}</td>
        </tr>
        <tr>
          <td class="score-label">Insight</td>
          <td class="score-value">${scoreEmoji(heuristic.allScores?.insight)}</td>
        </tr>
        <tr>
          <td class="score-label">Action</td>
          <td class="score-value">${scoreEmoji(heuristic.allScores?.action)}</td>
        </tr>
        <tr>
          <td class="score-label">Relevance</td>
          <td class="score-value">${scoreEmoji(heuristic.allScores?.relevance)}</td>
        </tr>
        <tr>
          <td class="score-label">Clarity</td>
          <td class="score-value">${scoreEmoji(heuristic.allScores?.clarity)}</td>
        </tr>
        <tr>
          <td class="score-label">Length</td>
          <td class="score-value">${scoreEmoji(heuristic.allScores?.length)}</td>
        </tr>
      </table>
    </div>
    
    <!-- Safety Analysis -->
    <div class="section" style="background: ${safety.override || safety.currentSevereFromFacts ? '#fff5f5' : '#ffffff'};">
      <h2 class="section-title" style="color: ${safety.override ? '#c53030' : '#4a5568'};">🛡️ Safety Analysis</h2>
      <table class="score-table">
        <tr>
          <td class="score-label">Safety Pass</td>
          <td class="score-value">${boolEmoji(safety.pass)}</td>
        </tr>
        <tr>
          <td class="score-label">Safety Override Active</td>
          <td class="score-value">${boolEmoji(safety.override, false)}</td>
        </tr>
        <tr>
          <td class="score-label">Severe Data in Facts</td>
          <td class="score-value">${boolEmoji(safety.severeInData, false)}</td>
        </tr>
        <tr>
          <td class="score-label">Current Severe (Facts)</td>
          <td class="score-value">${boolEmoji(safety.currentSevereFromFacts, false)}</td>
        </tr>
        <tr>
          <td class="score-label">Safety Cue in Summary</td>
          <td class="score-value">${boolEmoji(safety.safetyCuePresent)}</td>
        </tr>
        <tr>
          <td class="score-label">Safety Match Count</td>
          <td class="score-value">${safety.safetyMatchCount ?? 'N/A'}</td>
        </tr>
      </table>
    </div>
    
    <!-- Thresholds -->
    <div class="section">
      <h2 class="section-title">⚙️ Thresholds Used</h2>
      <table class="score-table" style="background: #f7fafc; border-radius: 6px;">
        <tr>
          <td class="score-label">Heuristic Min Score</td>
          <td class="score-value">${decision.thresholds?.heuristicMinScore || 'N/A'}</td>
        </tr>
        <tr>
          <td class="score-label">Heuristic Safety Min</td>
          <td class="score-value">${decision.thresholds?.heuristicSafetyMin || 'N/A'}</td>
        </tr>
        <tr>
          <td class="score-label">Factual Min Score</td>
          <td class="score-value">${decision.thresholds?.factualMinScore || 'N/A'}</td>
        </tr>
        <tr>
          <td class="score-label">Acceptable Ratings</td>
          <td class="score-value">${decision.thresholds?.acceptableRatings?.join(', ') || 'N/A'}</td>
        </tr>
      </table>
    </div>
    
    <!-- Generated Summary Preview -->
    ${summaryOutput ? `
    <div class="section">
      <h2 class="section-title">📝 Generated Summary (Preview)</h2>
      <div class="summary-box">
        <p style="margin: 0 0 10px 0; font-weight: 600;">Current Picture:</p>
        <p style="margin: 0 0 15px 0;">${summaryOutput.current_picture || summaryOutput.raw_text?.substring(0, 300) || 'N/A'}${summaryOutput.raw_text && summaryOutput.raw_text.length > 300 ? '...' : ''}</p>
        
        ${summaryOutput.recommendations ? `
        <p style="margin: 0 0 10px 0; font-weight: 600;">Recommendations:</p>
        <ol style="margin: 0; padding-left: 20px;">
          ${summaryOutput.recommendations.map(r => `<li>${r}</li>`).join('')}
        </ol>
        ` : ''}
        
        ${summaryOutput.safety_guidance ? `
        <p style="margin: 15px 0 10px 0; font-weight: 600;">Safety Guidance:</p>
        <ul style="margin: 0; padding-left: 20px;">
          <li>Professional Contact: ${summaryOutput.safety_guidance.professional_contact_recommended ? '<strong style="color: #e53e3e;">⚠️ YES</strong>' : 'No'}</li>
          <li>Monitoring Level: ${summaryOutput.safety_guidance.monitoring_level || 'N/A'}</li>
        </ul>
        ` : ''}
      </div>
    </div>
    ` : ''}
    
    <!-- Action Required -->
    <div class="section">
      <h2 class="section-title">🎬 Action Required</h2>
      <p style="margin: 0 0 15px 0; color: #4a5568;">Please review the generated summary and take one of the following actions:</p>
      
      <div class="action-card">
        <div class="action-title">✏️ REVISE & APPROVE</div>
        <p class="action-desc">Edit the summary to address the issues above, then manually send to the parent.</p>
      </div>
      
      <div class="action-card">
        <div class="action-title">🔄 REGENERATE</div>
        <p class="action-desc">Trigger a new summary generation with adjusted parameters.</p>
      </div>
      
      <div class="action-card">
        <div class="action-title">📞 DIRECT CONTACT</div>
        <p class="action-desc">If safety concerns exist, contact the family directly rather than sending an automated summary.</p>
      </div>
      
      <div class="action-card">
        <div class="action-title">❌ DISCARD</div>
        <p class="action-desc">Do not send any summary if the data quality is insufficient.</p>
      </div>
    </div>
    
    <!-- Footer -->
    <div class="footer">
      <p style="margin: 0;">This is an automated notification from the Clinical Summary Pipeline.</p>
      <p style="margin: 5px 0 0 0;">Generated at: ${new Date().toISOString()}</p>
    </div>
  </div>
</body>
</html>`;

// Determine subject line based on severity
let subject = '⚠️ Clinical Summary Requires Review';
if (safety.override || (safety.currentSevereFromFacts && !safety.safetyCuePresent)) {
  subject = '🚨 CRITICAL: Safety Review Required - Clinical Summary';
} else if (decision.decision === 'MAX_RETRIES_EXCEEDED') {
  subject = '🔄 Max Retries Exceeded - Clinical Summary Failed QA';
}

subject += ` - ${contactInfo.child_name || 'Patient'}`;

// Return formatted data for email node
return [{
  json: {
    to: contactInfo.admin_email,
    subject: subject,
    message: htmlContent,
    // Pass through decision data in case needed
    decision: decision.decision,
    action: decision.action,
    pass: decision.pass,
    child_name: contactInfo.child_name,
    is_critical: safety.override || (safety.currentSevereFromFacts && !safety.safetyCuePresent)
  }
}];