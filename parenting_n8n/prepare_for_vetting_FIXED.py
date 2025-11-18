"""
FIXED VERSION: Prepare for Vetting - n8n Code Node
Extracts insights from Gemini AI output and prepares them for individual scoring.
"""

import json

try:
    # Get the AI analysis from the Gemini node
    # Gemini output structure: items[0].json.content.parts[0].text
    raw_json_string = items[0].json.get("content", {}).get("parts", [{}])[0].get("text", "{}")
    
    # Parse the JSON string from Gemini (handle markdown code blocks)
    if '```json' in raw_json_string and '```' in raw_json_string:
        start_idx = raw_json_string.find('```json') + 7
        end_idx = raw_json_string.rfind('```')
        clean_json = raw_json_string[start_idx:end_idx].strip()
    else:
        clean_json = raw_json_string
    
    try:
        analysis_data = json.loads(clean_json)
    except json.JSONDecodeError as e:
        return [{'json': {
            'error': f'Failed to parse Gemini JSON output: {str(e)}',
            'raw_output': raw_json_string[:500] + "..." if len(raw_json_string) > 500 else raw_json_string,
            'clean_json': clean_json[:500] + "..." if len(clean_json) > 500 else clean_json
        }}]

    # Extract insights for individual vetting
    insights_to_vet = []
    
    # Process key strengths
    for strength in analysis_data.get("key_strengths", []):
        insights_to_vet.append({
            "type": "strength",
            "dimension": strength.get("dimension", "Unknown"),
            "evidence": strength.get("evidence", ""),
            "insight": strength.get("insight", "")
        })

    # Process areas for growth
    for growth_area in analysis_data.get("areas_for_growth", []):
        insights_to_vet.append({
            "type": "growth_area", 
            "dimension": growth_area.get("dimension", "Unknown"),
            "evidence": growth_area.get("evidence", ""),
            "insight": growth_area.get("insight", "")
        })
    
    if not insights_to_vet:
        return [{'json': {
            'error': 'No insights found in Gemini output',
            'analysis_data_keys': list(analysis_data.keys()) if isinstance(analysis_data, dict) else 'not_dict'
        }}]

    print(f"Prepared {len(insights_to_vet)} insights for vetting.")
    
    # CRITICAL FIX: Return each insight as a separate item for individual processing
    # This creates multiple outputs that can be processed individually by OpenAI
    result = []
    for insight in insights_to_vet:
        result.append({'json': insight})
    
    return result

except Exception as e:
    return [{'json': {
        'error': f'Prepare for vetting failed: {str(e)}',
        'input_structure': str(items[0].json.keys()) if items and hasattr(items[0], 'json') else 'no_json'
    }}]
