# FINAL Vetting Input Verification - Uses Real Dimensions from all_data.json
import json

def convert_jsproxy(obj):
    if hasattr(obj, 'to_py'):
        return obj.to_py()
    elif str(type(obj)).find('JsProxy') != -1:
        try:
            if hasattr(obj, 'keys'):
                result = {}
                for key in obj.keys():
                    result[key] = convert_jsproxy(obj[key])
                return result
            else:
                return str(obj)
        except:
            return str(obj)
    else:
        return obj

# Get insight data
insight = convert_jsproxy(items[0].json)

# REAL dimensions from actual all_data.json (extracted from  debug outputs and All_in_One_FIXED.py)
real_dimensions = [
    'Abstract Conceptualization', 'Acceptance', 'Active Experimentation', 
    'Analysis', 'Analyticity', 'Anger Management', 'Approach-Avoidance Style',
    'Attention', 'Attitude', 'Autonomy', 'Awareness', 'BAS Drive', 'BAS Fun Seeking',
    'BIS', 'Behavior Management', 'Behavioral Manifestation', 'Care', 'Clarity',
    'Cognitive Skills', 'Compromising', 'Concrete Experience', 'Conduct Problems',
    'Conflict', 'Cooperation', 'Creativity', 'Daily Living Skills', 'Depression',
    'Dominating', 'Emotional Regulation', 'Emotional Stability', 'Emotional Symptoms',
    'Empathy', 'Evaluation', 'Executive Function', 'Expressive Suppression',
    'Family Cohesion', 'Family Dynamics', 'Family Flexibility', 'General',
    'Goal Persistence', 'Imagination', 'Inference', 'Information Processing',
    'Involvement', 'Leadership', 'Mastery-Avoidance', 'Maturity of Judgment',
    'Motivation', 'Motor Skills', 'Negative Affect', 'Obliging', 'Open-mindedness',
    'Peer Relationship Problems', 'Performance-Approach', 'Performance-Avoidance',
    'Perseverance of Effort', 'Personal Distress', 'Positive Affect',
    'Problem-Solving Confidence', 'Prosocial Behavior', 'Reflective Observation',
    'Regulation of Cognition', 'Resilience', 'Role Orientation', 'Self-Control',
    'Self-Testing', 'Social Skills', 'Socialization', 'Study Aids', 'Systematicity',
    'Test Strategies', 'Time Management', 'Truth-seeking', 'Well-being', 'Worry Management'
]

# Analyze the insight
dimension = insight.get('dimension', 'Unknown')
is_real = dimension in real_dimensions



# Determine status - if not in real dimensions, it's fabricated
if is_real:
    status = ' REAL DIMENSION'
    confidence_prediction = 5
    recommendation = 'Ready for high-quality vetting - dimension exists in your assessment data'
else:
    status = ' FABRICATED DIMENSION'  
    confidence_prediction = 1
    recommendation = f'Will receive low confidence score - dimension "{dimension}" does not exist in your 75 real dimensions from all_data.json'

# Create verification result
verification = {
    'dimension': dimension,
    'type': insight.get('type', 'unknown'),
    'is_real_dimension': is_real,
    'is_fabricated_dimension': not is_real,
    'status': status,
    'predicted_confidence': confidence_prediction,
    'recommendation': recommendation,
    'evidence_preview': insight.get('evidence', '')[:100] + '...' if len(insight.get('evidence', '')) > 100 else insight.get('evidence', ''),
    'note': f'Compared against {len(real_dimensions)} real dimensions from all_data.json'
}

# Return verification + pass through original insight
return [
    {'json': verification},
    {'json': insight}
]
