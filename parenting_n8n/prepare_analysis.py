# Debug what the AI node should receive
input_data = items[0].json

# Extract key information
debug_info = {
    'teenager_name': input_data.get('teenager_name', 'Not found'),
    'has_trends': 'trends' in input_data,
    'trends_count': len(input_data.get('trends', {})),
    'sample_dimensions': list(input_data.get('trends', {}).keys())[:10],
    'significant_changes': []
}

# Find dimensions with significant changes
if 'trends' in input_data:
    for dim, data in input_data['trends'].items():
        parent_change = data.get('parent_trend', {}).get('change', 0)
        teen_change = data.get('teenager_trend', {}).get('change', 0)
        
        if abs(parent_change) > 0.5 or abs(teen_change) > 0.5:
            debug_info['significant_changes'].append({
                'dimension': dim,
                'parent_change': parent_change,
                'teen_change': teen_change,
                'parent_trend': data.get('parent_trend', {}).get('trend'),
                'teen_trend': data.get('teenager_trend', {}).get('trend')
            })

return [{'json': debug_info}]