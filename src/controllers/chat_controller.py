from flask_restx import Namespace as RestxNamespace, Resource, fields
from flask import request
from ultralytics import YOLO
from infra.db.models import ChatMessage, EditorMessage
from helpers.auth_helper import token_required
import cv2, re
from PIL import Image
from io import BytesIO
import base64
import os
import uuid
import requests
from infra.swagger import api
import google.generativeai as genai
from infra.db.models import Chat
import json
import numpy as np
from sklearn.cluster import KMeans
import sys
import traceback
from helpers.credit_helper import check_and_refresh_credits
from helpers.response_helper import clean_model_response, is_valid_json

API_TOKEN = os.getenv('FIGMA_API_TOKEN')

# Helper Functions

class_names = ['button', 'field', 'heading', 'iframe', 'image', 'label', 'link', 'text']

genai.configure(api_key='AIzaSyBK7zo3osQfk53Bm2xA6CO-Qt1_FfMsOmo')

def load_image_from_url(image_url):
    try:
        response = requests.get(image_url, stream=True)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        return image
    except requests.exceptions.RequestException as e:
        print(f"Error fetching image from URL: {e}")
        return None
    except Exception as e:
        print(f"Error loading image: {e}")
        return None

def decode_base64_image(base64_string):
    """
    Decode a base64 encoded image string to a PIL Image.
    
    Args:
        base64_string: Base64 encoded image string (may include data:image prefix)
        
    Returns:
        PIL.Image or None: Decoded image or None if decoding fails
    """
    try:
        # Check if the string is a base64 encoded image
        if not base64_string or not isinstance(base64_string, str):
            print("Invalid base64 string: None or not a string")
            return None
            
        # Handle data URL format (e.g., data:image/jpeg;base64,/9j/4AAQ...)
        if base64_string.startswith('data:image'):
            # Extract the base64 data part after the comma
            print("Processing data:image format")
            base64_data = base64_string.split(',', 1)[1]
            
            # Decode the base64 string
            image_data = base64.b64decode(base64_data)
            
            # Convert to PIL Image
            image = Image.open(BytesIO(image_data))
            print(f"Successfully decoded base64 image of size {image.size}")
            return image
            
        # Handle raw base64 string without data URL prefix
        elif len(base64_string) > 100:  # Simple check to avoid processing non-base64 strings
            try:
                print("Processing raw base64 string")
                # Try to decode as a raw base64 string
                # Ensure the base64 string has a valid length (multiple of 4)
                padding_needed = len(base64_string) % 4
                if padding_needed:
                    base64_string += '=' * (4 - padding_needed)
                
                image_data = base64.b64decode(base64_string)
                image = Image.open(BytesIO(image_data))
                print(f"Successfully decoded raw base64 image of size {image.size}")
                return image
            except Exception as e:
                print(f"Error decoding raw base64 string: {e}")
                return None
        else:
            print(f"Base64 string too short: {len(base64_string)} chars")       
        return None
    except Exception as e:
        print(f"Error decoding base64 image: {e}")
        traceback.print_exc()
        return None

def prepare_content(image_data, text_prompt=""):
    """
    Prepare content for the AI model with text and optional image.
    The image_data can be a URL or base64 encoded image.
    
    Args:
        image_data: String URL to an image or base64 encoded image
        text_prompt: String prompt for the AI
        
    Returns:
        list: Content list for the AI model
    """
    content = []

    # Add text prompt if provided
    if text_prompt:
        content.append(text_prompt)
        print(f"Added text prompt to content: {text_prompt[:50]}...")

    # Handle image data
    if image_data:
        # Check if it's a URL
        if isinstance(image_data, str) and image_data.startswith(('http://', 'https://')):
            image = load_image_from_url(image_data)
            if image:
                content.append(image)
                print(f"Added image from URL: {image_data}")
        # Check if it's a base64 encoded image
        elif isinstance(image_data, str) and (image_data.startswith('data:image') or len(image_data) > 100):
            image = decode_base64_image(image_data)
            if image:
                content.append(image)
                print("Added image from base64 data")
        # Handle other types or list of images
        elif isinstance(image_data, list):
            for item in image_data:
                if isinstance(item, str):
                    if item.startswith(('http://', 'https://')):
                        image = load_image_from_url(item)
                    else:
                        image = decode_base64_image(item)
                    
                    if image:
                        content.append(image)
        else:
            print(f"Unhandled image data type: {type(image_data)}")
    
    return content

model = genai.GenerativeModel('gemini-1.5-flash')

def generate_response(image_data, text_prompt=""):
    """Generate a response from the AI model using text and optional image."""
    try:
        # Prepare content
        content = prepare_content(image_data, text_prompt)

        if not content:
            print("No valid content (images or text) to send.")
            return "I couldn't process your request. Please provide valid text or image content."

        # Send to model and get response
        print(f"Sending content to model with length: {len(content)}")
        response = model.generate_content(content)
        raw_response = response.text
        
        # Clean the response to remove markdown artifacts
        cleaned_response = clean_model_response(raw_response)
        print(f"Raw response first 100 chars: {raw_response[:100]}...")
        print(f"Cleaned response first 100 chars: {cleaned_response[:100]}...")
        
        return cleaned_response
    except Exception as e:
        print(f"Error generating response: {e}")
        traceback.print_exc()
        return f"An error occurred while processing your request: {str(e)}"

def open_figma_file(file_key, api_token):
    headers = {'X-Figma-Token': api_token}
    response = requests.get(f'https://api.figma.com/v1/files/{file_key}', headers=headers)
        
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None

def process_figma_file_api(file_key, api_token):
    """Process a Figma file via API and extract design information"""
    file_data = open_figma_file(file_key, api_token)
    
    if not file_data:
        return "Failed to retrieve Figma file data"
    
    # Extract document and canvas data
    document = file_data.get('document', {})
    canvas_nodes = document.get('children', [])
    
    # Process the canvas and extract relevant elements
    result_data = []
    
    # Extract frame and component information
    for canvas in canvas_nodes:
        if canvas.get('type') == 'CANVAS':
            for node in canvas.get('children', []):
                if node.get('type') in ['FRAME', 'COMPONENT', 'INSTANCE']:
                    # Extract properties
                    element_data = {
                        "name": node.get('name', 'Unnamed'),
                        "type": node.get('type'),
                        "dimensions": {
                            "width": node.get('size', {}).get('width'),
                            "height": node.get('size', {}).get('height')
                        },
                        "position": {
                            "x": node.get('absoluteBoundingBox', {}).get('x'),
                            "y": node.get('absoluteBoundingBox', {}).get('y')
                        },
                        "background": node.get('backgroundColor', {}),
                        "children_count": len(node.get('children', []))
                    }
                    result_data.append(element_data)
    
    return result_data

def process_figma_file(figma_data):
    """Process an uploaded Figma (.fig) file and extract available metadata"""
    try:
        # For uploaded .fig files, we can extract basic metadata
        # Note: Full parsing of .fig binary format requires specialized tools
        file_size = len(figma_data)
        file_signature = figma_data[:4].hex()  # First few bytes as hex
        
        # Basic analysis of the file content
        result_data = {
            "file_type": "Figma Design File (.fig)",
            "file_size_bytes": file_size,
            "file_signature": file_signature,
            "estimated_complexity": "medium" if file_size > 500000 else "simple",
        }
        
        try:
            text_sample = figma_data.decode('utf-8', errors='ignore')
        except:
            text_sample = str(figma_data)  # Fallback if decode fails
        
        # Look for potential UI elements in the binary data
        elements = []
        ui_patterns = ['Button', 'TextField', 'Frame', 'Text', 'Image', 'Rectangle', 'Component']
        for pattern in ui_patterns:
            if pattern in text_sample:
                count = text_sample.count(pattern)
                if count > 0:
                    elements.append({"type": pattern, "count": count})
        
        result_data["detected_elements"] = elements
        
        return result_data
    except Exception as e:
        print(f"Error processing Figma file: {str(e)}")
        return {"error": str(e)}

# Define REST namespace for chat endpoints
chat_ns = RestxNamespace('chat', description='HTTP-based chat endpoints')
chat_model = api.model('ChatMessage', {
    'prompt': fields.String(required=True, description="Prompt message"),
    'image': fields.String(description="Base64 encoded image (optional)"),
    'chat_id': fields.String(required=True, description="Existing chat id"),
    'figma_link': fields.String(description="Figma file link (optional)"),
    'figma_token': fields.String(description="Figma API token (optional)")
    # Note: figma_file will be uploaded as a file, not included in the model
})

# New model for chat creation
chat_create_model = api.model('ChatCreate', {
    'title': fields.String(required=True, description="Chat title"),
    'prompt': fields.String(required=True, description="Initial chat prompt"),
    'image': fields.String(description="Base64 encoded image (optional)"),
    'figma_link': fields.String(description="Figma file link (optional)"),
    'figma_token': fields.String(description="Figma API token (optional)")
    # Note: figma_file will be uploaded as a file, not included in the model
})

chat_update_model = api.model('ChatUpdate', {
    'title': fields.String(required=True, description="Chat title")
})

feedback_model = api.model('Feedback', {
    'feedback': fields.String(required=True, description="User feedback text")
})

# Run credit refresh check at key API endpoints
@chat_ns.route('/history')
class ChatHistory(Resource):
    @token_required
    def get(self, user):
        try:
            # Check if credits need to be refreshed
            check_and_refresh_credits()
            
            # Convert Chat references to ObjectIds
            chat_ids = [chat.id for chat in user.chatIds]
            chats = Chat.objects(id__in=chat_ids).order_by('-created_at')[:10]
            
            history = []
            for chat in chats:
                # Get all messages with their original content
                messages = []
                for msg in chat.chat_messages:
                    messages.append({
                        "message_id": str(msg.id),
                        "prompt": msg.prompt,
                        "response": msg.response,  # Return exact response from database
                        "created_at": str(msg.created_at) if msg.created_at else None
                    })
                
                # Get editor messages for this chat
                editor_messages = []
                for msg in chat.editor_messages:
                    editor_messages.append({
                        "message_id": str(msg.id),
                        "prompt": msg.prompt,
                        "response": msg.response,  # Return exact response from database
                        "created_at": str(msg.created_at) if msg.created_at else None
                    })
                
                history.append({
                    "chat_id": str(chat.id),
                    "title": chat.title,
                    "messages": messages,
                    "editor_messages": editor_messages,  # Include editor messages in history
                    "created_at": str(chat.created_at) if chat.created_at else None,
                    "last_message": messages[-1] if messages else None,  # Include last message for quick preview
                })
            
            print(f"Returning history for {len(history)} chats", flush=True)
            return {"history": history}, 200
        except Exception as e:
            print(f"Error fetching chat history: {e}", flush=True)
            traceback.print_exc()
            return {"error": f"Failed to fetch chat history: {str(e)}"}, 500

@chat_ns.route('/send')
class ChatSend(Resource):
    # Remove the validation requirement which is causing the 415 error
    # @chat_ns.expect(chat_model, validate=True)
    def post(self):
        try:
            # Check if credits need to be refreshed
            check_and_refresh_credits()
            """
            Send a chat prompt to an existing chat, remembering earlier conversation.
            """
            # Debug the incoming request
            content_type = request.headers.get('Content-Type', '')
            
            # Handle different content types
            if 'multipart/form-data' in content_type:
                # This is a form submission with files
                data = request.form.to_dict()
            else:
                # Try to parse as JSON
                try:
                    data = request.get_json(force=True) or {}  # force=True tries to parse JSON 
                except Exception as e:
                    print(f"Error parsing JSON: {str(e)}", flush=True)
                    # Last resort, check if we can get form data
                    data = request.form.to_dict() or {}
        
            prompt = data.get('prompt', '')
            chat_id = data.get('chat_id')
            print(f"Prompt: {prompt}", flush=True)
            sys.stdout.flush()
            
            if not chat_id:
                return {"error": "Chat id is required"}, 400
                
            token = request.cookies.get('token')
            from helpers.auth_helper import verify_token
            user = verify_token(token)
            if not user:
                if hasattr(ChatSend, 'anonymous_used') and ChatSend.anonymous_used:
                    return {"error": "Please login to continue chatting"}, 401
                ChatSend.anonymous_used = True
            else:
                if user.freeCredits <= 0:
                    return {"error": "You have no more credits left"}, 403
                user.update(dec__freeCredits=1)
                
            # Process image from request
            image_data = data.get('image')
            
            # image_data could be a URL or base64 encoded image
            # our prepare_content function will handle both cases
            if image_data:
                if isinstance(image_data, str):
                    print(f"Image data received, type: string, length: {len(image_data)}")
                    if image_data.startswith('data:image'):
                        print("Image format: data URL (data:image)")
                    elif image_data.startswith(('http://', 'https://')):
                        print(f"Image format: URL ({image_data})")
                    else:
                        print(f"Image format: raw base64 (first 20 chars: {image_data[:20]}...)")
                else:
                    print(f"Image data received, type: {type(image_data)}")
            else:
                print("No image data received")
            
            figma_file = request.files.get('figma_file')
            figma_link = data.get('figma_link')
            figma_token = API_TOKEN if data.get('figma_token') is None else data.get('figma_token')
            
            if figma_file:
                try:
                    figma_data = figma_file.read()
                    figma_analysis = process_figma_file(figma_data)
                    prompt += f"\n[Figma file analysis: {figma_analysis}]"
                except Exception as e:
                    return {"error": f"Figma file processing failed: {str(e)}"}, 400
                    
            elif figma_link and figma_token:
                try:
                    # Extract file key from Figma link
                    file_key = figma_link.split('/')[-1]
                    if '?' in file_key:
                        file_key = file_key.split('?')[0]
                    
                    # Process the Figma file via API
                    figma_analysis = process_figma_file_api(file_key, figma_token)
                    prompt += f"\n[Figma API analysis: {figma_analysis}]"
                except Exception as e:
                    return {"error": f"Figma API processing failed: {str(e)}"}, 400
            
            chat = Chat.objects(id=chat_id).first()
            if not chat:
                return {"error": "Chat not found"}, 404
                
            # Build conversation history context from existing messages
            history = ""
            # Append the new user prompt
            full_prompt = history + f"User: {prompt}\nBot:"
            
            if user:
                word_count = len(full_prompt.split())
                if user.freeCredits < word_count:
                    return {"error": "You have no more credits left"}, 403
                user.update(dec__freeCredits=word_count)
            
            # Generate AI response - pass single URL or None, not the raw image_data
            ai_response = generate_response(image_data, full_prompt)
            
            try:
                # Verify the response is valid JSON
                if is_valid_json(ai_response):
                    # It's already valid JSON, no need to alter
                    pass
                else:
                    # If not valid JSON, wrap it in a basic structure
                    ai_response = json.dumps({
                        "/index.js": {
                            "code": ai_response
                        }
                    })
            except Exception as e:
                print(f"Error processing AI response: {e}", flush=True)
                # Fallback if any error occurs during processing
                ai_response = json.dumps({
                    "/index.js": {
                        "code": ai_response
                    }
                })

            # Save the new message
            new_msg = ChatMessage(prompt=prompt, response=ai_response)
            new_msg.save()
            chat.update(push__chat_messages=new_msg)
                
            return {
                "chat_id": str(chat.id),
                "message_id": str(new_msg.id),
                "response": ai_response,
            }, 200
        except Exception as e:
            print(f"Critical error in chat send: {str(e)}", flush=True)
            traceback.print_exc()
            return {"error": f"Failed to process request: {str(e)}"}, 500

@chat_ns.route('/send-code')
class ChatSendCode(Resource):
    # Remove the validation requirement which is causing the 415 error
    # @chat_ns.expect(chat_model, validate=True)
    def post(self):
        try:
            """
            Send a chat prompt to an existing chat to generate code response,
            and update the related message's code attribute with the AI response.
            """
            # Debug the incoming request
            content_type = request.headers.get('Content-Type', '')
            
            # Handle different content types
            if 'multipart/form-data' in content_type:
                # This is a form submission with files
                data = request.form.to_dict()
            else:
                # Try to parse as JSON
                try:
                    data = request.get_json(force=True) or {}  # force=True tries to parse JSON even if Content-Type is wrong
                except Exception as e:
                    print(f"Error parsing JSON: {str(e)}", flush=True)
                    # Last resort, check if we can get form data
                    data = request.form.to_dict() or {}
            
            prompt = data.get('prompt', '')
            chat_id = data.get('chat_id')
            print(f"Send Code Prompt: {prompt}", flush=True)
            sys.stdout.flush()
            
            if not chat_id:
                return {"error": "Chat id is required"}, 400
                
            token = request.cookies.get('token')
            from helpers.auth_helper import verify_token
            user = verify_token(token)
            if not user:
                if hasattr(ChatSendCode, 'anonymous_used') and ChatSendCode.anonymous_used:
                    return {"error": "Please login to continue chatting"}, 401
                ChatSendCode.anonymous_used = True
            else:
                if user.freeCredits <= 0:
                    return {"error": "You have no more credits left"}, 403
                user.update(dec__freeCredits=1)
            
            # Process image from request
            image_data = data.get('image')
            
            # image_data could be a URL or base64 encoded image
            # our prepare_content function will handle both cases
            if image_data:
                print(f"Image data received for code generation, length: {len(str(image_data))}")
            
            figma_file = request.files.get('figma_file')
            figma_link = data.get('figma_link')
            figma_token = API_TOKEN if data.get('figma_token') is None else data.get('figma_token')
                   
            if figma_file:
                try:
                    figma_data = figma_file.read()
                    figma_analysis = process_figma_file(figma_data)
                    prompt += f"\n[Figma file analysis: {figma_analysis}]"
                except Exception as e:
                    print(f"Figma file processing error: {str(e)}", flush=True)
                        
            elif figma_link and figma_token:
                try:
                    # Extract file key from Figma link
                    file_key = figma_link.split('/')[-1]
                    if '?' in file_key:
                        file_key = file_key.split('?')[0]
                        
                    # Process the Figma file via API
                    figma_analysis = process_figma_file_api(file_key, figma_token)
                    prompt += f"\n[Figma API analysis: {figma_analysis}]"
                except Exception as e:
                    print(f"Figma API processing error: {str(e)}", flush=True)
                
            # Continue with chat processing
            try:
                chat = Chat.objects(id=chat_id).first()
                if not chat:
                    return {"error": "Chat not found"}, 404
                    
                # Build conversation history context from existing messages
                history = ""
                # Append the new user prompt
                full_prompt = history + f"User: {prompt}\nBot:"
                
                if user:
                    word_count = len(full_prompt.split())
                    if user.freeCredits < word_count:
                        return {"error": "You have no more credits left"}, 403
                    user.update(dec__freeCredits=word_count)
                
                # Generate AI response - pass single URL or None, not the raw image_data
                ai_response = generate_response(image_data, full_prompt)
                
                print(f"Send Code Response: {ai_response}", flush=True)
                sys.stdout.flush()

                # Save the new message
                new_msg = EditorMessage(prompt=prompt, response=ai_response)
                new_msg.save()
                chat.update(push__editor_messages=new_msg)
                
                return {
                    "chat_id": str(chat.id),
                    "message_id": str(new_msg.id),
                    "response": ai_response,
                    "new_message": {
                        "id": str(new_msg.id),
                        "prompt": new_msg.prompt,
                        "response": new_msg.response
                    }
                }, 200
            except Exception as e:
                print(f"Error in chat processing: {str(e)}", flush=True)
                return {"error": f"Failed to process request: {str(e)}"}, 500
        except Exception as e:
            print(f"Critical error in code send: {str(e)}", flush=True)
            traceback.print_exc()
            return {"error": f"Failed to process request: {str(e)}"}, 500

@chat_ns.route('/create')
class ChatCreate(Resource):
    # Remove the validation requirement which is causing the 415 error
    # @chat_ns.expect(chat_create_model, validate=True)
    def post(self, **kwargs):
        """Create a new chat with optional image or Figma file"""
        try:
            # Check if credits need to be refreshed
            check_and_refresh_credits()
            
            # Get user info
            token = request.cookies.get('token')
            user = None
            if token and token.strip():
                from helpers.auth_helper import verify_token
                user = verify_token(token)
            if not user:
                if request.cookies.get("anonymousCreated"):
                    return {"error": "Unauthenticated user cannot create multiple chats"}, 401
            
            # Debug the incoming request
            content_type = request.headers.get('Content-Type', '')
            
            # Handle different content types
            if 'multipart/form-data' in content_type:
                # This is a form submission with files
                data = request.form.to_dict()
            else:
                # Try to parse as JSON
                try:
                    data = request.get_json(force=True) or {}
                except Exception as e:
                    print(f"Error parsing JSON: {str(e)}", flush=True)
                    # Last resort, check if we can get form data
                    data = request.form.to_dict() or {}
            
            title = data.get('title', 'New Chat')
            prompt = data.get('prompt', '')
            print(f"Processing with title={title}, prompt={prompt}", flush=True)
            
            if not prompt:
                return {"error": "Prompt is required"}, 400
                
            full_prompt = prompt  # initialize full_prompt to prompt
            
            # Process image from request
            image_data = data.get('image')
            
            # image_data could be a URL or base64 encoded image
            # our prepare_content function will handle both cases
            if image_data:
                print(f"Image data received for chat creation, length: {len(str(image_data))}")
            
            figma_file = request.files.get('figma_file') if request.files else None
            figma_link = data.get('figma_link')
            figma_token = data.get('figma_token')
            
            if figma_file:
                try:
                    figma_data = figma_file.read()
                    figma_analysis = process_figma_file(figma_data)
                    full_prompt += f"\n[Figma file analysis: {figma_analysis}]"
                except Exception as e:
                    print(f"Figma file processing error: {str(e)}", flush=True)
            
            elif figma_link and figma_token:
                try:
                    # Extract file key from Figma link
                    file_key = figma_link.split('/')[-1]
                    if '?' in file_key:
                        file_key = file_key.split('?')[0]
                    
                    # Process the Figma file via API
                    figma_analysis = process_figma_file_api(file_key, figma_token)
                    print(f"Figma API analysis: {figma_analysis}", flush=True)
                    full_prompt += f"\n[Figma API analysis: {figma_analysis}]"
                except Exception as e:
                    print(f"Figma API processing error: {str(e)}", flush=True)
            
            # Create chat and generate response
            new_chat = Chat(title=title, chat_messages=[], editor_messages=[])
            new_chat.save()
            
            if user:
                user.update(push__chatIds=new_chat)
            
            try:
                # Generate AI response - pass single URL or None, not the raw image_data
                ai_response = generate_response(image_data, full_prompt)
                new_msg = ChatMessage(prompt=prompt, response=ai_response)
                new_msg.save()
                new_chat.update(push__chat_messages=new_msg)
                
                return {
                    "chat_id": str(new_chat.id), 
                    "message_id": str(new_msg.id),
                    "prompt": prompt,
                    "response": ai_response
                }, 201
            except Exception as e:
                # If AI response fails, still return the chat but with an error message
                error_msg = f"Failed to generate AI response: {str(e)}"
                new_msg = ChatMessage(prompt=prompt, response=error_msg)
                new_msg.save()
                new_chat.update(push__chat_messages=new_msg)
                
                print(f"Error in AI response: {str(e)}", flush=True)
                traceback.print_exc()
                
                return {
                    "chat_id": str(new_chat.id), 
                    "message_id": str(new_msg.id),
                    "prompt": prompt,
                    "response": error_msg,
                    "error": "Generated fallback response due to error"
                }, 201
                
        except Exception as e:
            print(f"Critical error in chat creation: {str(e)}", flush=True)
            traceback.print_exc()
            return {"error": f"Failed to create chat: {str(e)}"}, 500

@chat_ns.route('/<chat_id>')
class ChatDetail(Resource):
    @token_required
    def delete(self, user, chat_id):
        chat = Chat.objects(id=chat_id).first()
        if not chat or chat not in user.chatIds:
            return {"error": "Unauthorized"}, 401
        # Delete associated chat messages
        for msg in chat.chat_messages:
            msg.delete()
        # Delete associated editor messages if any
        for em in chat.editor_messages:
            em.delete()
        # Remove chat from user's chatIds
        user.update(pull__chatIds=chat)
        # Delete the chat
        chat.delete()
        return {"message": "Chat deleted"}, 200

    @chat_ns.expect(chat_update_model)
    @token_required
    def patch(self, user, chat_id):
        """Update chat details (e.g., title)"""
        chat = Chat.objects(id=chat_id).first()
        if not chat or chat not in user.chatIds:
            return {"error": "Unauthorized"}, 401
        data = request.get_json()
        chat.update(set__title=data['title'])
        return {"message": "Chat updated successfully"}, 200

    @token_required
    def get(self, user, chat_id):
        """Get complete chat details with full original content"""
        try:
            chat = Chat.objects(id=chat_id).first()
            if not chat:
                return {"error": "Chat not found"}, 404
                
            # Check if user has access to this chat
            if chat not in user.chatIds:
                return {"error": "Unauthorized access to chat"}, 403
                
            # Return the exact chat data from the database
            result = {
                "chat_id": str(chat.id),
                "title": chat.title,
                "created_at": str(chat.created_at),
                "messages": [],
                "code_messages": []
            }
            
            # Add chat messages with their EXACT data
            for msg in chat.chat_messages:
                result["messages"].append({
                    "id": str(msg.id),
                    "prompt": msg.prompt,
                    "response": msg.response,  # Exactly as stored in DB
                    "created_at": str(msg.created_at)
                })
            
            # Add editor messages with their EXACT data
            for msg in chat.editor_messages:
                result["code_messages"].append({
                    "id": str(msg.id),
                    "prompt": msg.prompt,
                    "response": msg.response,  # Exactly as stored in DB
                    "created_at": str(msg.created_at)
                })
            
            # Log what we're returning
            print(f"Returning chat {chat_id} with {len(result['messages'])} messages")
            if result['messages']:
                print(f"First message id: {result['messages'][0]['id']}")
                print(f"First message response starts with: {result['messages'][0]['response'][:50]}...")
            
            return result, 200
        except Exception as e:
            print(f"Error fetching chat details: {e}")
            traceback.print_exc()
            return {"error": str(e)}, 500

@chat_ns.route('/<chat_id>/message/<message_id>')
class MessageDetail(Resource):
    @token_required
    def get(self, user, chat_id, message_id):
        try:
            chat = Chat.objects(id=chat_id).first()
            if not chat or chat not in user.chatIds:
                return {"error": "Unauthorized"}, 401
                
            # First check chat messages
            msg = next((m for m in chat.chat_messages if str(m.id) == message_id), None)
            if msg:
                return {
                    "message_id": str(msg.id),
                    "prompt": msg.prompt,
                    "response": msg.response,  # Return exact database content
                    "message_type": "chat",
                    "created_at": str(msg.created_at) if msg.created_at else None
                }, 200
                
            # If not found in chat messages, check editor messages
            editor_msg = next((m for m in chat.editor_messages if str(m.id) == message_id), None)
            if editor_msg:
                return {
                    "message_id": str(editor_msg.id),
                    "prompt": editor_msg.prompt,
                    "response": editor_msg.response,  # Return exact database content
                    "message_type": "editor",
                    "created_at": str(editor_msg.created_at) if editor_msg.created_at else None
                }, 200
                
            return {"error": "Message not found"}, 404
        except Exception as e:
            print(f"Error fetching message detail: {e}", flush=True)
            traceback.print_exc()
            return {"error": f"Failed to fetch message: {str(e)}"}, 500

@chat_ns.route('/<chat_id>/messages')
class ChatMessages(Resource):
    @token_required
    def get(self, user, chat_id):
        try:
            chat = Chat.objects(id=chat_id).first()
            if not chat:
                return {"error": "Chat not found"}, 404

            # Process chat messages and preserve original response content
            chat_messages_list = []
            editor_messages_list = []
            
            # Get conversation messages
            for m in chat.chat_messages:
                # Extract shorter prompt for display if needed
                index_single = m.prompt.find("'")
                index_double = m.prompt.find('"')
                if index_single == -1:
                    index_single = len(m.prompt)
                if index_double == -1:
                    index_double = len(m.prompt)
                index = min(index_single, index_double)
                prompt_text = m.prompt[:index].strip()
                
                # Use the exact response from the database without modification
                chat_messages_list.append({
                    "message_id": str(m.id),
                    "prompt": prompt_text,
                    "full_prompt": m.prompt,  # Include full prompt for context
                    "response": m.response,   # Keep the exact response from database
                    "created_at": str(m.created_at) if m.created_at else None
                })
            
            # Get editor messages (code-specific messages)
            for m in chat.editor_messages:
                # Extract shorter prompt for display
                match = re.search(r'"([^"]+)"', m.prompt)
                prompt_text = match.group(1) if match else m.prompt
                
                # Keep the exact response from database
                editor_messages_list.append({
                    "message_id": str(m.id),
                    "prompt": prompt_text,
                    "full_prompt": m.prompt,
                    "response": m.response,  # This is the actual code from database
                    "created_at": str(m.created_at) if m.created_at else None
                })
            
            print(f"Returning {len(chat_messages_list)} chat messages and {len(editor_messages_list)} editor messages", flush=True)
            
            # Debug log actual content of a message if available
            if editor_messages_list:
                print(f"Sample editor message response (first 100 chars): {editor_messages_list[-1]['response'][:100]}...", flush=True)
            
            return {
                "chat_messages": chat_messages_list,
                "editor_messages": editor_messages_list,  # Return all editor messages as a list
                "editor_message": editor_messages_list[-1] if editor_messages_list else None  # For backward compatibility
            }, 200
        except Exception as e:
            print(f"Error fetching chat messages: {e}", flush=True)
            traceback.print_exc()
            return {"error": f"Failed to fetch chat messages: {str(e)}"}, 500

@chat_ns.route('/<chat_id>/message/<message_id>/like')
class MessageLike(Resource):
    @token_required
    def post(self, user, chat_id, message_id):
        chat = Chat.objects(id=chat_id).first()
        if not chat or str(chat.id) not in [str(c.id) for c in user.chatIds]:
            return {"error": "Unauthorized"}, 401
        message = next((m for m in chat.chat_messages if str(m.id) == message_id), None)
        if not message:
            return {"error": "Message not found"}, 404
        message.likes += 1
        message.save()
        return {"message": "Feedback Sent", "likes": message.likes}, 200

@chat_ns.route('/<chat_id>/message/<message_id>/dislike')
class MessageDislike(Resource):
    @token_required
    def post(self, user, chat_id, message_id):
        chat = Chat.objects(id=chat_id).first()
        if not chat or str(chat.id) not in [str(c.id) for c in user.chatIds]:
            return {"error": "Unauthorized"}, 401
        message = next((m for m in chat.chat_messages if str(m.id) == message_id), None)
        if not message:
            return {"error": "Message not found"}, 404
        message.dislikes += 1
        message.save()
        return {"message": "Feedback Sent", "dislikes": message.dislikes}, 200

@chat_ns.route('/<chat_id>/editor_message')
class EditorMessageAPI(Resource):
    """
    Routes related to EditorMessage associated with a given ChatMessage.
    """
    def get(self, chat_id, chat_message_id):
        """
        Fetch the EditorMessage details (including its JSON response) for a ChatMessage.
        """
        chat_msg = ChatMessage.objects(id=chat_message_id).first()
        if not chat_msg or not chat_msg.editor_message:
            return {"error": "EditorMessage not found"}, 404
        editor_msg_id = chat_msg.editor_message
        editor_msg = EditorMessage.objects(id=editor_msg_id).first()
        # Convert the string-based JSON in editor_msg.response to dict
        try:
            response_dict = json.loads(editor_msg.response) if editor_msg.response else {}
        except ValueError:
            response_dict = {}
        return {
            "editor_message_id": str(editor_msg.id),
            "prompt": editor_msg.prompt,
            "response": response_dict
        }, 200

    def patch(self, chat_id):
        """
        Update the last EditorMessage.response JSON (file-based code) for the given Chat.
        Accepts a JSON body with file paths + code updates.
        """
        chat = Chat.objects(id=chat_id).first()
        if not chat or not chat.editor_messages:
            return {"error": "EditorMessage not found"}, 404

        # Grab the last EditorMessage from the chat's editor_messages list
        editor_msg = chat.editor_messages[-1]
        # Convert the string-based JSON in editor_msg.response to dict
        try:
            existing_response = json.loads(editor_msg.response) if editor_msg.response else {}
        except ValueError:
            existing_response = {}

        # Merge or overwrite existing JSON response
        data = request.get_json()
        if "files" in data:
            existing_response = data["files"]
        else:
            existing_response.update(data)
        
        editor_msg.response = json.dumps(existing_response)
        editor_msg.save()
        return {"message": "Editor updated successfully"}, 200

@chat_ns.route('/<chat_id>/editor_message')
class EditorMessageCreateAPI(Resource):
    """
    Create a new EditorMessage and link it with the Chat if needed.
    """
    def post(self, chat_id):
        """
        Create a new EditorMessage object, optionally link it to a new or existing ChatMessage.
        """
        chat = Chat.objects(id=chat_id).first()
        if not chat:
            return {"error": "Chat not found"}, 404

        data = request.get_json() or {}
        prompt = data.get('prompt', 'Editor prompt')
        response_payload = data.get('response', {})  # expected to be a JSON object

        editor_msg = EditorMessage(prompt=prompt, response=json.dumps(response_payload))
        editor_msg.save()
        chat.update(push__editor_messages=editor_msg)
        return {
            "editor_message_id": str(editor_msg.id),
            "prompt": prompt,
            "response": response_payload
        }, 200

@chat_ns.route('/feedback')
class ChatFeedback(Resource):
    @chat_ns.expect(feedback_model, validate=True)
    @token_required
    def post(self, user):
        """Send user feedback to developers."""
        data = request.get_json() or {}
        from helpers.email_helper import send_user_feedback
        feedback_body = data.get('feedback', '')
        send_user_feedback(user.email, feedback_body)
        return {"message": "Feedback sent"}, 200

@chat_ns.route('/recent')
class RecentChats(Resource):
    """
    Endpoint specifically for getting recent chats with their complete content
    This preserves the exact data stored in the database
    """
    @token_required
    def get(self, user):
        try:
            # Get the 5 most recent chats
            chat_ids = [chat.id for chat in user.chatIds]
            recent_chats = Chat.objects(id__in=chat_ids).order_by('-created_at')[:5]
            
            result = []
            for chat in recent_chats:
                # Get all messages with full, unmodified content
                chat_data = {
                    "chat_id": str(chat.id),
                    "title": chat.title,
                    "created_at": str(chat.created_at),
                    "messages": [],
                    "code_messages": []
                }
                
                # Add all chat messages with their EXACT content from the database
                for msg in chat.chat_messages:
                    chat_data["messages"].append({
                        "id": str(msg.id),
                        "prompt": msg.prompt,
                        "response": msg.response,  # Return exactly as stored
                        "created_at": str(msg.created_at)
                    })
                
                # Add all editor messages with their EXACT content from the database
                for msg in chat.editor_messages:
                    chat_data["code_messages"].append({
                        "id": str(msg.id),
                        "prompt": msg.prompt,
                        "response": msg.response,  # Return exactly as stored
                        "created_at": str(msg.created_at) 
                    })
                
                result.append(chat_data)
            
            # Log what we're returning to help debug
            print(f"Returning {len(result)} recent chats")
            if result:
                sample_chat = result[0]
                print(f"Sample chat {sample_chat['chat_id']} has {len(sample_chat['messages'])} messages")
                if sample_chat['messages']:
                    sample_msg = sample_chat['messages'][0]
                    print(f"First message: id={sample_msg['id']}, response_length={len(sample_msg['response'])}")
            
            return {"chats": result}, 200
        except Exception as e:
            print(f"Error in recent chats: {e}")
            traceback.print_exc()
            return {"error": str(e)}, 500
