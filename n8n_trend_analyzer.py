# n8n Questionnaire Trend Analyzer
# Analyzes score changes over time for mental health questionnaires
# Based on administration frequency and clinical significance guidelines

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Clinical trend interpretation based on reference table
TREND_GUIDELINES = {
    "phq": {
        "name": "PHQ-9",
        "frequency": "every session or 2 weeks or 4-6 weeks",
        "sensitivity": "sensitive to short-term changes in mood",
        "improvement_direction": "decrease",  # Lower scores = better
        "cutoffs": {"mild": 5, "moderate": 10, "moderately_severe": 15, "severe": 20}
    },
    "who-5": {
        "name": "WHO-5",
        "frequency": "every 4-6 weeks",
        "sensitivity": "sensitive to short-term changes in mood", 
        "improvement_direction": "increase",  # Higher scores = better
        "cutoffs": {"poor_wellbeing": 50, "depression_risk": 28}
    },
    "gad": {
        "name": "GAD-7",
        "frequency": "every 4-6 weeks",
        "sensitivity": "sensitive to short-term changes in mood",
        "improvement_direction": "decrease",  # Lower scores = better
        "cutoffs": {"mild": 5, "moderate": 10, "severe": 15}
    },
    "promis": {
        "name": "PROMIS Pediatric",
        "frequency": "every session, 4-6 weeks",
        "sensitivity": "sensitive to short-term changes in mood",
        "improvement_direction": "decrease",  # Lower T-scores = better
        "cutoffs": {"normal": 55, "mild": 60, "moderate": 70, "severe": 70}
    },
    "pedsql": {
        "name": "PedsQL",
        "frequency": "every 3-6 months",
        "sensitivity": "tracks medium-term functional changes",
        "improvement_direction": "increase",  # Higher scores = better
        "cutoffs": {"impaired_hrqol": 70, "borderline": 78}
    },
    "ces-dc": {
        "name": "CES-DC",
        "frequency": "every 6-12 months",
        "sensitivity": "less sensitive to small weekly shifts",
        "improvement_direction": "decrease",  # Lower scores = better
        "cutoffs": {"depression_risk": 15}
    },
    "scared": {
        "name": "SCARED",
        "frequency": "every 6-12 months", 
        "sensitivity": "less sensitive to small weekly shifts",
        "improvement_direction": "decrease",  # Lower scores = better
        "cutoffs": {"anxiety_disorder": 25}
    },
    "rses": {
        "name": "Rosenberg Self-Esteem Scale",
        "frequency": "every 6-12 months",
        "sensitivity": "tied to developmental trajectory",
        "improvement_direction": "increase",  # Higher scores = better self-esteem
        "cutoffs": {"low": 15, "normal_max": 25}
    },
    "sdq": {
        "name": "SDQ",
        "frequency": "every 6-12 months",
        "sensitivity": "less sensitive to small weekly shifts", 
        "improvement_direction": "decrease",  # Lower difficulties = better
        "cutoffs": {"normal": 13, "borderline": 16, "abnormal": 17}
    },
    "psc-17": {
        "name": "PSC-17",
        "frequency": "every 6-12 months",
        "sensitivity": "less sensitive to small weekly shifts",
        "improvement_direction": "decrease",  # Lower scores = better
        "cutoffs": {"positive_screen": 15}
    }
}

def get_questionnaire_key(questionnaire_name: str) -> str:
    """Extract questionnaire key from full name"""
    name = questionnaire_name.lower().strip()
    for key in TREND_GUIDELINES.keys():
        if key in name:
            return key
    return "unknown"

def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime object"""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except:
            return None

def validate_data_for_trends(results: List[Dict]) -> Dict[str, Any]:
    """
    Validate if data is suitable for trend analysis
    Returns validation info and warnings
    """
    validation = {
        "total_items": len(results),
        "items_with_dates": 0,
        "items_with_timepoints": 0,
        "date_range": None,
        "timepoint_range": None,
        "warnings": [],
        "can_analyze": False,
        "sort_method": None
    }
    
    valid_dates = []
    valid_timepoints = []
    
    for result in results:
        # Check dates
        date_obj = parse_date(result.get('date', ''))
        if date_obj:
            validation["items_with_dates"] += 1
            valid_dates.append(date_obj)
        
        # Check timepoints
        timepoint = result.get('timepoint', 0)
        if timepoint and timepoint > 0:
            validation["items_with_timepoints"] += 1
            valid_timepoints.append(timepoint)
    
    # Determine date range
    if valid_dates:
        valid_dates.sort()
        validation["date_range"] = {
            "earliest": valid_dates[0].strftime('%Y-%m-%d'),
            "latest": valid_dates[-1].strftime('%Y-%m-%d'),
            "span_days": (valid_dates[-1] - valid_dates[0]).days
        }
    
    # Determine timepoint range
    if valid_timepoints:
        valid_timepoints.sort()
        validation["timepoint_range"] = {
            "earliest": valid_timepoints[0],
            "latest": valid_timepoints[-1],
            "unique_timepoints": len(set(valid_timepoints))
        }
    
    # Determine if we can analyze and how
    if validation["items_with_dates"] >= 2:
        validation["can_analyze"] = True
        validation["sort_method"] = "date_primary"
        if validation["items_with_dates"] < validation["total_items"]:
            validation["warnings"].append(f"Using dates for {validation['items_with_dates']}/{validation['total_items']} items")
    elif validation["items_with_timepoints"] >= 2:
        validation["can_analyze"] = True
        validation["sort_method"] = "timepoint_only"
        validation["warnings"].append("No dates available - using timepoint ordering only")
        if validation["items_with_timepoints"] < validation["total_items"]:
            validation["warnings"].append(f"Using timepoints for {validation['items_with_timepoints']}/{validation['total_items']} items")
    else:
        validation["warnings"].append("Insufficient data: need at least 2 items with dates or timepoints")
    
    return validation

def sort_results_for_trends(results: List[Dict], sort_method: str) -> List[Dict]:
    """
    Sort results based on available data (dates, timepoints, or both)
    """
    if sort_method == "date_primary":
        # Primary: date, Secondary: timepoint
        def sort_key(result):
            date_obj = parse_date(result.get('date', ''))
            timepoint = result.get('timepoint', 0)
            # Use a very early date for missing dates, then sort by timepoint
            if date_obj:
                return (date_obj, timepoint)
            else:
                return (datetime(1900, 1, 1), timepoint)
        
        # Filter out items without either date or timepoint
        valid_results = []
        for result in results:
            date_obj = parse_date(result.get('date', ''))
            timepoint = result.get('timepoint', 0)
            if date_obj or timepoint > 0:
                valid_results.append(result)
        
        return sorted(valid_results, key=sort_key)
    
    elif sort_method == "timepoint_only":
        # Sort by timepoint only
        valid_results = [r for r in results if r.get('timepoint', 0) > 0]
        return sorted(valid_results, key=lambda x: x.get('timepoint', 0))
    
    else:
        return results

def calculate_days_between(date1: str, date2: str) -> int:
    """Calculate days between two date strings"""
    d1 = parse_date(date1)
    d2 = parse_date(date2)
    if d1 and d2:
        return abs((d2 - d1).days)
    return 0

def estimate_days_from_timepoints(initial_timepoint: int, latest_timepoint: int) -> int:
    """
    Estimate days between timepoints based on common administration intervals
    This is a rough estimate when dates are missing
    """
    timepoint_diff = abs(latest_timepoint - initial_timepoint)
    if timepoint_diff == 0:
        return 0
    
    # Rough estimate: assume 4-6 weeks between timepoints for most questionnaires
    # This is based on the reference table showing most tools administered every 4-6 weeks
    estimated_weeks_per_timepoint = 5  # Middle of 4-6 week range
    return timepoint_diff * estimated_weeks_per_timepoint * 7  # Convert to days

def determine_trend_direction(initial_score: float, latest_score: float, 
                            initial_severity: str, latest_severity: str,
                            improvement_direction: str) -> Dict[str, Any]:
    """
    Determine if change represents improvement, worsening, or stability.
    Reports raw score changes and severity level changes without imposing
    arbitrary magnitude thresholds. Clinical interpretation left to reviewers.
    """
    change = latest_score - initial_score
    
    # Did severity level change?
    severity_changed = initial_severity != latest_severity
    
    # Determine direction based on improvement_direction and score change
    if improvement_direction == "decrease":
        # Lower scores are better (PHQ-9, GAD-7, etc.)
        if change < 0:
            score_direction = "improvement"
        elif change > 0:
            score_direction = "worsening"
        else:
            score_direction = "stable"
    else:
        # Higher scores are better (WHO-5, PedsQL, RSES)
        if change > 0:
            score_direction = "improvement"
        elif change < 0:
            score_direction = "worsening"
        else:
            score_direction = "stable"
    
    return {
        "direction": score_direction,
        "change_value": change,
        "change_percentage": round((abs(change) / initial_score * 100), 1) if initial_score > 0 else 0,
        "severity_level_changed": severity_changed
    }

def get_severity_change(initial_severity: str, latest_severity: str) -> str:
    """Describe change in severity levels"""
    if initial_severity == latest_severity:
        return f"remained {initial_severity}"
    else:
        return f"from {initial_severity} to {latest_severity}"

def analyze_questionnaire_trends(processed_data: List[Dict]) -> Dict[str, Any]:
    """
    Main function to analyze trends across questionnaires
    
    Args:
        processed_data: List of processed questionnaire results from the preprocessing script
                       Each item should represent ONE aggregated timepoint per questionnaire
                       (e.g., all PHQ-9 questions at timepoint 1 combined into a single score)
        
    Returns:
        Structured trend analysis for LLM consumption
    """
    
    # Debug logging for n8n
    print(f"🔍 TREND ANALYSIS: Starting with {len(processed_data)} processed items")
    
    # Group by questionnaire
    questionnaire_groups = {}
    profile_id = "unknown"
    questionnaire_counts = {}
    
    for item in processed_data:
        data = item.get('json', {})
        questionnaire = data.get('questionnaire', '')
        
        # Count for debugging
        questionnaire_counts[questionnaire] = questionnaire_counts.get(questionnaire, 0) + 1
        
        # Validate that this looks like aggregated data (should have raw_total)
        if 'raw_total' not in data:
            print(f"Warning: Item missing 'raw_total' - may not be properly aggregated: {questionnaire}")
        
        if questionnaire not in questionnaire_groups:
            questionnaire_groups[questionnaire] = []
        questionnaire_groups[questionnaire].append(data)
    
    print(f"🔍 TREND ANALYSIS: Grouped into {len(questionnaire_groups)} questionnaires: {dict(questionnaire_counts)}")
    
    # Debug: Show what we received
    print(f"📊 Received {len(processed_data)} processed items")
    for q, items in questionnaire_groups.items():
        timepoints = [item.get('timepoint', '?') for item in items]
        print(f"   {q}: {len(items)} timepoints {timepoints}")
    
    # Analyze trends for each questionnaire
    trends = []
    overall_warnings = []
    
    for questionnaire, results in questionnaire_groups.items():
        if len(results) < 2:
            # Need at least 2 time points for trend analysis
            overall_warnings.append(f"{questionnaire}: Only {len(results)} assessment(s) - need at least 2 for trends")
            continue
        
        # Validate data quality for this questionnaire
        validation = validate_data_for_trends(results)
        
        if not validation["can_analyze"]:
            overall_warnings.extend([f"{questionnaire}: {w}" for w in validation["warnings"]])
            continue
        
        # Sort results using the determined method
        sorted_results = sort_results_for_trends(results, validation["sort_method"])
        
        if len(sorted_results) < 2:
            overall_warnings.append(f"{questionnaire}: Insufficient valid data after filtering")
            continue
        
        # Get questionnaire guidelines
        q_key = get_questionnaire_key(questionnaire)
        guidelines = TREND_GUIDELINES.get(q_key, {
            "name": questionnaire,
            "frequency": "unknown",
            "sensitivity": "unknown",
            "improvement_direction": "decrease"
        })
        
        # Extract timeline data
        initial = sorted_results[0]
        latest = sorted_results[-1]
        
        # Get appropriate score for analysis based on questionnaire type
        # PedsQL: Use transformed total_score (0-100 scale) instead of raw sum
        # PROMIS: Use T-score instead of raw sum
        # WHO-5: Use index score (0-100) instead of raw sum
        # Others: Use raw_total
        
        if q_key == "pedsql":
            # PedsQL stores transformed scores in derived
            initial_score = initial.get('derived', {}).get('total_score', initial.get('raw_total', 0))
            latest_score = latest.get('derived', {}).get('total_score', latest.get('raw_total', 0))
        elif q_key == "promis":
            # PROMIS stores T-scores in derived
            initial_score = initial.get('derived', {}).get('t_score', initial.get('raw_total', 0))
            latest_score = latest.get('derived', {}).get('t_score', latest.get('raw_total', 0))
        elif q_key == "who-5":
            # WHO-5 uses index score (0-100)
            initial_score = initial.get('who5_index', initial.get('raw_total', 0) * 4)
            latest_score = latest.get('who5_index', latest.get('raw_total', 0) * 4)
        else:
            # All other questionnaires use raw_total
            initial_score = initial.get('raw_total', 0)
            latest_score = latest.get('raw_total', 0)
        
        # Calculate trend
        trend_analysis = determine_trend_direction(
            initial_score, latest_score,
            initial.get('severity', ''), latest.get('severity', ''),
            guidelines["improvement_direction"]
        )
        
        # Build history
        history = []
        for result in sorted_results:
            # Use same score extraction logic as main analysis
            if q_key == "pedsql":
                score = result.get('derived', {}).get('total_score', result.get('raw_total', 0))
            elif q_key == "promis":
                score = result.get('derived', {}).get('t_score', result.get('raw_total', 0))
            elif q_key == "who-5":
                score = result.get('who5_index', result.get('raw_total', 0) * 4)
            else:
                score = result.get('raw_total', 0)
                
            history.append({
                "date": result.get('date', ''),
                "timepoint": result.get('timepoint', 0),
                "score": score,
                "severity": result.get('severity', ''),
                "clinical_flags": result.get('clinical_flags', [])
            })
        
        # Calculate time span based on available data
        initial_date = initial.get('date', '')
        latest_date = latest.get('date', '')
        days_span = 0
        timeline_method = "unknown"
        
        if initial_date and latest_date:
            days_span = calculate_days_between(initial_date, latest_date)
            timeline_method = "actual_dates"
        elif initial.get('timepoint') and latest.get('timepoint'):
            days_span = estimate_days_from_timepoints(
                initial.get('timepoint', 0), 
                latest.get('timepoint', 0)
            )
            timeline_method = "estimated_from_timepoints"
        
        # Build timeline info
        period_start = initial_date or f'timepoint {initial.get("timepoint", "?")}'
        period_end = latest_date or f'timepoint {latest.get("timepoint", "?")}'
        
        timeline_info = {
            "period": f"{period_start} to {period_end}", 
            "days_span": days_span,
            "timeline_method": timeline_method,
            "number_of_assessments": len(sorted_results)
        }
        
        # Add validation warnings for this questionnaire
        questionnaire_warnings = [w for w in validation["warnings"]]
        
        # Build trend summary
        trend_summary = {
            "questionnaire": guidelines["name"],
            "questionnaire_key": q_key,
            "administration_info": {
                "recommended_frequency": guidelines["frequency"],
                "sensitivity": guidelines["sensitivity"]
            },
            "timeline": timeline_info,
            "data_quality": {
                "sort_method": validation["sort_method"],
                "warnings": questionnaire_warnings
            },
            "score_analysis": {
                "initial_score": initial_score,
                "latest_score": latest_score,
                "change": trend_analysis["change_value"],
                "change_percentage": trend_analysis["change_percentage"],
                "trend_direction": trend_analysis["direction"],
                "severity_level_changed": trend_analysis["severity_level_changed"]
            },
            "severity_analysis": {
                "initial_severity": initial.get('severity', ''),
                "latest_severity": latest.get('severity', ''),
                "severity_change": get_severity_change(
                    initial.get('severity', ''), 
                    latest.get('severity', '')
                )
            },
            "history": history
        }
        
        trends.append(trend_summary)
    
    # Generate overall summary
    total_assessments = sum(len(results) for results in questionnaire_groups.values())
    improving_trends = sum(1 for t in trends if t["score_analysis"]["trend_direction"] == "improvement")
    worsening_trends = sum(1 for t in trends if t["score_analysis"]["trend_direction"] == "worsening")
    stable_trends = sum(1 for t in trends if t["score_analysis"]["trend_direction"] == "stable")
    
    return {
        "profile_summary": {
            "total_questionnaires": len(questionnaire_groups),
            "total_assessments": total_assessments,
            "questionnaires_with_trends": len(trends)
        },
        "trend_overview": {
            "improving": improving_trends,
            "worsening": worsening_trends, 
            "stable": stable_trends
        },
        "data_quality": {
            "overall_warnings": overall_warnings,
            "questionnaires_excluded": len(questionnaire_groups) - len(trends)
        },
        "detailed_trends": trends,
        "clinical_notes": [
            f"Analysis based on {len(trends)} questionnaires with multiple time points",
            "Trend directions consider questionnaire-specific improvement patterns (higher/lower scores)",
            "Score changes reported as raw values and percentages for transparent interpretation",
            "Severity level changes indicate crossing clinical cut-off thresholds",
            "Clinical significance interpretation left to reviewers based on context and expertise",
            "Timeline estimates used when dates missing (based on typical 4-6 week intervals)"
        ]
    }

# =============================================================================
# n8n CODE NODE EXECUTION (Direct execution - no function wrappers)
# =============================================================================
# Note: In n8n, 'items' is a global variable provided by the platform
# The following code is designed to run directly in an n8n Code node

# Check if running in n8n environment
if 'items' in globals():
    try:
        # Debug: Log what we received from previous node (preprocessor)
        print(f"🔍 n8n TREND DEBUG: Received {len(items)} processed items from preprocessor")
        
        if items:
            sample_item = items[0].get('json', {})
            print(f"🔍 n8n TREND DEBUG: Sample item keys: {list(sample_item.keys())}")
            print(f"🔍 n8n TREND DEBUG: Sample questionnaire: {sample_item.get('questionnaire', 'N/A')}")
            print(f"🔍 n8n TREND DEBUG: Sample timepoint: {sample_item.get('timepoint', 'N/A')}")
        
        # Perform trend analysis
        trend_analysis = analyze_questionnaire_trends(items)
        
        # Debug: Log results
        print(f"✅ n8n TREND SUCCESS: Generated trend analysis")
        print(f"   → Analyzed {trend_analysis['profile_summary']['questionnaires_with_trends']} questionnaires")
        print(f"   → Improving: {trend_analysis['trend_overview']['improving']}, Worsening: {trend_analysis['trend_overview']['worsening']}, Stable: {trend_analysis['trend_overview']['stable']}")
        
        # Log summary of trends
        for trend in trend_analysis.get('detailed_trends', []):
            q_name = trend.get('questionnaire', 'Unknown')
            direction = trend['score_analysis']['trend_direction']
            change = trend['score_analysis']['change']
            print(f"   → {q_name}: {direction} (change: {change:+.1f})")
        
        # Return trend analysis to next n8n node
        return [{'json': trend_analysis}]

    except Exception as e:
        # Return detailed error information for n8n debugging
        import traceback
        
        error_details = {
            'error_message': str(e),
            'error_type': type(e).__name__,
            'input_items_count': len(items) if 'items' in globals() else 0,
            'traceback': traceback.format_exc(),
            'debug_info': {
                'items_available': 'items' in globals(),
                'items_type': type(items).__name__ if 'items' in globals() else 'undefined',
                'help': 'Check that this Code node is connected after the Questionnaire Preprocessor node',
                'expected_input': 'List of processed questionnaire items with questionnaire, timepoint, raw_total, severity fields'
            }
        }
        
        print(f"❌ n8n TREND ERROR: {str(e)}")
        print(f"🔍 n8n TREND DEBUG: Error details logged in output")
        
        # Return error as JSON for next node
        return [{'json': error_details}]
