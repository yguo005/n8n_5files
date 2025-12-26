/**
 * Final Decision Gate
 * Combines heuristic evaluator + LLM factual evaluator + safety flags
 * into a single authoritative pass/fail decision
 * 
 * Input: Merged outputs from both evaluators
 * Output: Final decision with detailed breakdown
 */

// Helper to safely get nested value
function getPath(obj, path, defaultVal = null) {
    return path.split('.').reduce((acc, key) => 
      (acc && acc[key] !== undefined) ? acc[key] : defaultVal, obj);
  }
  
  /**
   * Parse LLM output that may be wrapped in markdown code fences
   * Handles: ```json\n{...}\n``` or ```\n{...}\n``` or raw JSON
   */
  function parseMarkdownWrappedJson(input) {
    if (!input) return null;
    
    let str = typeof input === 'string' ? input : JSON.stringify(input);
    
    // Strip markdown code fences: ```json ... ``` or ``` ... ```
    const codeBlockMatch = str.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
    if (codeBlockMatch) {
      str = codeBlockMatch[1].trim();
    }
    
    try {
      return JSON.parse(str);
    } catch (e) {
      // Try to extract JSON object if parsing failed
      const jsonMatch = str.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        try {
          return JSON.parse(jsonMatch[0]);
        } catch (e2) {}
      }
    }
    return null;
  }
    
    // Extract data from merged items
    // Item 0: factual_QA_judge output (via merge)
    // Item 1: Evaluation_LLMSummary&processedData output (via merge)
    
    let factual = null;
    let heuristic = null;
    let facts = null;
    
    // Find the factual QA and heuristic evaluator outputs
    for (const item of items) {
      const json = item.json || {};
      
      // Detect factual QA judge output (has alignment_score)
      if (json.alignment_score !== undefined || json.pass !== undefined) {
        factual = json;
      }
      // Detect heuristic evaluator output (has final.score)
      else if (json.final && json.final.score !== undefined) {
        heuristic = json;
      }
      // Detect facts (has domains)
      else if (json.facts && json.facts.domains) {
        facts = json.facts;
      }
      // Check for nested output field (LangChain agent output)
      // Handle markdown code fences: ```json\n{...}\n```
      else if (json.output) {
        const parsed = parseMarkdownWrappedJson(json.output);
        if (parsed && (parsed.alignment_score !== undefined || parsed.pass !== undefined)) {
          factual = parsed;
        }
      }
    }
    
    // Handle missing data
    if (!factual && !heuristic) {
      return [{
        json: {
          pass: false,
          decision: 'FAIL',
          reason: 'Missing evaluator outputs - cannot make decision',
          debug: {
            factualFound: !!factual,
            heuristicFound: !!heuristic,
            factsFound: !!facts,
            itemCount: items.length,
            itemKeys: items.map(i => Object.keys(i.json || {}))
          }
        }
      }];
    }
    
    // =============================================================================
    // DECISION LOGIC
    // =============================================================================
    
    // Factual QA pass (from LLM judge)
    const factualPass = factual?.pass === true;
    const factualScores = {
      alignment: factual?.alignment_score ?? 0,
      trendAccuracy: factual?.trend_accuracy_score ?? 0,
      severityAccuracy: factual?.severity_accuracy_score ?? 0,
      riskAccuracy: factual?.risk_accuracy_score ?? 0,
      domainCoverage: factual?.domain_coverage_score ?? 0
    };
    const factualMinScore = Math.min(...Object.values(factualScores).filter(v => v > 0)) || 0;
    
    // Heuristic evaluator scores
    const heuristicFinalScore = heuristic?.final?.score ?? 0;
    const heuristicSafetyScore = heuristic?.scores?.safety ?? 0;
    const heuristicRating = heuristic?.final?.rating ?? 'F';
    
    // Safety indicators
    const severeInData = heuristic?.meta?.severeInData ?? false;
    const safetyCuePresent = heuristic?.meta?.safetyCuePresent ?? false;
    const safetyMatchCount = heuristic?.meta?.safetyMatchCount ?? 0;
    
    // Current severe from facts
    const currentSevereFromFacts = facts?.risk?.currentSevere ?? false;
    
    // =============================================================================
    // DECISION RULES
    // =============================================================================
    
    const thresholds = {
      heuristicMinScore: 3.5,
      heuristicSafetyMin: 4,
      factualMinScore: 3,
      acceptableRatings: ['A', 'B']
    };
    
    // Core pass conditions
    const heuristicPass = heuristicFinalScore >= thresholds.heuristicMinScore;
    const safetyPass = heuristicSafetyScore >= thresholds.heuristicSafetyMin;
    const ratingPass = thresholds.acceptableRatings.includes(heuristicRating);
    const factualScorePass = factualMinScore >= thresholds.factualMinScore;
    
    // Safety override: If data has severe indicators, summary MUST have safety cues
    const safetyOverride = severeInData && !safetyCuePresent;
    
    // Final decision
    const pass = 
      factualPass &&
      heuristicPass &&
      safetyPass &&
      !safetyOverride;
    
    // Decision category
    let decision = 'PASS';
    let action = 'PUBLISH';
    let failReasons = [];
    
    if (!factualPass) {
      failReasons.push('Factual QA failed - claims not supported by facts');
    }
    if (!heuristicPass) {
      failReasons.push(`Heuristic score ${heuristicFinalScore.toFixed(2)} below threshold ${thresholds.heuristicMinScore}`);
    }
    if (!safetyPass) {
      failReasons.push(`Safety score ${heuristicSafetyScore} below threshold ${thresholds.heuristicSafetyMin}`);
    }
    if (safetyOverride) {
      failReasons.push('CRITICAL: Severe data present but no safety cues in summary');
    }
    
    if (!pass) {
      // Determine if regeneration might help or needs admin review
      if (safetyOverride || (factual?.unsupported_claims?.length || 0) > 2) {
        decision = 'ADMIN_REVIEW';
        action = 'ESCALATE';
      } else if (failReasons.length === 1 && heuristicFinalScore >= 3.0) {
        decision = 'REGENERATE';
        action = 'RETRY';
      } else {
        decision = 'FAIL';
        action = 'ADMIN_REVIEW';
      }
    }
    
    // =============================================================================
    // OUTPUT
    // =============================================================================
    
    return [{
      json: {
        pass,
        decision,
        action,
        
        // Detailed breakdown
        evaluation: {
          factual: {
            pass: factualPass,
            scores: factualScores,
            minScore: factualMinScore,
            unsupportedClaims: factual?.unsupported_claims || [],
            missedInfo: factual?.missed_critical_info || []
          },
          heuristic: {
            pass: heuristicPass,
            finalScore: heuristicFinalScore,
            rating: heuristicRating,
            safetyScore: heuristicSafetyScore,
            allScores: heuristic?.scores || {}
          },
          safety: {
            pass: safetyPass,
            override: safetyOverride,
            severeInData,
            safetyCuePresent,
            safetyMatchCount,
            currentSevereFromFacts
          }
        },
        
        // Thresholds used
        thresholds,
        
        // Failure reasons (if any)
        failReasons: failReasons.length > 0 ? failReasons : null,
        
        // Metadata
        decidedAt: new Date().toISOString()
      }
    }];