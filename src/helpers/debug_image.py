import base64
import os
from io import BytesIO
import logging
import traceback

logger = logging.getLogger(__name__)

def save_debug_image(image_data, request_id):
    """
    Save a copy of the image data for debugging purposes
    
    Args:
        image_data: Base64 encoded image or PIL Image
        request_id: Unique ID for this request to identify the debug file
    """
    try:
        debug_dir = "/tmp/devdistruct_debug"
        os.makedirs(debug_dir, exist_ok=True)
        
        # Handle different input types
        if isinstance(image_data, str):
            # It's a base64 string or URL
            if image_data.startswith('data:image'):
                # It's a data URL
                try:
                    # Extract the base64 data and image type
                    parts = image_data.split(',', 1)
                    mime_type = parts[0].split(':')[1].split(';')[0]
                    extension = mime_type.split('/')[-1]
                    
                    # Extract and decode the base64 data
                    base64_data = parts[1]
                    with open(f"{debug_dir}/image_{request_id}.{extension}", "wb") as f:
                        f.write(base64.b64decode(base64_data))
                    
                    logger.info(f"Saved debug image: {debug_dir}/image_{request_id}.{extension}")
                    return True
                except Exception as e:
                    logger.error(f"Error saving data URL image: {e}")
                    traceback.print_exc()
            
            elif image_data.startswith(('http://', 'https://')):
                # It's a URL - don't try to save it, just log it
                logger.info(f"Image URL (not saved): {image_data}")
                return True
            
            else:
                # Assume it's a raw base64 string
                try:
                    with open(f"{debug_dir}/image_{request_id}.jpg", "wb") as f:
                        # Ensure correct padding
                        padding_needed = len(image_data) % 4
                        if padding_needed:
                            image_data += '=' * (4 - padding_needed)
                        
                        f.write(base64.b64decode(image_data))
                    
                    logger.info(f"Saved debug image: {debug_dir}/image_{request_id}.jpg")
                    return True
                except Exception as e:
                    logger.error(f"Error saving base64 image: {e}")
                    traceback.print_exc()
        
        elif hasattr(image_data, 'save'):
            # It's likely a PIL Image object
            try:
                image_data.save(f"{debug_dir}/image_{request_id}.png")
                logger.info(f"Saved PIL Image: {debug_dir}/image_{request_id}.png")
                return True
            except Exception as e:
                logger.error(f"Error saving PIL Image: {e}")
                traceback.print_exc()
        
        else:
            logger.warning(f"Unsupported image data type: {type(image_data)}")
        
        return False
    except Exception as e:
        logger.error(f"Error in save_debug_image: {e}")
        traceback.print_exc()
        return False
