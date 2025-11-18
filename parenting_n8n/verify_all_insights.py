# Verify ALL Insights at Once - Batch Processing
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

# REAL dimensions from actual all_data.json
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

# Process ALL items at once
all_insights = []
verification_summary = {
    'total_insights': len(items),
    'real_dimensions': [],
    'fabricated_dimensions': [],
    'verification_details': []
}

for item in items:
    insight = convert_jsproxy(item.json)
    dimension = insight.get('dimension', 'Unknown')
    is_real = dimension in real_dimensions
    
    # Analyze each insight
    verification_detail = {
        'dimension': dimension,
        'type': insight.get('type', 'unknown'),
        'is_real': is_real,
        'status': ' REAL' if is_real else ' FABRICATED',
        'predicted_confidence': 5 if is_real else 1,
        'evidence_preview': insight.get('evidence', '')[:50] + '...' if len(insight.get('evidence', '')) > 50 else insight.get('evidence', '')
    }
    
    verification_summary['verification_details'].append(verification_detail)
    
    if is_real:
        verification_summary['real_dimensions'].append(dimension)
    else:
        verification_summary['fabricated_dimensions'].append(dimension)
    
    # Keep original insight for passing through
    all_insights.append(insight)

# Calculate summary stats
verification_summary['real_count'] = len(verification_summary['real_dimensions'])
verification_summary['fabricated_count'] = len(verification_summary['fabricated_dimensions'])
verification_summary['accuracy_percentage'] = (verification_summary['real_count'] / verification_summary['total_insights'] * 100) if verification_summary['total_insights'] > 0 else 0

# Overall assessment
if verification_summary['fabricated_count'] == 0:
    verification_summary['overall_status'] = ' ALL DIMENSIONS ARE REAL'
    verification_summary['recommendation'] = 'All insights ready for high-quality vetting'
elif verification_summary['real_count'] == 0:
    verification_summary['overall_status'] = ' ALL DIMENSIONS ARE FABRICATED'
    verification_summary['recommendation'] = 'URGENT: Fix Gemini analysis - all dimensions are fabricated'
else:
    verification_summary['overall_status'] = f' MIXED: {verification_summary["real_count"]} real, {verification_summary["fabricated_count"]} fabricated'
    verification_summary['recommendation'] = 'Some real dimensions found, but still need to fix Gemini analysis'

# Return summary first, then each insight separately for OpenAI vetting
# The summary is for monitoring, the individual insights go to OpenAI
result = []

# Add summary as first item (for monitoring/debugging)
result.append({'json': verification_summary})

# Add each individual insight for OpenAI vetting
for insight in all_insights:
    result.append({'json': insight})

return result
