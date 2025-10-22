#!/usr/bin/env python3
"""
Local Data Quality Validator
Standalone version that can validate processed questionnaire data locally
"""

import json
import argparse
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

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

def validate_preprocessed_data(items: List[Dict]) -> Dict[str, Any]:
    """
    Comprehensive validation of preprocessed questionnaire data
    
    Args:
        items: List of preprocessed items from the questionnaire preprocessor
        
    Returns:
        Validation report with data quality metrics, warnings, and pass/fail status
    """
    
    validation_report = {
        "status": "PASS",  # Will change to FAIL or WARNING if issues found
        "total_items": len(items),
        "validation_checks": {},
        "data_quality_metrics": {},
        "warnings": [],
        "errors": [],
        "recommendations": []
    }
    
    if not items:
        validation_report["status"] = "FAIL"
        validation_report["errors"].append("No data received - empty input")
        return validation_report
    
    # Items are already in the correct format (not wrapped in 'json' key for local processing)
    data_items = items
    
    # =========================================================================
    # CHECK 1: Required Fields Validation
    # =========================================================================
    required_fields = ['questionnaire', 'timepoint', 'raw_total', 'severity']
    optional_but_recommended = ['date', 'clinical_flags', 'derived', 'responses']
    
    items_with_all_required = 0
    items_with_dates = 0
    items_with_derived = 0
    items_with_responses = 0
    missing_fields_by_item = []
    
    for idx, item in enumerate(data_items):
        missing = [field for field in required_fields if field not in item or (item[field] is None or (isinstance(item[field], str) and not item[field].strip()))]
        if not missing:
            items_with_all_required += 1
        else:
            missing_fields_by_item.append({
                'item_index': idx,
                'questionnaire': item.get('questionnaire', 'Unknown'),
                'missing_fields': missing
            })
        
        if item.get('date'):
            items_with_dates += 1
        if item.get('derived') and isinstance(item['derived'], dict) and item['derived']:
            items_with_derived += 1
        if item.get('responses'):
            items_with_responses += 1
    
    validation_report["validation_checks"]["required_fields"] = {
        "pass": len(missing_fields_by_item) == 0,
        "items_with_all_required": items_with_all_required,
        "items_missing_fields": len(missing_fields_by_item),
        "details": missing_fields_by_item[:5]  # Show first 5 only
    }
    
    if missing_fields_by_item:
        validation_report["status"] = "FAIL"
        validation_report["errors"].append(
            f"{len(missing_fields_by_item)} items missing required fields: {required_fields}"
        )
    
    # =========================================================================
    # CHECK 2: Date/Timepoint Quality
    # =========================================================================
    valid_dates = []
    valid_timepoints = []
    invalid_dates = []
    
    for idx, item in enumerate(data_items):
        # Check dates
        date_str = item.get('date', '')
        date_obj = parse_date(date_str)
        if date_obj:
            valid_dates.append(date_obj)
        elif date_str and date_str.strip():
            invalid_dates.append({
                'item_index': idx,
                'questionnaire': item.get('questionnaire', 'Unknown'),
                'invalid_date': date_str
            })
        
        # Check timepoints
        timepoint = item.get('timepoint', 0)
        if timepoint and timepoint > 0:
            valid_timepoints.append(timepoint)
    
    # Determine date range
    date_range_info = None
    if valid_dates:
        valid_dates.sort()
        date_range_info = {
            "earliest": valid_dates[0].strftime('%Y-%m-%d'),
            "latest": valid_dates[-1].strftime('%Y-%m-%d'),
            "span_days": (valid_dates[-1] - valid_dates[0]).days,
            "total_with_dates": len(valid_dates)
        }
    
    # Determine timepoint range
    timepoint_range_info = None
    if valid_timepoints:
        valid_timepoints_sorted = sorted(valid_timepoints)
        timepoint_range_info = {
            "earliest": valid_timepoints_sorted[0],
            "latest": valid_timepoints_sorted[-1],
            "unique_timepoints": len(set(valid_timepoints)),
            "total_with_timepoints": len(valid_timepoints)
        }
    
    validation_report["validation_checks"]["date_timepoint_quality"] = {
        "items_with_dates": len(valid_dates),
        "items_with_valid_timepoints": len(valid_timepoints),
        "invalid_dates": len(invalid_dates),
        "date_range": date_range_info,
        "timepoint_range": timepoint_range_info
    }
    
    # Warnings for date/timepoint issues
    if len(valid_dates) < len(data_items):
        pct = (len(valid_dates) / len(data_items)) * 100
        validation_report["warnings"].append(
            f"Only {len(valid_dates)}/{len(data_items)} ({pct:.1f}%) items have valid dates"
        )
        if pct < 50:
            validation_report["recommendations"].append(
                "Consider adding dates to more items for better trend analysis"
            )
    
    if invalid_dates:
        validation_report["warnings"].append(
            f"{len(invalid_dates)} items have invalid date formats"
        )
    
    # =========================================================================
    # CHECK 3: Questionnaire Distribution & Grouping
    # =========================================================================
    questionnaire_groups = {}
    
    for item in data_items:
        q_name = item.get('questionnaire', 'Unknown')
        if q_name not in questionnaire_groups:
            questionnaire_groups[q_name] = {
                'count': 0,
                'timepoints': set(),
                'has_dates': 0,
                'has_derived': 0,
                'total_scores': []
            }
        
        questionnaire_groups[q_name]['count'] += 1
        questionnaire_groups[q_name]['timepoints'].add(item.get('timepoint', 0))
        if item.get('date'):
            questionnaire_groups[q_name]['has_dates'] += 1
        if item.get('derived') and item['derived']:
            questionnaire_groups[q_name]['has_derived'] += 1
        questionnaire_groups[q_name]['total_scores'].append(item.get('raw_total', 0))
    
    # Convert sets to counts for JSON serialization
    questionnaire_summary = {}
    questionnaires_ready_for_trends = []
    questionnaires_insufficient_data = []
    
    for q_name, info in questionnaire_groups.items():
        timepoint_count = len(info['timepoints'])
        questionnaire_summary[q_name] = {
            'total_assessments': info['count'],
            'unique_timepoints': timepoint_count,
            'assessments_with_dates': info['has_dates'],
            'assessments_with_derived': info['has_derived'],
            'score_range': {
                'min': min(info['total_scores']) if info['total_scores'] else 0,
                'max': max(info['total_scores']) if info['total_scores'] else 0
            }
        }
        
        # Check if ready for trend analysis (needs 2+ timepoints)
        if timepoint_count >= 2:
            questionnaires_ready_for_trends.append(q_name)
        else:
            questionnaires_insufficient_data.append(q_name)
    
    validation_report["data_quality_metrics"]["questionnaire_distribution"] = {
        "total_questionnaires": len(questionnaire_groups),
        "questionnaires_ready_for_trends": len(questionnaires_ready_for_trends),
        "questionnaires_insufficient_data": len(questionnaires_insufficient_data),
        "summary": questionnaire_summary
    }
    
    # Warnings for questionnaires with insufficient data
    if questionnaires_insufficient_data:
        validation_report["warnings"].append(
            f"{len(questionnaires_insufficient_data)} questionnaire(s) have only 1 timepoint - cannot analyze trends: {', '.join(questionnaires_insufficient_data)}"
        )
        validation_report["recommendations"].append(
            "Collect data at multiple timepoints to enable trend analysis"
        )
    
    # =========================================================================
    # CHECK 4: Derived Data Completeness
    # =========================================================================
    items_with_empty_derived = []
    items_with_scale_info = 0
    items_with_interpretations = 0
    
    for idx, item in enumerate(data_items):
        derived = item.get('derived')
        if derived and isinstance(derived, dict):
            if derived.get('scale'):
                items_with_scale_info += 1
            if derived.get('interpretations'):
                items_with_interpretations += 1
        else:
            items_with_empty_derived.append({
                'item_index': idx,
                'questionnaire': item.get('questionnaire', 'Unknown'),
                'timepoint': item.get('timepoint', '?')
            })

    # Calculate derived count based on items that are NOT empty
    final_items_with_derived = len(data_items) - len(items_with_empty_derived)

    validation_report["validation_checks"]["derived_data_quality"] = {
        "items_with_derived": final_items_with_derived,
        "items_with_empty_derived": len(items_with_empty_derived),
        "items_with_scale_info": items_with_scale_info,
        "items_with_interpretations": items_with_interpretations
    }
    
    if items_with_empty_derived:
        if len(items_with_empty_derived) == len(data_items):
            validation_report["status"] = "FAIL"
            validation_report["errors"].append(
                "All items have empty 'derived' dictionary - preprocessor may not be working correctly"
            )
        else:
            validation_report["warnings"].append(
                f"{len(items_with_empty_derived)} items have empty 'derived' data"
            )
    
    # =========================================================================
    # CHECK 5: Score Validity
    # =========================================================================
    items_with_zero_scores = []
    items_with_negative_scores = []
    
    for idx, item in enumerate(data_items):
        raw_total = item.get('raw_total', 0)
        if raw_total == 0:
            items_with_zero_scores.append({
                'item_index': idx,
                'questionnaire': item.get('questionnaire', 'Unknown'),
                'timepoint': item.get('timepoint', '?')
            })
        elif raw_total < 0:
            items_with_negative_scores.append({
                'item_index': idx,
                'questionnaire': item.get('questionnaire', 'Unknown'),
                'raw_total': raw_total
            })
    
    validation_report["validation_checks"]["score_validity"] = {
        "items_with_zero_scores": len(items_with_zero_scores),
        "items_with_negative_scores": len(items_with_negative_scores)
    }
    
    if items_with_negative_scores:
        validation_report["status"] = "FAIL"
        validation_report["errors"].append(
            f"{len(items_with_negative_scores)} items have negative scores (invalid)"
        )
    
    if len(items_with_zero_scores) > len(data_items) * 0.5:
        validation_report["warnings"].append(
            f"{len(items_with_zero_scores)} items have zero scores - verify this is expected"
        )
    
    # =========================================================================
    # CHECK 6: Trend Analysis Readiness
    # =========================================================================
    can_analyze_trends = False
    sort_method = None
    trend_readiness_issues = []
    
    if len(valid_dates) >= 2:
        can_analyze_trends = True
        sort_method = "date_primary"
    elif len(valid_timepoints) >= 2:
        can_analyze_trends = True
        sort_method = "timepoint_only"
        trend_readiness_issues.append("No dates available - will use timepoint ordering only")
    else:
        trend_readiness_issues.append("Need at least 2 items with dates or timepoints for trend analysis")
    
    validation_report["data_quality_metrics"]["trend_analysis_readiness"] = {
        "ready_for_trend_analysis": can_analyze_trends,
        "recommended_sort_method": sort_method,
        "issues": trend_readiness_issues,
        "questionnaires_with_trends": len(questionnaires_ready_for_trends),
        "total_questionnaires": len(questionnaire_groups)
    }
    
    if not can_analyze_trends:
        validation_report["warnings"].append(
            "Insufficient data for trend analysis - need at least 2 timepoints with dates or timepoint markers"
        )
    
    # =========================================================================
    # CHECK 7: Clinical Flags Review
    # =========================================================================
    items_with_clinical_flags = 0
    total_clinical_flags = 0
    critical_flags = []
    
    for item in data_items:
        flags = item.get('clinical_flags', [])
        if flags:
            items_with_clinical_flags += 1
            total_clinical_flags += len(flags)
            
            # Identify critical flags (severe, abnormal, etc.)
            for flag in flags:
                flag_lower = flag.lower()
                if any(keyword in flag_lower for keyword in ['severe', 'abnormal', 'high risk', 'clinical attention']):
                    critical_flags.append({
                        'questionnaire': item.get('questionnaire', 'Unknown'),
                        'timepoint': item.get('timepoint', '?'),
                        'flag': flag
                    })
    
    validation_report["data_quality_metrics"]["clinical_flags_summary"] = {
        "items_with_flags": items_with_clinical_flags,
        "total_flags": total_clinical_flags,
        "critical_flags": len(critical_flags),
        "critical_flags_details": critical_flags[:10]  # Show first 10
    }
    
    if critical_flags:
        validation_report["recommendations"].append(
            f"{len(critical_flags)} critical clinical flags detected - review before LLM processing"
        )
    
    # =========================================================================
    # FINAL STATUS DETERMINATION
    # =========================================================================
    if validation_report["errors"]:
        validation_report["status"] = "FAIL"
        validation_report["recommendations"].append(
            "Fix errors before proceeding to trend analysis or LLM processing"
        )
    elif validation_report["warnings"]:
        if validation_report["status"] != "FAIL":
            validation_report["status"] = "WARNING"
        validation_report["recommendations"].append(
            "Review warnings - data may still be usable but quality could be improved"
        )
    
    # Add summary
    validation_report["summary"] = {
        "total_items": len(data_items),
        "items_with_all_required_fields": items_with_all_required,
        "questionnaires_analyzed": len(questionnaire_groups),
        "ready_for_trend_analysis": can_analyze_trends,
        "critical_issues": len(validation_report["errors"]),
        "warnings": len(validation_report["warnings"]),
        "status": validation_report["status"]
    }
    
    return validation_report

def format_validation_report(validation: Dict[str, Any]) -> str:
    """Format validation report as human-readable text"""
    lines = []
    lines.append("=" * 70)
    lines.append("DATA QUALITY VALIDATION REPORT")
    lines.append("=" * 70)
    lines.append(f"Status: {validation['status']}")
    lines.append(f"Total Items: {validation['total_items']}")
    lines.append("")
    
    # Summary
    if validation.get('summary'):
        lines.append("SUMMARY:")
        for key, value in validation['summary'].items():
            lines.append(f"  {key}: {value}")
        lines.append("")
    
    # Errors
    if validation.get('errors'):
        lines.append("ERRORS:")
        for error in validation['errors']:
            lines.append(f"  ❌ {error}")
        lines.append("")
    
    # Warnings
    if validation.get('warnings'):
        lines.append("WARNINGS:")
        for warning in validation['warnings']:
            lines.append(f"  ⚠️  {warning}")
        lines.append("")
    
    # Recommendations
    if validation.get('recommendations'):
        lines.append("RECOMMENDATIONS:")
        for rec in validation['recommendations']:
            lines.append(f"  💡 {rec}")
        lines.append("")
    
    # Questionnaire Distribution
    if validation.get('data_quality_metrics', {}).get('questionnaire_distribution'):
        dist = validation['data_quality_metrics']['questionnaire_distribution']
        lines.append("QUESTIONNAIRE DISTRIBUTION:")
        for q_name, info in dist['summary'].items():
            lines.append(f"  {q_name}:")
            lines.append(f"    Assessments: {info['total_assessments']}")
            lines.append(f"    Timepoints: {info['unique_timepoints']}")
            lines.append(f"    Score Range: {info['score_range']['min']}-{info['score_range']['max']}")
        lines.append("")
    
    lines.append("=" * 70)
    return "\n".join(lines)

def load_processed_data(file_path: str) -> List[Dict]:
    """Load processed questionnaire data from JSON file"""
    print(f"📖 Loading processed data from: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ Loaded {len(data)} processed items")
        return data
        
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        sys.exit(1)

def save_validation_report(report: Dict[str, Any], output_file: str):
    """Save validation report to JSON file"""
    print(f"💾 Saving validation report to: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved validation report to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Validate processed questionnaire data')
    parser.add_argument('input_file', help='Path to processed JSON file')
    parser.add_argument('-o', '--output', default='validation_report.json', 
                       help='Output validation report file (default: validation_report.json)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    print("🔍 Local Data Quality Validator")
    print("=" * 50)
    
    # Load processed data
    processed_data = load_processed_data(args.input_file)
    
    # Validate data
    validation_report = validate_preprocessed_data(processed_data)
    
    # Print formatted report
    print("\n" + format_validation_report(validation_report))
    
    # Save validation report
    save_validation_report(validation_report, args.output)
    
    # Exit with appropriate code
    if validation_report['status'] == 'FAIL':
        print(f"\n❌ VALIDATION FAILED: {len(validation_report['errors'])} critical error(s) found")
        sys.exit(1)
    elif validation_report['status'] == 'WARNING':
        print(f"\n⚠️  VALIDATION PASSED WITH WARNINGS: {len(validation_report['warnings'])} warning(s)")
        sys.exit(0)
    else:
        print(f"\n✅ VALIDATION PASSED: All checks successful")
        sys.exit(0)

if __name__ == "__main__":
    main()
