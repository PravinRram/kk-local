
import os
import sys

# Add current directory to path so imports work
sys.path.append(os.getcwd())

# Ensure no API key is set for this test
if 'OPENAI_API_KEY' in os.environ:
    del os.environ['OPENAI_API_KEY']

try:
    from moderation import moderate_content
    print("Successfully imported moderation module.")
    
    result = moderate_content(text_fields={'content': 'Test content'})
    print(f"Moderation result: {result}")
    
    if result['flagged'] is False:
        print("SUCCESS: Moderation bypassed as expected.")
    else:
        print("FAILURE: Moderation returned flagged=True unexpectedly.")
        
except Exception as e:
    print(f"FAILURE: An error occurred: {e}")
