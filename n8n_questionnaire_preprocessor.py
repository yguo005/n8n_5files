# n8n Questionnaire Preprocessor (Python)
# Converts raw questionnaire data into structured, interpreted results for LLM processing

import json
import re
from datetime import datetime, timedelta
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
    
    # Start preprocessing (quiet mode for n8n Code node)
    
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
        
        # Try both 'timepoint' (singular) and 'timepoints' (plural) for flexibility
        timepoint_value = json_data.get('timepoint', json_data.get('timepoints', 0))
        date_str = to_iso_date(json_data.get('date'))
        dim_str = str(json_data.get('dimension', '')).strip()

        # Note: We no longer skip rows that are missing timepoint/date/dimension; they will be included as-is
            
        row = {
            'questionnaire': questionnaire,
            'timepoint': safe_round(timepoint_value),
            'date': date_str,
            'question': str(json_data.get('question', '')).strip(),
            'answer_int': safe_number(json_data.get('answer', 0)),
            'answer_raw': safe_number(json_data.get('answer', 0)),
            'dimension': dim_str,
            'free_text': str(json_data.get('free_text', '')).strip() if json_data.get('free_text') and not (isinstance(json_data.get('free_text'), float) and math.isnan(json_data.get('free_text'))) else '',
            'response_options': str(json_data.get('response_options', '')).strip()
        }
        rows.append(row)
    
    # Questionnaire counts collected (not printed in n8n)
    
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
    
    # Groups created (quiet)
    
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
            # T-score conversion tables
            PROMIS_DEPRESSION_PEDIATRIC = {
                8: 39.9, 9: 46.9, 10: 49.3, 11: 51.0, 12: 52.4, 13: 53.6, 14: 54.6, 15: 55.6,
                16: 56.5, 17: 57.4, 18: 58.3, 19: 59.1, 20: 60.0, 21: 60.8, 22: 61.7, 23: 62.5,
                24: 63.3, 25: 64.1, 26: 64.9, 27: 65.7, 28: 66.5, 29: 67.3, 30: 68.0, 31: 68.8,
                32: 69.6, 33: 70.4, 34: 71.2, 35: 72.1, 36: 73.1, 37: 74.2, 38: 75.5, 39: 77.2, 40: 80.3
            }
            
            PROMIS_ANXIETY_PEDIATRIC = {
                8: 39.0, 9: 45.4, 10: 47.8, 11: 49.6, 12: 51.0, 13: 52.2, 14: 53.3, 15: 54.4,
                16: 55.3, 17: 56.3, 18: 57.2, 19: 58.1, 20: 59.0, 21: 59.9, 22: 60.8, 23: 61.7,
                24: 62.6, 25: 63.4, 26: 64.3, 27: 65.1, 28: 65.9, 29: 66.8, 30: 67.6, 31: 68.4,
                32: 69.2, 33: 70.0, 34: 70.9, 35: 71.8, 36: 72.8, 37: 73.9, 38: 75.2, 39: 76.7, 40: 79.8
            }
            
            PROMIS_LIFE_SATISFACTION_PEDIATRIC = {
                8: 20.5, 9: 23.6, 10: 25.3, 11: 26.7, 12: 27.9, 13: 28.9, 14: 29.9, 15: 30.7,
                16: 31.6, 17: 32.5, 18: 33.3, 19: 34.1, 20: 34.9, 21: 35.8, 22: 36.6, 23: 37.4,
                24: 38.3, 25: 39.1, 26: 40.0, 27: 40.9, 28: 41.9, 29: 42.9, 30: 43.9, 31: 44.9,
                32: 45.9, 33: 46.9, 34: 48.1, 35: 49.2, 36: 50.5, 37: 52.0, 38: 53.9, 39: 56.7, 40: 62.5
            }
            
            PROMIS_DEPRESSION_PARENT = {
                6: 40.8, 7: 48.2, 8: 51.1, 9: 53.2, 10: 54.9, 11: 56.4, 12: 57.9, 13: 59.2,
                14: 60.6, 15: 61.9, 16: 63.2, 17: 64.6, 18: 65.9, 19: 67.1, 20: 68.3, 21: 69.6,
                22: 70.7, 23: 71.9, 24: 73.0, 25: 74.2, 26: 75.4, 27: 76.7, 28: 78.2, 29: 79.8, 30: 82.7
            }
            
            PROMIS_ANXIETY_PARENT = {
                8: 38.8, 9: 45.2, 10: 48.0, 11: 49.9, 12: 51.5, 13: 52.8, 14: 54.0, 15: 55.2,
                16: 56.3, 17: 57.3, 18: 58.4, 19: 59.4, 20: 60.4, 21: 61.4, 22: 62.5, 23: 63.4,
                24: 64.4, 25: 65.3, 26: 66.3, 27: 67.2, 28: 68.1, 29: 69.0, 30: 69.9, 31: 70.8,
                32: 71.7, 33: 72.6, 34: 73.5, 35: 74.5, 36: 75.6, 37: 76.8, 38: 78.2, 39: 80.0, 40: 82.7
            }
            
            PROMIS_LIFE_SATISFACTION_PARENT = {
                8: 18.5, 9: 21.4, 10: 22.9, 11: 24.1, 12: 25.2, 13: 26.1, 14: 27.0, 15: 27.8,
                16: 28.6, 17: 29.4, 18: 30.2, 19: 31.0, 20: 31.8, 21: 32.7, 22: 33.5, 23: 34.4,
                24: 35.3, 25: 36.2, 26: 37.2, 27: 38.2, 28: 39.2, 29: 40.3, 30: 41.5, 31: 42.7,
                32: 43.9, 33: 45.1, 34: 46.4, 35: 47.7, 36: 49.1, 37: 50.6, 38: 52.5, 39: 55.2, 40: 61.5
            }
            
            def get_promis_t_score(raw_total, conversion_table):
                """Convert raw PROMIS score to T-score using lookup table"""
                return conversion_table.get(raw_total, None)
            
            def interpret_promis_t_score(t_score, measure_type):
                """Interpret PROMIS T-score based on measure type"""
                if measure_type in ['depression', 'anxiety']:
                    # Higher scores = worse (negative measures)
                    if t_score <= 50:
                        return {
                            'severity': 'within normal limits',
                            'interpretation': 'Within Normal Limits'
                        }
                    elif t_score <= 55:
                        return {
                            'severity': 'mild',
                            'interpretation': 'Mild'
                        }
                    elif t_score <= 65:
                        return {
                            'severity': 'moderate',
                            'interpretation': 'Moderate'
                        }
                    else:
                        return {
                            'severity': 'severe',
                            'interpretation': 'Severe'
                        }
                else:  # life satisfaction
                    # Higher scores = better (positive measure)
                    if t_score >= 70:
                        return {
                            'severity': 'very high',
                            'interpretation': 'Very High'
                        }
                    elif t_score >= 60:
                        return {
                            'severity': 'high',
                            'interpretation': 'High'
                        }
                    elif t_score >= 40:
                        return {
                            'severity': 'average',
                            'interpretation': 'Average'
                        }
                    elif t_score >= 30:
                        return {
                            'severity': 'low',
                            'interpretation': 'Low'
                        }
                    else:
                        return {
                            'severity': 'very low',
                            'interpretation': 'Very Low'
                        }
            
            # Determine measure type and version
            is_parent = 'parent' in name.lower()
            measure_type = None
            conversion_table = None
            
            if 'depression' in name:
                measure_type = 'depression'
                conversion_table = PROMIS_DEPRESSION_PARENT if is_parent else PROMIS_DEPRESSION_PEDIATRIC
                result['derived']['scale'] = f'PROMIS Depression {"Parent Proxy" if is_parent else "Pediatric"} T-score (mean 50, SD 10, higher worse)'
                result['derived']['note'] = 'Higher T-scores indicate more depression symptoms'
            elif 'anxiety' in name:
                measure_type = 'anxiety'
                conversion_table = PROMIS_ANXIETY_PARENT if is_parent else PROMIS_ANXIETY_PEDIATRIC
                result['derived']['scale'] = f'PROMIS Anxiety {"Parent Proxy" if is_parent else "Pediatric"} T-score (mean 50, SD 10, higher worse)'
                result['derived']['note'] = 'Higher T-scores indicate more anxiety symptoms'
            elif 'life' in name or 'satisfaction' in name:
                measure_type = 'life_satisfaction'
                conversion_table = PROMIS_LIFE_SATISFACTION_PARENT if is_parent else PROMIS_LIFE_SATISFACTION_PEDIATRIC
                result['derived']['scale'] = f'PROMIS Life Satisfaction {"Parent Proxy" if is_parent else "Pediatric"} T-score (mean 50, SD 10, higher better)'
                result['derived']['note'] = 'Higher T-scores indicate better life satisfaction'
            else:
                result['derived']['scale'] = 'PROMIS Pediatric T-score (mean 50, SD 10)'
                result['derived']['note'] = 'Unknown PROMIS measure - cannot convert to T-score'
            
            # Store raw scores
            result['derived']['raw_score'] = int(total)
            result['derived']['total_score'] = int(total)
            
            # Convert to T-score if table available
            if conversion_table and measure_type:
                t_score = get_promis_t_score(int(total), conversion_table)
                
                if t_score is not None:
                    result['derived']['t_score'] = round(t_score, 1)
                    
                    # Get interpretation
                    interpretation = interpret_promis_t_score(t_score, measure_type)
                    result['severity'] = interpretation['severity']
                    result['derived']['severity_level'] = result['severity']
                    result['derived']['interpretation'] = interpretation['interpretation']
                    
                    # Add clinical flags based on T-score thresholds
                    if measure_type in ['depression', 'anxiety']:
                        if t_score > 65:
                            result['clinical_flags'].append(f'PROMIS {measure_type.title()} T-score {t_score:.1f} (Severe - significant clinical concern)')
                        elif t_score > 55:
                            result['clinical_flags'].append(f'PROMIS {measure_type.title()} T-score {t_score:.1f} (Moderate - clinical attention warranted)')
                        elif t_score > 50:
                            result['clinical_flags'].append(f'PROMIS {measure_type.title()} T-score {t_score:.1f} (Mild - monitor)')
                    else:  # life satisfaction
                        if t_score < 30:
                            result['clinical_flags'].append(f'PROMIS Life Satisfaction T-score {t_score:.1f} (Very Low - significant concern)')
                        elif t_score < 40:
                            result['clinical_flags'].append(f'PROMIS Life Satisfaction T-score {t_score:.1f} (Low - below average)')
                    
                    result['clinical_flags'].append(f'PROMIS {measure_type.replace("_", " ").title()}: Raw={int(total)}, T-score={t_score:.1f} ({interpretation["interpretation"]})')
                
                else:
                    # Raw score outside conversion table range
                    result['severity'] = 'raw score outside conversion range'
                    result['derived']['severity_level'] = result['severity']
                    result['clinical_flags'].append(f'PROMIS raw total {int(total)} outside conversion table range (8-40)')
            
            else:
                # No conversion table available
                result['severity'] = 'unknown PROMIS measure'
                result['derived']['severity_level'] = result['severity']
                result['clinical_flags'].append(f'PROMIS raw total: {int(total)}. Unable to convert - unknown measure type.')
        
        # PedsQL - Calculate both Total Score and Psychosocial Score for ratio-based interpretation
        elif 'pedsql' in name:
            result['derived']['scale'] = 'PedsQL Psychosocial/Total Score (0-100, higher better)'
            result['derived']['note'] = 'Scores reverse-transformed: 0→100, 1→75, 2→50, 3→25, 4→0. Interpretation based on Psychosocial/Total Score ratio'
            
            # Transform raw scores (0-4) to PedsQL scale (0-100)
            def transform_pedsql_score(raw_score):
                """Transform raw PedsQL score (0-4) to 0-100 scale"""
                transformation_map = {0: 100, 1: 75, 2: 50, 3: 25, 4: 0}
                return transformation_map.get(int(raw_score), None)
            
            # Extract question number from question text
            def get_question_number(question_text):
                """Extract question number from question text (e.g., '1. Question text' -> 1)"""
                match = re.match(r'^(\d+)', str(question_text).strip())
                if match:
                    return int(match.group(1))
                return None
            
            # Group responses by ALL dimensions (Physical + Psychosocial)
            all_dimensions = {
                'Physical': [],
                'Emotional': [],
                'Social': [],
                'School': []
            }
            
            # Categorize responses by question number
            # Questions 1-8: Physical, 9-13: Emotional, 14-18: Social, 19-23: School
            for response in group['responses']:
                raw_score = response.get('answer', 0)
                question_text = response.get('question', '')
                transformed_score = transform_pedsql_score(raw_score)
                
                if transformed_score is not None:  # Valid score (0-4 range)
                    question_num = get_question_number(question_text)
                    
                    if question_num is not None:
                        if 1 <= question_num <= 8:
                            all_dimensions['Physical'].append(transformed_score)
                        elif 9 <= question_num <= 13:
                            all_dimensions['Emotional'].append(transformed_score)
                        elif 14 <= question_num <= 18:
                            all_dimensions['Social'].append(transformed_score)
                        elif 19 <= question_num <= 23:
                            all_dimensions['School'].append(transformed_score)
            
            # Define expected items per dimension
            PEDSQL_DIMENSION_ITEMS = {
                'Physical': 8,      # Physical Functioning (8 items)
                'Emotional': 5,     # Emotional Functioning (5 items) 
                'Social': 5,        # Social Functioning (5 items)
                'School': 5         # School Functioning (5 items)
            }
            
            # Calculate dimension scores
            dimension_scores = {}
            all_total_scores = []
            all_psychosocial_scores = []
            
            for dimension_name, scores in all_dimensions.items():
                expected_items = PEDSQL_DIMENSION_ITEMS.get(dimension_name, len(scores))
                answered_items = len(scores)
                
                if answered_items >= (expected_items * 0.5):  # At least 50% answered
                    dimension_mean = sum(scores) / len(scores)
                    dimension_scores[dimension_name] = {
                        'score': round(dimension_mean, 2),
                        'items_answered': answered_items,
                        'items_expected': expected_items,
                        'completion_rate': round((answered_items / expected_items) * 100, 1)
                    }
                    # Add all individual scores to total pool
                    all_total_scores.extend(scores)
                    
                    # Add psychosocial scores (exclude Physical)
                    if dimension_name in ['Emotional', 'Social', 'School']:
                        all_psychosocial_scores.extend(scores)
                else:
                    # Don't calculate score - insufficient data
                    dimension_scores[dimension_name] = {
                        'score': None,
                        'items_answered': answered_items,
                        'items_expected': expected_items,
                        'completion_rate': round((answered_items / expected_items) * 100, 1),
                        'reason': 'Insufficient data (>50% missing)'
                    }
            
            # Store detailed results
            result['derived']['dimension_scores'] = dimension_scores
            result['derived']['raw_total'] = int(total)  # Keep original sum for reference
            
            # Calculate Total Score and Psychosocial Score
            if all_total_scores and all_psychosocial_scores:
                total_score = sum(all_total_scores) / len(all_total_scores)
                psychosocial_score = sum(all_psychosocial_scores) / len(all_psychosocial_scores)
                
                # Calculate Psychosocial/Total Score ratio (psychosocial score divided by total score as percentage)
                psychosocial_total_ratio = (psychosocial_score / total_score) * 100 if total_score > 0 else 0
                
                result['derived']['total_score'] = round(total_score, 2)
                result['derived']['psychosocial_score'] = round(psychosocial_score, 2)
                result['derived']['psychosocial_total_ratio'] = round(psychosocial_total_ratio, 2)
                
                # PedsQL interpretation function based on reference table
                def get_pedsql_interpretation(score):
                    """Get PedsQL interpretation based on reference table for Psychosocial/Total Score"""
                    if score >= 80:
                        return {
                            'severity': 'typical range',
                            'interpretation': 'Typical range',
                            'mental_health_status': 'Normal wellbeing'
                        }
                    elif score >= 70:
                        return {
                            'severity': 'slightly below norms',
                            'interpretation': 'Slightly below norms', 
                            'mental_health_status': 'Mild emotional or adjustment difficulties'
                        }
                    elif score >= 60:
                        return {
                            'severity': 'noticeably below average',
                            'interpretation': 'Noticeably below average',
                            'mental_health_status': 'Possible clinical concern — monitor or screen further'
                        }
                    else:  # < 60
                        return {
                            'severity': 'significantly impaired',
                            'interpretation': 'Significantly impaired',
                            'mental_health_status': 'Likely emotional/mental-health problems'
                        }
                
                # Apply interpretation to Psychosocial/Total Score ratio
                ratio_interpretation = get_pedsql_interpretation(psychosocial_total_ratio)
                result['severity'] = ratio_interpretation['severity']
                result['derived']['severity_level'] = result['severity']
                result['derived']['interpretation'] = ratio_interpretation['interpretation']
                result['derived']['mental_health_status'] = ratio_interpretation['mental_health_status']
                
                # Add clinical flags based on Psychosocial/Total Score ratio interpretation
                if psychosocial_total_ratio < 60:
                    result['clinical_flags'].append(f'PedsQL Psychosocial/Total Score {psychosocial_total_ratio:.1f} < 60 (significantly impaired - likely emotional/mental-health problems)')
                elif psychosocial_total_ratio < 70:
                    result['clinical_flags'].append(f'PedsQL Psychosocial/Total Score {psychosocial_total_ratio:.1f} (60-69: noticeably below average - possible clinical concern)')
                elif psychosocial_total_ratio < 80:
                    result['clinical_flags'].append(f'PedsQL Psychosocial/Total Score {psychosocial_total_ratio:.1f} (70-79: slightly below norms - mild emotional/adjustment difficulties)')
                
                # Add component scores for reference
                result['clinical_flags'].append(f'PedsQL Total Score: {total_score:.1f}, Psychosocial Score: {psychosocial_score:.1f}, Ratio: {psychosocial_total_ratio:.1f}%')
                
                # Add flags for dimensions with insufficient data
                for dimension_name, dimension_data in dimension_scores.items():
                    dimension_score = dimension_data.get('score')
                    if dimension_score is None:
                        # Flag dimensions with insufficient data
                        completion_rate = dimension_data.get('completion_rate', 0)
                        result['clinical_flags'].append(f'PedsQL {dimension_name}: Insufficient data ({completion_rate}% complete, need ≥50%)')
            
            else:
                result['severity'] = 'insufficient valid responses'
                result['derived']['severity_level'] = result['severity']
                result['clinical_flags'].append('PedsQL: No valid responses in 0-4 range for transformation')
        
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
        elif any(x in name for x in ['psc-17', 'psc17', 'psc 17', 'Pediatric Symptom Checklist – 17 (PSC-17)', 'psc']):
            # PSC-17 processing (quiet)
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
            # Generic processing (quiet)
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
        processed_items = preprocess_questionnaire_data(items)
        return processed_items
    except Exception as e:
        import traceback
        error_details = {
            'error_message': str(e),
            'error_type': type(e).__name__,
            'input_items_count': len(items) if 'items' in globals() else 0,
            'traceback': traceback.format_exc(),
            'debug_info': {
                'items_available': 'items' in globals(),
                'items_type': type(items).__name__ if 'items' in globals() else 'undefined',
                'help': 'Ensure this node receives a list of items with a json payload per row.'
            }
        }
        return [{'json': error_details}]

