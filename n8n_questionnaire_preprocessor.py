#!/usr/bin/env python3
"""
n8n Questionnaire Preprocessor (Python)
Converts raw questionnaire data into structured, interpreted results for LLM processing
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import math

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
        "cutoffs": {"impaired_hrqol": 70, "borderline": 78}
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

def promis_severity(t_score: float) -> str:
    """PROMIS Pediatric T-score interpretation"""
    if t_score <= 55:
        return 'within normal limits'
    elif t_score <= 60:
        return 'mild'
    elif t_score <= 70:
        return 'moderate'
    else:
        return 'severe'

def pedsql_flag(score: float) -> str:
    """PedsQL quality of life flag (0-100, lower worse)"""
    if score < 70:
        return 'possible impaired HRQoL (<70-78)'
    elif score <= 78:
        return 'borderline HRQoL (70-78)'
    else:
        return ''

def rses_band(score: int) -> str:
    """Rosenberg Self-Esteem Scale bands"""
    if score < 15:
        return 'low'
    elif score > 25:
        return 'high'
    else:
        return 'normal'

def detect_sdq_version(questionnaire_name: str) -> str:
    """Detect if SDQ is parent or self-completed version"""
    name_lower = questionnaire_name.lower()
    if 'youth' in name_lower or 'self' in name_lower or 'adolescent' in name_lower:
        return 'self_completed'
    elif 'parent' in name_lower or 'teacher' in name_lower:
        return 'parent'
    else:
        # Default to self-completed for youth report (11-17)
        return 'self_completed'

def get_sdq_cutoffs(version: str) -> Dict[str, Dict[str, Any]]:
    """Get SDQ cut-offs based on version (parent or self-completed)"""
    if version == 'self_completed':
        return {
            'total_difficulties': {
                'normal': (0, 15),
                'borderline': (16, 19),
                'abnormal': (20, 40)
            },
            'emotional': {
                'normal': (0, 5),
                'borderline': (6, 6),
                'abnormal': (7, 10)
            },
            'conduct': {
                'normal': (0, 3),
                'borderline': (4, 4),
                'abnormal': (5, 10)
            },
            'hyperactivity': {
                'normal': (0, 5),
                'borderline': (6, 6),
                'abnormal': (7, 10)
            },
            'peer_problems': {
                'normal': (0, 3),
                'borderline': (4, 5),
                'abnormal': (6, 10)
            },
            'prosocial': {
                'normal': (6, 10),
                'borderline': (5, 5),
                'abnormal': (0, 4)
            }
        }
    else:  # parent version
        return {
            'total_difficulties': {
                'normal': (0, 13),
                'borderline': (14, 16),
                'abnormal': (17, 40)
            },
            'emotional': {
                'normal': (0, 3),
                'borderline': (4, 4),
                'abnormal': (5, 10)
            },
            'conduct': {
                'normal': (0, 2),
                'borderline': (3, 3),
                'abnormal': (4, 10)
            },
            'hyperactivity': {
                'normal': (0, 5),
                'borderline': (6, 6),
                'abnormal': (7, 10)
            },
            'peer_problems': {
                'normal': (0, 2),
                'borderline': (3, 3),
                'abnormal': (4, 10)
            },
            'prosocial': {
                'normal': (6, 10),
                'borderline': (5, 5),
                'abnormal': (0, 4)
            }
        }

def interpret_sdq_score(score: int, subscale: str, cutoffs: Dict[str, tuple]) -> Dict[str, Any]:
    """Interpret a single SDQ score against cut-offs"""
    if subscale not in cutoffs:
        return {'band': 'unknown', 'interpretation': 'No cut-offs available'}
    
    ranges = cutoffs[subscale]
    
    # Check which band the score falls into
    if ranges['normal'][0] <= score <= ranges['normal'][1]:
        band = 'normal'
        interpretation = 'close to average - clinically significant problems in this area are unlikely'
    elif ranges['borderline'][0] <= score <= ranges['borderline'][1]:
        band = 'borderline'
        if subscale == 'prosocial':
            interpretation = 'slightly low, which may reflect clinically significant problems'
        else:
            interpretation = 'slightly raised, which may reflect clinically significant problems'
    else:  # abnormal range
        band = 'abnormal'
        if subscale == 'prosocial':
            interpretation = 'low - there is a substantial risk of clinically significant problems in this area'
        else:
            interpretation = 'high - there is a substantial risk of clinically significant problems in this area'
    
    return {
        'score': score,
        'band': band,
        'interpretation': interpretation
    }


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

def preprocess_questionnaire_data(items: List[Dict]) -> List[Dict]:
    """
    Main preprocessing function for questionnaire data
    
    Args:
        items: List of raw questionnaire items from n8n
        
    Returns:
        List of processed items with computed scores, severities, and flags
    """
    
    # Debug logging for n8n
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
            result['derived']['average_response'] = round(avg_score, 2)
            result['severity'] = 'requires T-score conversion for clinical interpretation'
            result['clinical_flags'].append(f'PROMIS raw total: {int(total)}. Convert to T-scores using official tables for clinical interpretation.')
        
        # PedsQL
        elif 'pedsql' in name:
            result['derived']['scale'] = 'PedsQL (0-100, lower worse)'
            result['derived']['note'] = 'Items have reverse scoring; interpretation relies on transformed scores'
            # Use average of item scores if they're already transformed to 0-100 range
            valid_scores = [r['answer'] for r in group['responses'] 
                          if 0 <= r['answer'] <= 100]
            if valid_scores:
                avg = sum(valid_scores) / len(valid_scores)
                result['derived']['score_0_to_100'] = round(avg)
                flag = pedsql_flag(avg)
                if flag:
                    result['clinical_flags'].append(flag)
                result['severity'] = 'lower quality of life' if avg < 70 else 'typical range'
            else:
                result['severity'] = 'needs transformed 0-100 scores'
                result['clinical_flags'].append('PedsQL requires linearly transformed scores (0=100, 1=75, 2=50, 3=25, 4=0)')
        
        # CES-DC
        elif any(x in name for x in ['ces-dc', 'cesdc', 'ces dc']):
            result['derived']['scale'] = 'CES-DC (≥15 suggests risk for depression)'
            result['derived']['total_score'] = int(total)
            result['severity'] = 'depression risk (≥15)' if total >= 15 else 'below risk threshold'
            result['derived']['severity_level'] = result['severity']
            if total >= 15:
                result['clinical_flags'].append('CES-DC positive screen (≥15)')
        
        # SCARED
        elif 'scared' in name:
            result['derived']['scale'] = 'SCARED (total ≥25 possible anxiety disorder; subscale cut-offs apply)'
            result['derived']['total_score'] = int(total)
            result['severity'] = 'possible anxiety disorder (≥25)' if total >= 25 else 'below screening threshold'
            result['derived']['severity_level'] = result['severity']
            
            # Subscales by dimension
            subscales = score_subscales(group['responses'], {
                'Panic': lambda r: includes_any(r['dimension'], ['panic']),
                'Generalized Anxiety (GAD)': lambda r: includes_any(r['dimension'], ['gad', 'generalized']),
                'Separation': lambda r: includes_any(r['dimension'], ['separation']),
                'Social': lambda r: includes_any(r['dimension'], ['social']),
                'School Phobia': lambda r: includes_any(r['dimension'], ['school'])
            })
            result['derived']['subscales'] = subscales
            
            # Subscale flags
            if subscales.get('Panic', {}).get('total', 0) >= 7:
                result['clinical_flags'].append('SCARED Panic ≥7')
            if subscales.get('Social', {}).get('total', 0) >= 8:
                result['clinical_flags'].append('SCARED Social ≥8')
            if subscales.get('School Phobia', {}).get('total', 0) >= 3:
                result['clinical_flags'].append('SCARED School ≥3')
            if subscales.get('Separation', {}).get('total', 0) >= 5:
                result['clinical_flags'].append('SCARED Separation ≥5')
            if subscales.get('Generalized Anxiety (GAD)', {}).get('total', 0) >= 9:
                result['clinical_flags'].append('SCARED GAD ≥9')
        
        # RSES
        elif any(x in name for x in ['rosenberg', 'rses']):
            result['derived']['scale'] = 'RSES (0-30; <15 low, 15-25 normal, >25 high)'
            result['derived']['note'] = 'Contains reverse-scored items; verify scoring before interpretation'
            result['derived']['total_score'] = int(total)
            result['severity'] = rses_band(int(total))
            result['derived']['severity_level'] = result['severity']
        
        # SDQ - Enhanced with version-specific interpretation
        elif 'sdq' in name:
            # Detect version (parent or self-completed)
            sdq_version = detect_sdq_version(group['questionnaire'])
            sdq_cutoffs = get_sdq_cutoffs(sdq_version)
            
            # Subscales by dimension
            subscales = score_subscales(group['responses'], {
                'Emotional': lambda r: includes_any(r['dimension'], ['emotional']),
                'Conduct': lambda r: includes_any(r['dimension'], ['conduct']),
                'Hyperactivity/Inattention': lambda r: includes_any(r['dimension'], ['hyperactivity', 'inattention']),
                'Peer Problems': lambda r: includes_any(r['dimension'], ['peer']),
                'Prosocial': lambda r: includes_any(r['dimension'], ['prosocial'])
            })
            
            # Total difficulties (exclude Prosocial)
            total_difficulties = (
                subscales.get('Emotional', {}).get('total', 0) +
                subscales.get('Conduct', {}).get('total', 0) +
                subscales.get('Hyperactivity/Inattention', {}).get('total', 0) +
                subscales.get('Peer Problems', {}).get('total', 0)
            )
            
            # Store raw scores
            result['derived']['raw_scores'] = {
                'total_difficulties': total_difficulties,
                'emotional': subscales.get('Emotional', {}).get('total', 0),
                'conduct': subscales.get('Conduct', {}).get('total', 0),
                'hyperactivity': subscales.get('Hyperactivity/Inattention', {}).get('total', 0),
                'peer_problems': subscales.get('Peer Problems', {}).get('total', 0),
                'prosocial': subscales.get('Prosocial', {}).get('total', 0)
            }
            
            # Store subscale details for reference
            result['derived']['subscales'] = subscales
            
            # Interpret all scores using version-specific cut-offs
            result['derived']['interpretations'] = {
                'version': sdq_version,
                'total_difficulties': interpret_sdq_score(total_difficulties, 'total_difficulties', sdq_cutoffs),
                'emotional': interpret_sdq_score(result['derived']['raw_scores']['emotional'], 'emotional', sdq_cutoffs),
                'conduct': interpret_sdq_score(result['derived']['raw_scores']['conduct'], 'conduct', sdq_cutoffs),
                'hyperactivity': interpret_sdq_score(result['derived']['raw_scores']['hyperactivity'], 'hyperactivity', sdq_cutoffs),
                'peer_problems': interpret_sdq_score(result['derived']['raw_scores']['peer_problems'], 'peer_problems', sdq_cutoffs),
                'prosocial': interpret_sdq_score(result['derived']['raw_scores']['prosocial'], 'prosocial', sdq_cutoffs)
            }
            
            # Set overall severity based on total difficulties
            total_diff_interpretation = result['derived']['interpretations']['total_difficulties']
            result['severity'] = total_diff_interpretation['band']
            
            # Add scale information with version-specific cut-offs
            if sdq_version == 'self_completed':
                result['derived']['scale'] = 'SDQ Total Difficulties - Self-Completed (0-15 normal, 16-19 borderline, 20-40 abnormal)'
            else:
                result['derived']['scale'] = 'SDQ Total Difficulties - Parent/Teacher (0-13 normal, 14-16 borderline, 17-40 abnormal)'
            
            # Add clinical flags for abnormal subscales
            for subscale_name, interpretation in result['derived']['interpretations'].items():
                if subscale_name != 'version' and interpretation.get('band') == 'abnormal':
                    result['clinical_flags'].append(
                        f"SDQ {subscale_name.replace('_', ' ').title()}: {interpretation['score']} - {interpretation['interpretation']}"
                    )
        
        # PSC-17
        elif any(x in name for x in ['psc-17', 'psc17', 'psc 17']):
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
        
        # All other questionnaires - use generic cut-off approach
        else:
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
        
        results.append({'json': result})
    
    return results

# =============================================================================
# n8n CODE NODE EXECUTION (Direct execution - no function wrappers)
# =============================================================================
# Note: In n8n, 'items' is a global variable provided by the platform
# The following code is designed to run directly in an n8n Code node

# Check if running in n8n environment
if 'items' in globals():
    try:
        # Debug: Log what we received from previous node
        print(f"🔍 n8n DEBUG: Received {len(items)} items from previous node")
        
        if items:
            sample_item = items[0].get('json', {})
            print(f"🔍 n8n DEBUG: Sample item keys: {list(sample_item.keys())}")
            print(f"🔍 n8n DEBUG: Sample questionnaire: {sample_item.get('questionnaire', 'N/A')}")
        
        # Process the questionnaire data
        processed_items = preprocess_questionnaire_data(items)
        
        # Debug: Log results
        print(f"✅ n8n SUCCESS: Generated {len(processed_items)} processed questionnaire groups")
        
        # Log summary of each processed group
        for item in processed_items:
            data = item['json']
            flags_summary = f" | Flags: {len(data.get('clinical_flags', []))}" if data.get('clinical_flags') else ""
            print(f"   → {data['questionnaire']} T{data['timepoint']}: score={data['raw_total']}, severity={data['severity']}{flags_summary}")
        
        # Return the processed items - n8n expects this format
        return processed_items

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
                'help': 'Check that this Code node is connected after a Spreadsheet File node with the first sheet data'
            }
        }
        
        print(f"❌ n8n ERROR: {str(e)}")
        print(f"🔍 n8n DEBUG: Error details logged in output")
        
        # Return error as JSON for next node
        return [{'json': error_details}]

