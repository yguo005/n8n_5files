"""
FIXED VERSION: Assemble Vetting Insights - n8n Code Node
Combines the scored insights back into a single report structure.
"""

import json

try:
    # Get all the scored items from the OpenAI vetting node
    scored_items = items
    print(f"Assembling {len(scored_items)} vetted insights...")

    if not scored_items:
        return [{'json': {
            'error': 'No scored items received from OpenAI vetting node'
        }}]

    vetted_strengths = []
    vetted_growth_areas = []

    # Process each scored item
    for i, scored_item in enumerate(scored_items):
        try:
            # Get the original insight data (this should be in the OpenAI input)
            original_data = scored_item.json.get('input', {})
            
            # Get the AI scoring result
            ai_response = scored_item.json.get('message', {}).get('content', '{}')
            
            # Parse the AI scoring if it's a string
            if isinstance(ai_response, str):
                try:
                    ai_score_data = json.loads(ai_response)
                except json.JSONDecodeError:
                    ai_score_data = {
                        "confidence_score": 3,
                        "reasoning": "Could not parse AI scoring response"
                    }
            else:
                ai_score_data = ai_response

            # Reconstruct the complete insight with scoring
            full_insight = {
                "dimension": original_data.get("dimension", f"Unknown_{i}"),
                "evidence": original_data.get("evidence", ""),
                "insight": original_data.get("insight", ""),
                "confidence_score": ai_score_data.get("confidence_score", 3),
                "reasoning": ai_score_data.get("reasoning", "No reasoning provided")
            }
            
            # Sort into the correct category
            insight_type = original_data.get("type", "unknown")
            if insight_type == "strength":
                vetted_strengths.append(full_insight)
            elif insight_type == "growth_area":
                vetted_growth_areas.append(full_insight)
            else:
                print(f"Warning: Unknown insight type '{insight_type}' for item {i}")

        except Exception as e:
            print(f"Warning: Could not process scored item {i}: {str(e)}")
            continue

    # Create the final report structure
    final_report_data = {
        "vetted_analysis": {
            "key_strengths": vetted_strengths,
            "areas_for_growth": vetted_growth_areas
        },
        "processing_summary": {
            "total_insights_processed": len(scored_items),
            "strengths_identified": len(vetted_strengths),
            "growth_areas_identified": len(vetted_growth_areas)
        }
    }

    print(f"Assembly complete. {len(vetted_strengths)} strengths, {len(vetted_growth_areas)} growth areas.")
    
    # Return in proper n8n format
    return [{'json': final_report_data}]

except Exception as e:
    return [{'json': {
        'error': f'Assembly failed: {str(e)}',
        'items_received': len(items) if items else 0,
        'debug_info': str(items[0].json.keys()) if items and hasattr(items[0], 'json') else 'no_items'
    }}]
