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

# Load the YOLO model
model_yolo = YOLO('src/controllers/yolov8n_trained.pt')

API_TOKEN = os.getenv('FIGMA_API_TOKEN')

# Helper Functions

class_names = ['button', 'field', 'heading', 'iframe', 'image', 'label', 'link', 'text']

def analyze_gradient(image_array, num_colors=5):
    image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
    pixels = image_rgb.reshape((-1, 3))
    kmeans = KMeans(n_clusters=num_colors, random_state=42)
    kmeans.fit(pixels)
    dominant_colors = np.array(kmeans.cluster_centers_, dtype=int)
    gradient_magnitude = cv2.Laplacian(cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY), cv2.CV_64F)
    gradient_direction = cv2.phase(gradient_magnitude, gradient_magnitude, angleInDegrees=True)
    return dominant_colors.tolist(), gradient_direction.tolist()

def process_image(image_data):
    if hasattr(image_data, 'read'):
        image = Image.open(image_data)
    elif isinstance(image_data, str):
        # Handle both direct URLs and data URLs
        if image_data.startswith("http"):
            response = requests.get(image_data)
            if response.status_code != 200:
                raise Exception("Failed to retrieve image from URL")
            image = Image.open(BytesIO(response.content))
        else:
            # For data URLs, split the actual base64 content
            parts = image_data.split('base64,')
            if len(parts) == 2:
                image_str = parts[1]
            else:
                image_str = image_data
            image = Image.open(BytesIO(base64.b64decode(image_str)))
    else:
        raise Exception("Unsupported image input type")

    if image.mode != "RGB":
        image = image.convert("RGB")

    temp_path = f"temp_{uuid.uuid4()}.jpg"
    image.save(temp_path)
    mime_type = image.format.lower() if image.format else 'jpg'
    if mime_type in ['png', 'jpeg', 'jpg']:
        img = cv2.imread(temp_path)
        results = model_yolo(img)
        result_data = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                class_name = class_names[cls_id]
                x_min, y_min, x_max, y_max = box.xyxy[0].tolist()
                width = x_max - x_min
                height = y_max - y_min
                center_x = x_min + width / 2
                center_y = y_min + height / 2
                cropped_image = img[int(y_min):int(y_max), int(x_min):int(x_max)]
                dominant_colors, gradient_direction = analyze_gradient(cropped_image)
                result_data.append({
                    "class_id": cls_id,
                    "class_name": class_name,
                    "confidence": float(box.conf[0]),
                    "bbox": {
                        "width": width,
                        "height": height,
                        "center_x": center_x,
                        "center_y": center_y
                    },
                    "color_distribution": dominant_colors
                })
        analysis = result_data
    elif mime_type == 'pdf':
        analysis = "PDF content analysis not implemented"
    else:
        analysis = "Unsupported file type"
    os.remove(temp_path)
    return analysis

def generate_text_response(prompt):
    try:
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise Exception("Missing GOOGLE_API_KEY environment variable")
            
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "text/plain",
        }

        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config=generation_config,
        )

        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(prompt)
        return response.text
    except Exception as e:
        print(f"Error in generate_text_response: {str(e)}", flush=True)
        traceback.print_exc()
        # Fallback response in case of error
        return f"I'm sorry, but I encountered an error: {str(e)}"

def generate_code_response(prompt, image_file=None):
    try:
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise Exception("Missing GOOGLE_API_KEY environment variable")
            
        genai.configure(api_key=api_key)
        generation_config = {
            "temperature": 1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }

        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",  # Using a safer model choice
            generation_config=generation_config,
        )

        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(prompt)
        return response.text
    except Exception as e:
        print(f"Error in generate_code_response: {str(e)}", flush=True)
        traceback.print_exc()
        # Return a valid JSON as fallback
        return json.dumps({"error": str(e)})

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
        # Check if credits need to be refreshed
        check_and_refresh_credits()
        # Convert Chat references to ObjectIds
        chat_ids = [chat.id for chat in user.chatIds]
        chats = Chat.objects(id__in=chat_ids).order_by('-created_at')[:10]
        history = []
        for chat in chats:
            messages = [{
                "prompt": msg.prompt,
                "response": msg.response,
                "code": msg.response,
                "created_at": str(msg.created_at) if msg.created_at else None
            } for msg in chat.chat_messages]
            history.append({
                "chat_id": str(chat.id),
                "title": chat.title,
                "messages": messages,
                "created_at": str(chat.created_at) if chat.created_at else None
            })
        return {"history": history}, 200

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
            print(f"Send Content-Type received: {content_type}", flush=True)
            
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
                
            # Process image from request.files or data
            image_file = request.files.get('image')
            figma_file = request.files.get('figma_file')
            figma_link = data.get('figma_link')
            figma_token = API_TOKEN if data.get('figma_token') is None else data.get('figma_token')
            
            if image_file:
                try:
                    analysis = process_image(image_file)
                    prompt += f"\n[Image analysis: {analysis}]"
                except Exception as e:
                    prompt += f"\n[Image analysis failed: {str(e)}]"
                    print(f"Image processing error: {str(e)}")
                    
            elif figma_file:
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
            
            ai_response = generate_text_response(full_prompt)
            
            try:
                # Verify the response is valid JSON
                json.loads(ai_response)
            except:
                # If not valid JSON, wrap it in a basic structure
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
            print(f"Send-code Content-Type received: {content_type}", flush=True)
            print(f"Send-code Form data: {request.form}", flush=True)
            print(f"Send-code Files: {request.files}", flush=True)
            
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
            
            # Process image or figma file from request.files
            try:
                image_file = request.files.get('image')
                figma_file = request.files.get('figma_file')
                figma_link = data.get('figma_link')
                figma_token = API_TOKEN if data.get('figma_token') is None else data.get('figma_token')
                
                if image_file:
                    try:
                        analysis = process_image(image_file)
                        prompt += f"\n[Image analysis: {analysis}]"
                    except Exception as e:
                        print(f"Image processing error: {str(e)}", flush=True)
                        
                elif figma_file:
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
            except Exception as e:
                print(f"Error in file processing: {str(e)}", flush=True)
                
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
                
                ai_response = generate_code_response(full_prompt, image_file)
                
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
            print(f"Create Content-Type received: {content_type}", flush=True)
            print(f"Create Form data: {request.form}", flush=True)
            print(f"Create Files: {request.files}", flush=True)
            
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
            
            # Process image or Figma file if provided
            image_data = data.get('image')
            figma_file = request.files.get('figma_file') if request.files else None
            figma_link = data.get('figma_link')
            figma_token = data.get('figma_token')
            
            if image_data:
                try:
                    analysis = process_image(image_data)
                    full_prompt += f"\n[Image analysis: {analysis}]"
                except Exception as e:
                    print(f"Image processing error: {str(e)}", flush=True)
            
            elif figma_file:
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
                ai_response = generate_text_response(full_prompt)
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

@chat_ns.route('/<chat_id>/message/<message_id>')
class MessageDetail(Resource):
    @token_required
    def get(self, user, chat_id, message_id):
        chat = Chat.objects(id=chat_id).first()
        if not chat or chat not in user.chatIds:
            return {"error": "Unauthorized"}, 401
        msg = next((m for m in chat.chat_messages if str(m.id) == message_id), None)
        if not msg:
            return {"error": "Message not found"}, 404
        return {
            "message_id": str(msg.id),
            "prompt": msg.prompt,
            "response": msg.response
        }, 200

@chat_ns.route('/<chat_id>/messages')
class ChatMessages(Resource):
    @token_required
    def get(self, user, chat_id):
        chat = Chat.objects(id=chat_id).first()
        if not chat:
            return {"error": "Chat not found"}, 404

        chat_messages_list = []
        editor_messages_list = []
        for m in chat.chat_messages:
            index_single = m.prompt.find("'")
            index_double = m.prompt.find('"')
            if index_single == -1:
                index_single = len(m.prompt)
            if index_double == -1:
                index_double = len(m.prompt)
            index = min(index_single, index_double)
            prompt_text = m.prompt[:index].strip()
            chat_messages_list.append({
                "message_id": str(m.id),
                "prompt": prompt_text,
                "response": m.response,
                "created_at": str(m.created_at) if m.created_at else None
            })
        for m in chat.editor_messages:
            match = re.search(r'"([^"]+)"', m.prompt)
            prompt_text = match.group(1) if match else m.prompt
            editor_messages_list.append({
                "message_id": str(m.id),
                "prompt": prompt_text,
                "response": m.response,
                "created_at": str(m.created_at) if m.created_at else None
            })
        sys.stdout.flush()
        return {
            "chat_messages": chat_messages_list,
            "editor_message": editor_messages_list[-1] if editor_messages_list else None
        }, 200

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
