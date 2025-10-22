#!/usr/bin/env python3
"""
Local Questionnaire Preprocessor
Standalone version that can read Excel files and process questionnaire data locally
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import math
import argparse
import sys

# Clinical cut-offs and scoring information from reference table
QUESTIONNAIRE_CUTOFFS = {
    "phq-9": {
        "scale_range": "0-27",
        "direction": "higher worse", 
        "cutoffs": {"mild": 5, "moderate": 10, "moderately_severe": 15, "severe": 20},
        "clinical_flag": {"threshold": 10, "meaning": "likely MDD"}
    },
    "gad-7": {
        "scale_range": "0-21", 
        "direction": "higher worse",
        "cutoffs": {"mild": 5, "moderate": 10, "severe": 15}
    },
    "who-5": {
        "scale_range": "0-25 raw, 0-100 index",
        "direction": "lower worse", 
        "cutoffs": {"poor_wellbeing": 50, "depression_risk": 28},
        "transformation": "multiply raw by 4"
    },
    "promis-depression": {
        "scale_range": "T-score (mean 50, SD 10)",
        "direction": "higher worse",
        "cutoffs": {"normal": 55, "mild": 60, "moderate": 70, "severe": 70}
    },
    "promis-anxiety": {
        "scale_range": "T-score (mean 50, SD 10)",
        "direction": "higher worse",
        "cutoffs": {"normal": 55, "mild": 60, "moderate": 70, "severe": 70}
    },
    "promis-life": {
        "scale_range": "T-score (mean 50, SD 10)",
        "direction": "lower worse",
        "cutoffs": {"poor": 40, "below_average": 45}
    },
    "pedsql": {
        "scale_range": "0-100 transformed", 
        "direction": "lower worse",
        "cutoffs": {"impaired_hrqol": 70}
    },
    "ces-dc": {
        "scale_range": "0-60",
        "direction": "higher worse",
        "cutoffs": {"depression_risk": 15}
    },
    "scared": {
        "scale_range": "0-82 total",
        "direction": "higher worse",
        "cutoffs": {"anxiety_disorder": 25},
        "subscales": {"panic": 7, "social": 8, "school_phobia": 3, "separation": 5, "gad": 9}
    },
    "rses": {
        "scale_range": "0-30", 
        "direction": "varies",
        "cutoffs": {"low": 15, "normal_min": 15, "normal_max": 25, "high": 25}
    },
    "sdq": {
        "scale_range": "0-40 total difficulties",
        "direction": "higher worse", 
        "cutoffs": {"normal": 13, "borderline": 16, "abnormal": 17}
    },
    "psc-17": {
        "scale_range": "0-34",
        "direction": "higher worse",
        "cutoffs": {"positive_screen": 15},
        "subscales": {"internalizing": 5, "attention": 7, "externalizing": 7}
    }
}

def to_iso_date(value: Any) -> str:
    """Convert various date formats to ISO date string"""
    if not value:
        return ''
    try:
        if isinstance(value, str):
            # Handle various date formats
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        elif hasattr(value, 'year'):
            # Handle datetime/Timestamp objects (pandas Timestamp, datetime.datetime)
            dt = value
        elif isinstance(value, (int, float)):
            # Handle Excel serial date numbers (days since 1900-01-01)
            # Excel date system: 1 = 1900-01-01, 2 = 1900-01-02, etc.
            # Note: Excel has a bug treating 1900 as a leap year, but for dates after 1900-02-28 this doesn't matter
            excel_epoch = datetime(1899, 12, 30)  # Use Dec 30, 1899 to account for Excel's quirk
            dt = excel_epoch + timedelta(days=int(value))
        else:
            return ''  # Can't parse, return empty instead of today's date
        return dt.strftime('%Y-%m-%d')
    except:
        return ''

def safe_number(value: Any) -> float:
    """Safely convert value to number"""
    try:
        return float(value) if value is not None else 0.0
    except:
        return 0.0

def safe_round(value: Any) -> int:
    """Safely round value to integer"""
    return round(safe_number(value))

def get_questionnaire_info(questionnaire: str) -> Dict[str, Any]:
    """Get cut-off and scoring information for a questionnaire"""
    if not questionnaire:
        return {}
    
    q_name = questionnaire.lower().strip()
    
    # Find matching questionnaire in our cut-offs
    for key, info in QUESTIONNAIRE_CUTOFFS.items():
        if key in q_name:
            return info.copy()
    
    return {"scale_range": "unknown", "direction": "unknown", "cutoffs": {}}

# Severity functions based on reference table
def phq9_severity(score: int) -> str:
    """PHQ-9 severity: 5=mild, 10=moderate, 15=moderately severe, ≥20=severe"""
    if score <= 4:
        return 'minimal'
    elif score <= 9:
        return 'mild'
    elif score <= 14:
        return 'moderate'
    elif score <= 19:
        return 'moderately severe'
    else:
        return 'severe'

def gad7_severity(score: int) -> str:
    """GAD-7 severity: 5=mild, 10=moderate, 15=severe"""
    if score <= 4:
        return 'minimal'
    elif score <= 9:
        return 'mild'
    elif score <= 14:
        return 'moderate'
    else:
        return 'severe'

def who5_index(raw_score: int) -> int:
    """WHO-5: raw 0-25 multiplied by 4 = index 0-100"""
    return max(0, min(100, raw_score * 4))

def normalize_text(text: str) -> str:
    """Normalize text for comparison"""
    return str(text or '').strip().lower()

def includes_any(text: str, keywords: List[str]) -> bool:
    """Check if text includes any of the keywords"""
    norm_text = normalize_text(text)
    return any(normalize_text(keyword) in norm_text for keyword in keywords)

def score_subscales(responses: List[Dict], mapping: Dict[str, callable]) -> Dict[str, Dict[str, int]]:
    """Score subscales based on dimension mapping"""
    subscales = {}
    for name, predicate in mapping.items():
        matching_responses = [r for r in responses if predicate(r)]
        total = sum(safe_number(r.get('answer', 0)) for r in matching_responses)
        subscales[name] = {
            'total': int(total),
            'count': len(matching_responses)
        }
    return subscales

def read_excel_data(file_path: str) -> List[Dict]:
    """Read Excel file and convert to the format expected by the preprocessor"""
    print(f"📖 Reading Excel file: {file_path}")
    
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        print(f"📊 Loaded {len(df)} rows from Excel")
        print(f"📊 Columns: {list(df.columns)}")
        
        # Convert DataFrame to list of items in n8n format
        items = []
        for index, row in df.iterrows():
            # Convert row to dictionary and handle NaN values
            row_dict = {}
            for col, value in row.items():
                if pd.isna(value):
                    row_dict[col] = None
                else:
                    row_dict[col] = value
            
            # Wrap in n8n format
            items.append({'json': row_dict})
        
        print(f"✅ Converted to {len(items)} items for processing")
        return items
        
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        sys.exit(1)

def preprocess_questionnaire_data(items: List[Dict]) -> List[Dict]:
    """
    Main preprocessing function for questionnaire data
    
    Args:
        items: List of raw questionnaire items
        
    Returns:
        List of processed items with computed scores, severities, and flags
    """
    
    # Debug logging
    print(f"🔍 PREPROCESSING: Starting with {len(items)} raw items")
    
    # Step A: Normalize individual rows
    rows = []
    questionnaire_counts = {}
    
    for item in items:
        json_data = item.get('json', {})
        questionnaire = str(json_data.get('questionnaire', '')).strip()
        
        # Count questionnaires for debugging
        questionnaire_counts[questionnaire] = questionnaire_counts.get(questionnaire, 0) + 1
        
        # Skip rows with NaN/None/empty questionnaire (metadata rows)
        if not questionnaire or questionnaire.lower() in ['nan', 'none', '<na>', 'null']:
            continue
            
        row = {
            'questionnaire': questionnaire,
            'timepoint': safe_round(json_data.get('timepoints', 0)),  # Use 'timepoints' as primary field
            'date': to_iso_date(json_data.get('date')),
            'question': str(json_data.get('question', '')).strip(),
            'answer_int': safe_number(json_data.get('answer', 0)),
            'answer_raw': safe_number(json_data.get('answer', 0)),
            'dimension': str(json_data.get('dimension', '')).strip(),
            'free_text': str(json_data.get('free_text', '')).strip() if json_data.get('free_text') and not (isinstance(json_data.get('free_text'), float) and math.isnan(json_data.get('free_text'))) else '',
            'response_options': str(json_data.get('response_options', '')).strip()
        }
        rows.append(row)
    
    print(f"🔍 PREPROCESSING: Found questionnaires: {dict(questionnaire_counts)}")
    
    # Step B: Group by questionnaire + timepoint
    groups = {}
    for row in rows:
        key = f"{row['questionnaire']}::{row['timepoint']}"
        if key not in groups:
            groups[key] = {
                'questionnaire': row['questionnaire'],
                'timepoint': row['timepoint'],
                'date': row['date'],
                'responses': [],
                'free_text': row['free_text']
            }
        
        # Accumulate free text if present in this row
        if row['free_text'] and row['free_text'] not in groups[key]['free_text']:
            if groups[key]['free_text']:
                groups[key]['free_text'] += ' | ' + row['free_text']
            else:
                groups[key]['free_text'] = row['free_text']
        
        groups[key]['responses'].append({
            'question': row['question'],
            'answer': row['answer_int'],
            'dimension': row['dimension'],
            'response_options': row['response_options']
        })
    
    print(f"🔍 PREPROCESSING: Created {len(groups)} groups: {list(groups.keys())}")
    
    # Step C: Process each questionnaire group with cut-off focus
    results = []
    for group in groups.values():
        name = normalize_text(group['questionnaire'])
        total = sum(safe_number(r.get('answer', 0)) for r in group['responses'])
        
        print(f"🔍 PROCESSING: {group['questionnaire']} -> name='{name}', total={total}")
        
        # Get questionnaire-specific cut-off information
        q_info = get_questionnaire_info(group['questionnaire'])
        
        result = {
            'questionnaire': group['questionnaire'],
            'timepoint': group['timepoint'],
            'date': group['date'],
            'raw_total': int(total),
            'scale_info': {
                'range': q_info.get('scale_range', 'unknown'),
                'direction': q_info.get('direction', 'unknown'),
                'cutoffs': q_info.get('cutoffs', {})
            },
            'severity': '',
            'clinical_flags': [],
            'derived': {},  # Initialize derived dictionary
            'responses': group['responses'],
            'free_text': group['free_text']
        }
        
        # PHQ-9
        if 'phq-9' in name or 'phq9' in name or 'phq' in name:
            cutoffs = q_info.get('cutoffs', {})
            result['severity'] = phq9_severity(int(total))
            result['derived']['scale'] = 'PHQ-9 (0-27, higher worse)'
            result['derived']['severity_level'] = result['severity']
            result['derived']['total_score'] = int(total)
            
            # Apply clinical cut-offs
            if total >= cutoffs.get('severe', 20):
                result['clinical_flags'].append(f'PHQ-9 ≥{cutoffs.get("severe", 20)} (severe depression)')
            elif total >= cutoffs.get('moderately_severe', 15):
                result['clinical_flags'].append(f'PHQ-9 ≥{cutoffs.get("moderately_severe", 15)} (moderately severe)')
            elif total >= cutoffs.get('moderate', 10):
                result['clinical_flags'].append(f'PHQ-9 ≥{cutoffs.get("moderate", 10)} (moderate depression)')
            elif total >= cutoffs.get('mild', 5):
                result['clinical_flags'].append(f'PHQ-9 ≥{cutoffs.get("mild", 5)} (mild depression)')
                
            # Clinical significance flag
            clinical_flag = q_info.get('clinical_flag', {})
            if total >= clinical_flag.get('threshold', 10):
                result['clinical_flags'].append(f'PHQ-9 ≥{clinical_flag.get("threshold", 10)} suggests {clinical_flag.get("meaning", "clinical attention")}')
        
        # WHO-5
        elif any(x in name for x in ['who-5', 'who5', 'who 5']):
            cutoffs = q_info.get('cutoffs', {})
            index = who5_index(int(total))
            result['who5_index'] = index
            result['derived']['scale'] = 'WHO-5 (0-100 index, lower worse)'
            result['derived']['raw_score'] = int(total)
            result['derived']['total_score'] = int(total)  # Add total_score for consistency
            result['derived']['index_score'] = index
            result['severity'] = 'reduced well-being' if index <= cutoffs.get('poor_wellbeing', 50) else 'adequate well-being'
            result['derived']['severity_level'] = result['severity']
            
            # Apply WHO-5 cut-offs
            if index <= cutoffs.get('depression_risk', 28):
                result['clinical_flags'].append(f'WHO-5 ≤{cutoffs.get("depression_risk", 28)} indicates depression risk')
            elif index <= cutoffs.get('poor_wellbeing', 50):
                result['clinical_flags'].append(f'WHO-5 ≤{cutoffs.get("poor_wellbeing", 50)} suggests poor well-being')
        
        # GAD-7
        elif any(x in name for x in ['gad-7', 'gad7', 'gad 7']):
            cutoffs = q_info.get('cutoffs', {})
            result['severity'] = gad7_severity(int(total))
            result['derived']['scale'] = 'GAD-7 (0-21, higher worse)'
            result['derived']['severity_level'] = result['severity']
            result['derived']['total_score'] = int(total)
            
            # Apply GAD-7 cut-offs
            if total >= cutoffs.get('severe', 15):
                result['clinical_flags'].append(f'GAD-7 ≥{cutoffs.get("severe", 15)} (severe anxiety)')
            elif total >= cutoffs.get('moderate', 10):
                result['clinical_flags'].append(f'GAD-7 ≥{cutoffs.get("moderate", 10)} (moderate anxiety)')
            elif total >= cutoffs.get('mild', 5):
                result['clinical_flags'].append(f'GAD-7 ≥{cutoffs.get("mild", 5)} (mild anxiety)')
        
        # PROMIS (Depression, Anxiety, Life Satisfaction)
        elif 'promis' in name:
            if 'depression' in name:
                result['derived']['scale'] = 'PROMIS Depression T-score (mean 50, SD 10, higher worse)'
                result['derived']['note'] = 'Higher scores indicate more depression symptoms'
            elif 'anxiety' in name:
                result['derived']['scale'] = 'PROMIS Anxiety T-score (mean 50, SD 10, higher worse)'
                result['derived']['note'] = 'Higher scores indicate more anxiety symptoms'
            elif 'life' in name or 'satisfaction' in name:
                result['derived']['scale'] = 'PROMIS Life Satisfaction T-score (mean 50, SD 10, lower worse)'
                result['derived']['note'] = 'Higher scores indicate better life satisfaction'
            else:
                result['derived']['scale'] = 'PROMIS Pediatric T-score (mean 50, SD 10)'
                result['derived']['note'] = 'Item labels vary by form; interpretation relies on T-scores'
            
            # For PROMIS, we need actual T-scores from the answer field or calculate from raw scores
            # Since the Excel has raw answer values, we'll provide a note about T-score conversion
            avg_score = total / len(group['responses']) if group['responses'] else 0
            result['derived']['raw_score'] = int(total)
            result['derived']['total_score'] = int(total)  # Add total_score for consistency
            result['derived']['average_response'] = round(avg_score, 2)
            result['severity'] = 'requires T-score conversion for clinical interpretation'
            result['derived']['severity_level'] = result['severity']
            result['clinical_flags'].append(f'PROMIS raw total: {int(total)}. Convert to T-scores using official tables for clinical interpretation.')
        
        # PSC-17
        elif any(x in name for x in ['psc-17', 'psc17', 'psc 17', 'Pediatric Symptom Checklist – 17 (PSC-17)', 'psc']):
            print(f"🔍 PSC-17 DEBUG: Processing {group['questionnaire']} with total={total}")
            result['derived']['scale'] = 'PSC-17 (total ≥15 positive; subscales Internalizing ≥5, Attention ≥7, Externalizing ≥7)'
            result['derived']['total_score'] = int(total)
            result['severity'] = 'positive screen (≥15)' if total >= 15 else 'below threshold'
            result['derived']['severity_level'] = result['severity']
            
            # Subscales by dimension
            subscales = score_subscales(group['responses'], {
                'Internalizing': lambda r: includes_any(r['dimension'], ['internalizing']),
                'Attention': lambda r: includes_any(r['dimension'], ['attention']),
                'Externalizing': lambda r: includes_any(r['dimension'], ['externalizing'])
            })
            result['derived']['subscales'] = subscales
            
            # Subscale flags
            if subscales.get('Internalizing', {}).get('total', 0) >= 5:
                result['clinical_flags'].append('PSC-17 Internalizing ≥5')
            if subscales.get('Attention', {}).get('total', 0) >= 7:
                result['clinical_flags'].append('PSC-17 Attention ≥7')
            if subscales.get('Externalizing', {}).get('total', 0) >= 7:
                result['clinical_flags'].append('PSC-17 Externalizing ≥7')
        
        # PedsQL - Proper scoring with reverse transformation
        elif 'pedsql' in name:
            result['derived']['scale'] = 'PedsQL (0-100, higher better)'
            result['derived']['note'] = 'Scores reverse-transformed: 0→100, 1→75, 2→50, 3→25, 4→0'
            
            # Transform raw scores (0-4) to PedsQL scale (0-100)
            def transform_pedsql_score(raw_score):
                """Transform raw PedsQL score (0-4) to 0-100 scale"""
                transformation_map = {0: 100, 1: 75, 2: 50, 3: 25, 4: 0}
                return transformation_map.get(int(raw_score), None)
            
            # Group responses by subscale/dimension
            subscales = {
                'Physical': [],
                'Emotional': [],
                'Social': [],
                'School': []
            }
            
            # Categorize responses by dimension
            for response in group['responses']:
                raw_score = response.get('answer', 0)
                dimension = response.get('dimension', '').lower()
                transformed_score = transform_pedsql_score(raw_score)
                
                if transformed_score is not None:  # Valid score (0-4 range)
                    if 'physical' in dimension:
                        subscales['Physical'].append(transformed_score)
                    elif 'emotional' in dimension:
                        subscales['Emotional'].append(transformed_score)
                    elif 'social' in dimension:
                        subscales['Social'].append(transformed_score)
                    elif 'school' in dimension:
                        subscales['School'].append(transformed_score)
                    # No fallback - items without proper dimension are ignored
            
            # Define expected items per subscale for PedsQL
            PEDSQL_SUBSCALE_ITEMS = {
                'Physical': 8,      # Physical Functioning (8 items)
                'Emotional': 5,     # Emotional Functioning (5 items) 
                'Social': 5,        # Social Functioning (5 items)
                'School': 5         # School Functioning (5 items)
            }
            
            # Calculate subscale scores (mean of transformed scores)
            subscale_scores = {}
            valid_subscales = []
            
            for subscale_name, scores in subscales.items():
                expected_items = PEDSQL_SUBSCALE_ITEMS.get(subscale_name, len(scores))
                answered_items = len(scores)
                
                if answered_items >= (expected_items * 0.5):  # At least 50% answered
                    subscale_mean = sum(scores) / len(scores)
                    subscale_scores[subscale_name] = {
                        'score': round(subscale_mean, 2),
                        'items_answered': answered_items,
                        'items_expected': expected_items,
                        'completion_rate': round((answered_items / expected_items) * 100, 1),
                        'transformed_scores': scores
                    }
                    valid_subscales.append(subscale_name)
                else:
                    # Don't calculate score - insufficient data
                    subscale_scores[subscale_name] = {
                        'score': None,
                        'items_answered': answered_items,
                        'items_expected': expected_items,
                        'completion_rate': round((answered_items / expected_items) * 100, 1),
                        'reason': 'Insufficient data (>50% missing)',
                        'transformed_scores': scores
                    }
            
            # Calculate summary scores (only from valid subscales that passed 50% rule)
            all_transformed_scores = []
            psychosocial_scores = []
            
            for subscale_name, subscale_data in subscale_scores.items():
                # Only include scores from subscales that have valid scores (passed 50% rule)
                if subscale_data.get('score') is not None:
                    scores = subscale_data['transformed_scores']
                    all_transformed_scores.extend(scores)
                    
                    # Psychosocial includes Emotional, Social, School (not Physical)
                    if subscale_name in ['Emotional', 'Social', 'School']:
                        psychosocial_scores.extend(scores)
            
            # Store detailed results
            result['derived']['subscale_scores'] = subscale_scores
            result['derived']['raw_total'] = int(total)  # Keep original sum for reference
            
            # Calculate main scores
            if all_transformed_scores:
                total_scale_score = sum(all_transformed_scores) / len(all_transformed_scores)
                result['derived']['total_scale_score'] = round(total_scale_score, 2)
                result['derived']['total_score'] = round(total_scale_score, 2)  # For consistency
                
                # Physical Health Summary (same as Physical subscale, if valid)
                if 'Physical' in subscale_scores and subscale_scores['Physical'].get('score') is not None:
                    result['derived']['physical_health_summary'] = subscale_scores['Physical']['score']
                
                # Psychosocial Health Summary
                if psychosocial_scores:
                    psychosocial_summary = sum(psychosocial_scores) / len(psychosocial_scores)
                    result['derived']['psychosocial_health_summary'] = round(psychosocial_summary, 2)
                
                # Set severity based on total score
                if total_scale_score < 70:
                    result['severity'] = 'possible impaired HRQoL'
                    result['clinical_flags'].append(f'PedsQL Total Score {total_scale_score:.1f} < 70 (possible impaired HRQoL)')
                elif total_scale_score <= 78:
                    result['severity'] = 'borderline HRQoL'
                    result['clinical_flags'].append(f'PedsQL Total Score {total_scale_score:.1f} ≤ 78 (borderline HRQoL)')
                else:
                    result['severity'] = 'typical range'
                
                result['derived']['severity_level'] = result['severity']
                
                # Add subscale-specific flags
                for subscale_name, subscale_data in subscale_scores.items():
                    subscale_score = subscale_data.get('score')
                    if subscale_score is not None:
                        if subscale_score < 70:
                            result['clinical_flags'].append(f'PedsQL {subscale_name} {subscale_score:.1f} < 70 (possible impairment)')
                    else:
                        # Flag subscales with insufficient data
                        completion_rate = subscale_data.get('completion_rate', 0)
                        result['clinical_flags'].append(f'PedsQL {subscale_name}: Insufficient data ({completion_rate}% complete, need ≥50%)')
            
            else:
                result['severity'] = 'insufficient valid responses'
                result['derived']['severity_level'] = result['severity']
                result['clinical_flags'].append('PedsQL: No valid responses in 0-4 range for transformation')
        
        # All other questionnaires - use generic cut-off approach
        else:
            print(f"🔍 GENERIC DEBUG: Processing {group['questionnaire']} with total={total}, name='{name}'")
            if 'psc' in name.lower() or 'pediatric' in name.lower():
                print(f"🔍 GENERIC DEBUG: PSC-17 fell through to generic handler!")
            cutoffs = q_info.get('cutoffs', {})
            result['severity'] = 'see cut-offs for interpretation'
            result['derived']['scale'] = f'{group["questionnaire"]} ({q_info.get("scale_range", "unknown range")})'
            result['derived']['total_score'] = int(total)
            result['derived']['direction'] = q_info.get('direction', 'unknown')
            
            # Apply any available cut-offs generically
            for threshold_name, threshold_value in cutoffs.items():
                if isinstance(threshold_value, (int, float)):
                    direction = q_info.get('direction', 'higher worse')
                    if 'higher' in direction and total >= threshold_value:
                        result['clinical_flags'].append(f'{group["questionnaire"]} ≥{threshold_value} ({threshold_name.replace("_", " ")})')
                    elif 'lower' in direction and total <= threshold_value:
                        result['clinical_flags'].append(f'{group["questionnaire"]} ≤{threshold_value} ({threshold_name.replace("_", " ")})')
            
            # Handle subscales if available
            subscales_info = q_info.get('subscales', {})
            if subscales_info:
                result['derived']['subscale_cutoffs'] = subscales_info
        
        results.append(result)
    
    print(f"✅ PREPROCESSING: Generated {len(results)} processed questionnaire groups")
    return results

def save_results(results: List[Dict], output_file: str):
    """Save results to JSON file"""
    print(f"💾 Saving results to: {output_file}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(results)} processed items to {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Process questionnaire data from Excel file')
    parser.add_argument('input_file', help='Path to Excel file')
    parser.add_argument('-o', '--output', default='processed_questionnaires.json', 
                       help='Output JSON file (default: processed_questionnaires.json)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    print("🚀 Local Questionnaire Preprocessor")
    print("=" * 50)
    
    # Read Excel data
    items = read_excel_data(args.input_file)
    
    # Process questionnaire data
    results = preprocess_questionnaire_data(items)
    
    # Save results
    save_results(results, args.output)
    
    # Summary
    print("\n📊 PROCESSING SUMMARY:")
    print("=" * 50)
    questionnaire_summary = {}
    for result in results:
        q_name = result['questionnaire']
        if q_name not in questionnaire_summary:
            questionnaire_summary[q_name] = 0
        questionnaire_summary[q_name] += 1
    
    for q_name, count in questionnaire_summary.items():
        print(f"  {q_name}: {count} assessment(s)")
    
    print(f"\n✅ Total: {len(results)} processed assessments")
    print(f"💾 Results saved to: {args.output}")

if __name__ == "__main__":
    main()
