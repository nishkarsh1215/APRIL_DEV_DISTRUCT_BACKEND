import re
import json

def clean_model_response(response_text):
    """
    Clean up the response from the AI model by removing markdown formatting
    artifacts like code fences (backticks) and language indicators.
    
    Args:
        response_text (str): Raw response from the AI model
        
    Returns:
        str: Cleaned response text
    """
    if not response_text:
        return ""
    
    # Pattern to match markdown code blocks like ```json {...} ``` or ```javascript {...} ```
    # This handles both with and without language specifier
    code_block_pattern = r'^```(?:[a-zA-Z]*\s*)?\n?(.*?)```$'
    
    # Try to match and extract the content between code fences
    match = re.search(code_block_pattern, response_text.strip(), re.DOTALL)
    if match:
        # We found a code block, extract just the content
        extracted_content = match.group(1).strip()
        return extracted_content
    
    # If no code block is found, return the original text
    return response_text.strip()

def is_valid_json(text):
    """
    Check if a string is valid JSON.
    
    Args:
        text (str): Text to check
        
    Returns:
        bool: True if valid JSON, False otherwise
    """
    if not text or not isinstance(text, str):
        return False
        
    try:
        json.loads(text)
        return True
    except:
        return False

def format_code_response(response):
    """
    Format the code response for storage in database and retrieval.
    Ensures we store clean, usable code without markdown artifacts.
    
    Args:
        response (str): Raw response from AI model
        
    Returns:
        str: Formatted response suitable for database storage
    """
    # First clean any markdown artifacts
    cleaned = clean_model_response(response)
    
    # Check if it's already valid JSON
    if is_valid_json(cleaned):
        return cleaned
    
    # If it's not valid JSON but looks like code, wrap it
    if "function" in cleaned or "class" in cleaned or "import " in cleaned or "<" in cleaned:
        try:
            return json.dumps({
                "/index.js": {
                    "code": cleaned
                }
            })
        except:
            pass
    
    # Return the cleaned text as-is if we can't process it further
    return cleaned
