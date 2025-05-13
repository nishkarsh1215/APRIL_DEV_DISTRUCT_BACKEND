import re
from urllib.parse import urlparse

def is_valid_url(url):
    """
    Check if the provided string is a valid URL.
    
    Args:
        url (str): The URL to validate
        
    Returns:
        bool: True if valid URL, False otherwise
    """
    if not isinstance(url, str):
        return False
    
    # Check if URL starts with http:// or https://
    if not url.startswith(('http://', 'https://')):
        return False
    
    # Validate URL format
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def process_base64_image(base64_string):
    """
    Process a base64 encoded image string for AI model input.
    
    Args:
        base64_string (str): Base64 encoded image
        
    Returns:
        Image object or None if processing fails
    """
    if not base64_string or not isinstance(base64_string, str):
        return None
    
    # Check if it's a data URL (e.g., data:image/jpeg;base64,...)
    if base64_string.startswith('data:image'):
        try:
            from PIL import Image
            import base64
            from io import BytesIO
            
            # Extract the base64 part
            base64_data = base64_string.split(',', 1)[1]
            image_data = base64.b64decode(base64_data)
            image = Image.open(BytesIO(image_data))
            return image
        except Exception as e:
            print(f"Error processing base64 image: {e}")
            return None
    
    return None
