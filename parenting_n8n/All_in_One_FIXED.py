"""
FIXED VERSION: All-in-One Data Processing for n8n Code Node
Handles JsProxy objects from n8n's Python environment correctly.
"""

import json

# --- Step 1: Handle JsProxy Objects ---
print("=== DEBUGGING INPUT DATA ===")
print(f"Items received: {len(items) if items else 0}")

if not items:
    return [{'json': {'error': 'No input items received'}}]

def js_proxy_to_python(obj):
    """Convert JsProxy objects to Python objects recursively"""
    if hasattr(obj, 'to_py'):
        # This is a JsProxy object
        return obj.to_py()
    elif hasattr(obj, 'valueOf'):
        # Alternative JsProxy conversion
        return obj.valueOf()
    elif str(type(obj)).find('JsProxy') != -1:
        # Try to convert JsProxy manually
        try:
            # Try to convert to dict if it has keys
            if hasattr(obj, 'keys'):
                result = {}
                for key in obj.keys():
                    result[key] = js_proxy_to_python(obj[key])
                return result
            # Try to convert to list if it has length
            elif hasattr(obj, 'length'):
                result = []
                for i in range(obj.length):
                    result.append(js_proxy_to_python(obj[i]))
                return result
            else:
                return str(obj)
        except:
            return str(obj)
    else:
        return obj

try:
    # Get the raw input and convert JsProxy to Python
    raw_input = items[0].json
    print(f"Raw input type: {type(raw_input)}")
    
    # Convert JsProxy to Python object
    input_data = js_proxy_to_python(raw_input)
    print(f"Converted input type: {type(input_data)}")
    print(f"Input keys: {list(input_data.keys()) if isinstance(input_data, dict) else 'Not a dict'}")
    
    # Extract assessment data
    all_assessments = None
    
    # Case 1: Direct array of assessments
    if isinstance(input_data, list) and input_data and isinstance(input_data[0], dict) and 'assessment_session' in input_data[0]:
        all_assessments = input_data
        print("✅ Found direct assessment array")
    
    # Case 2: Data wrapped in 'data' key (most common)
    elif isinstance(input_data, dict) and 'data' in input_data:
        potential_data = input_data['data']
        # Convert potential_data if it's still a JsProxy
        if str(type(potential_data)).find('JsProxy') != -1:
            potential_data = js_proxy_to_python(potential_data)
        
        if isinstance(potential_data, list) and potential_data and isinstance(potential_data[0], dict) and 'assessment_session' in potential_data[0]:
            all_assessments = potential_data
            print("✅ Found assessments in 'data' key")
    
    # Case 3: Try to find assessment data anywhere in the structure
    if all_assessments is None:
        def find_assessment_data(obj, path=""):
            if isinstance(obj, list) and obj and isinstance(obj[0], dict) and 'assessment_session' in obj[0]:
                print(f"✅ Found assessments at path: {path}")
                return obj
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    # Convert value if it's JsProxy
                    if str(type(value)).find('JsProxy') != -1:
                        value = js_proxy_to_python(value)
                    result = find_assessment_data(value, f"{path}.{key}")
                    if result:
                        return result
            return None
        
        all_assessments = find_assessment_data(input_data)
    
    if all_assessments is None:
        return [{'json': {
            'error': 'Could not find assessment data after JsProxy conversion',
            'converted_input_type': str(type(input_data)),
            'converted_keys': list(input_data.keys()) if isinstance(input_data, dict) else 'Not a dict',
            'sample_data': str(input_data)[:500] + "..." if len(str(input_data)) > 500 else str(input_data)
        }}]

except Exception as e:
    return [{'json': {
        'error': f'JsProxy conversion failed: {str(e)}',
        'raw_input_type': str(type(items[0].json)) if items and hasattr(items[0], 'json') else 'no_json'
    }}]

print(f"✅ Successfully extracted {len(all_assessments)} assessments")

# --- Step 2: Extract Free-Text Responses ---
print("Processing free-text responses...")
free_text_responses = []
for assessment in all_assessments:
    if not isinstance(assessment, dict): 
        continue
    session_date = assessment.get('assessment_session', {}).get('assessment_date')
    for perspective in ['parent', 'teenager']:
        responses_list = assessment.get('responses', {}).get(perspective, [])
        if not isinstance(responses_list, list): 
            continue
        for response in responses_list:
            if (isinstance(response, dict) and 
                response.get('response_type') == 'free_text' and 
                response.get('free_text_response')):
                free_text_responses.append({
                    'date': session_date.split('T')[0] if session_date else '',
                    'response_text': response.get('free_text_response', '').strip(),
                    'respondent': perspective
                })
print(f"Found {len(free_text_responses)} free-text responses.")

# --- Step 3: Generate Time-Series Structure ---
print("Generating time-series structure...")

# Helper function for trend calculation
def calculate_trends(timeline):
    if not timeline or len(timeline) < 2: 
        return {'trend': 'insufficient_data', 'change': 0}
    scores = [item['average_score'] for item in timeline if item.get('average_score') is not None]
    if len(scores) < 2: 
        return {'trend': 'insufficient_data', 'change': 0}
    change = scores[-1] - scores[0]
    trend = 'improving' if change > 0.5 else 'declining' if change < -0.5 else 'stable'
    return {'trend': trend, 'change': round(change, 2)}

# Sort assessments by date
assessments_by_date = sorted(all_assessments, key=lambda x: x.get('assessment_session', {}).get('assessment_date', ''))

# Collect all unique dimension names
all_dimensions = set()
for assessment in assessments_by_date:
    if 'analysis_ready_data' in assessment:
        parent_dims = assessment.get('analysis_ready_data', {}).get('dimension_scores', {}).get('parent', {})
        teenager_dims = assessment.get('analysis_ready_data', {}).get('dimension_scores', {}).get('teenager', {})
        all_dimensions.update(parent_dims.keys())
        all_dimensions.update(teenager_dims.keys())

print(f"Found {len(all_dimensions)} unique dimensions")

# Build the time-series data for each dimension
temporal_dimension_scores = {}
for dimension in sorted(list(all_dimensions)):
    parent_timeline = []
    teenager_timeline = []
    for assessment in assessments_by_date:
        # Get assessment period with fallback
        period = (
            assessment.get('metadata', {}).get('assessment_period') or
            assessment.get('participant_info', {}).get('parent', {}).get('assessment_period') or
            assessment.get('assessment_session', {}).get('assessment_date', '')[:10]
        )
        
        parent_data = assessment.get('analysis_ready_data', {}).get('dimension_scores', {}).get('parent', {}).get(dimension)
        if parent_data and parent_data.get('average_score') is not None:
            parent_timeline.append({'period': period, 'average_score': parent_data['average_score']})
        
        teenager_data = assessment.get('analysis_ready_data', {}).get('dimension_scores', {}).get('teenager', {}).get(dimension)
        if teenager_data and teenager_data.get('average_score') is not None:
            teenager_timeline.append({'period': period, 'average_score': teenager_data['average_score']})

    temporal_dimension_scores[dimension] = {
        'parent_trend': calculate_trends(parent_timeline),
        'teenager_trend': calculate_trends(teenager_timeline),
        'parent_timeline_summary': [f"{item['period']}: {item['average_score']:.2f}" for item in parent_timeline if item.get('average_score') is not None],
        'teenager_timeline_summary': [f"{item['period']}: {item['average_score']:.2f}" for item in teenager_timeline if item.get('average_score') is not None]
    }

print("Time-series structure generated.")

# --- Step 4: Prepare the Final Output for the AI ---
latest_assessment = assessments_by_date[-1] if assessments_by_date else {}
teen_name = latest_assessment.get('participant_info', {}).get('child', {}).get('name', 'The teenager')

final_output = {
    "teenager_name": teen_name,
    "trends": temporal_dimension_scores,
    "parent_qualitative": [resp['response_text'] for resp in free_text_responses if resp.get('respondent') == 'parent'],
    "teenager_qualitative": [resp['response_text'] for resp in free_text_responses if resp.get('respondent') == 'teenager'],
    "debug_info": {
        "assessments_processed": len(all_assessments),
        "dimensions_found": len(all_dimensions),
        "free_text_responses": len(free_text_responses),
        "conversion_successful": True
    }
}

print(f"Final output created: {teen_name}, {len(temporal_dimension_scores)} dimensions, {len(free_text_responses)} responses")

# Return in proper n8n format
return [{'json': final_output}]
