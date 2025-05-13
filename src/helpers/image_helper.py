import requests
from PIL import Image
from io import BytesIO
import base64
import logging

logger = logging.getLogger(__name__)

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
    
    # Basic URL validation is enough for this check
    return True

def process_image_input(image_data):
    """
    Process image input which could be a URL or base64 encoded string.
    
    Args:
        image_data (str): URL or base64 encoded image
        
    Returns:
        str or None: Valid URL if provided, or None if invalid/not processable
    """
    if not image_data or not isinstance(image_data, str):
        return None
    
    # If it's a URL, validate and return it
    if image_data.startswith(('http://', 'https://')):
        if is_valid_url(image_data):
            return image_data
        else:
            logger.warning(f"Invalid image URL format: {image_data}")
            return None
    
    # For base64 encoding (not implemented in this example)
    # You would decode the base64 string, save as temporary file, and return the file path
    
    return None

def load_image_from_url(image_url):
    """
    Load an image from a URL.
    
    Args:
        image_url (str): URL to the image
        
    Returns:
        PIL.Image or None: Loaded image or None if failed
    """
    if not is_valid_url(image_url):
        logger.warning(f"Invalid image URL: {image_url}")
        return None
        
    try:
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return image
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching image from URL {image_url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error processing image from URL {image_url}: {e}")
        return None
