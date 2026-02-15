from openai import OpenAI
import os
from dotenv import load_dotenv
import base64

load_dotenv()

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def moderate_content(text_fields=None, image_path=None):
    """
    Moderate text and/or image content using OpenAI Moderation API
    
    Args:
        text_fields: dict of field_name: field_value pairs (e.g., {'content': 'post text', 'title': 'forum name'})
        image_path: path to image file on server (optional)
    
    Returns:
        dict: {
            'flagged': bool,
            'categories': dict of flagged categories,
            'message': str (error message if flagged)
        }
    """

    try:
        # Combine text fields with labels
        combined_text = ""
        if text_fields:
            for field_name, field_value in text_fields.items():
                if field_value and field_value.strip():
                    combined_text += f"=== {field_name.upper()} ===\n{field_value}\n\n"
        
        # Prepare moderation input
        moderation_input = []
        
        # Add text if present
        if combined_text.strip():
            moderation_input.append({
                "type": "text",
                "text": combined_text.strip()
            })
        
        # Add image if present
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as img_file:
                img_data = base64.b64encode(img_file.read()).decode('utf-8')
                # Determine image format
                ext = os.path.splitext(image_path)[1].lower()
                mime_type = {
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.webp': 'image/webp'
                }.get(ext, 'image/jpeg')
                
                moderation_input.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{img_data}"
                    }
                })
        
        if not moderation_input:
            return {'flagged': False, 'categories': {}, 'message': ''}
        
        # Call moderation API
        response = client.moderations.create(
            model="omni-moderation-latest",
            input=moderation_input
        )
        
        result = response.results[0]
        
        if result.flagged:
            # Get flagged categories
            flagged_categories = [cat for cat, flagged in result.categories.model_dump().items() if flagged]
            return {
                'flagged': True,
                'categories': result.categories.model_dump(),
                'message': f"Content violates community guidelines: {', '.join(flagged_categories)}"
            }
        
        return {'flagged': False, 'categories': {}, 'message': ''}
        
    except Exception as e:
        print(f"Moderation API error: {str(e)}")
        # Fail open - allow content if moderation fails
        return {'flagged': False, 'categories': {}, 'message': ''}