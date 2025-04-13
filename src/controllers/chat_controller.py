from flask_restx import Namespace as RestxNamespace, Resource, fields
from flask import request
from ultralytics import YOLO
from infra.db.models import ChatMessage, EditorMessage
from helpers.auth_helper import token_required
import cv2, easyocr, re
from PIL import Image
from io import BytesIO
import base64
import os
import uuid
import requests
from middlewares.auth_middleware import credit_required
from infra.swagger import api
import google.generativeai as genai
from infra.db.models import Chat
import json
import numpy as np
from sklearn.cluster import KMeans
import sys
# Load the YOLO model
model_yolo = YOLO('controllers\yolov8n_trained.pt')

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
        print(result_data)
        analysis = result_data
    elif mime_type == 'pdf':
        analysis = "PDF content analysis not implemented"
    else:
        analysis = "Unsupported file type"
    os.remove(temp_path)
    return analysis

def generate_text_response(prompt):
    api_key = os.getenv('GOOGLE_API_KEY')
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
    
    if not api_key:
        raise Exception("Missing GOOGLE_API_KEY environment variable")
    
    return response.text

def generate_code_response(prompt):
    api_key = os.getenv('GOOGLE_API_KEY')
    genai.configure(api_key=api_key)

    generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
    }

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config=generation_config,
    )

    chat_session = model.start_chat(history=[])
    
    response = chat_session.send_message(prompt)
    

    if not api_key:
        raise Exception("Missing GOOGLE_API_KEY environment variable")
    
    return response.text

# Define REST namespace for chat endpoints
chat_ns = RestxNamespace('chat', description='HTTP-based chat endpoints')
chat_model = api.model('ChatMessage', {
    'prompt': fields.String(required=True, description="Prompt message"),
    'image': fields.String(description="Base64 encoded image (optional)"),
    'chat_id': fields.String(required=True, description="Existing chat id")
})

# New model for chat creation
chat_create_model = api.model('ChatCreate', {
    'title': fields.String(required=True, description="Chat title"),
    'prompt': fields.String(required=True, description="Initial chat prompt"),
    'image': fields.String(description="Base64 encoded image (optional)")
})

chat_update_model = api.model('ChatUpdate', {
    'title': fields.String(required=True, description="Chat title")
})

feedback_model = api.model('Feedback', {
    'feedback': fields.String(required=True, description="User feedback text")
})

@chat_ns.route('/history')
class ChatHistory(Resource):
    @token_required
    def get(self, user):
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
    @chat_ns.expect(chat_model, validate=True)
    def post(self):
        """
        Send a chat prompt to an existing chat, remembering earlier conversation.
            "Generate a React code that displays the following UI elements with their respective "
            "positions, sizes, and color distributions according to class names, first think about them according to their extracted text and rethink that whether they should be class names if their  confidence scores  are low, for example, if extracted text is 'click me' it will be a button right? so think accordingly and use colors ... if class name is field it's an input field obviously:\n\n"
            f"\n Please generate a good website. It should look like a well-designed website. Adjust as needed—you are super good at making websites! Make a good looking website... the data that I am giving is just the reference you have to think and make it look good... also  take in consideration of positions and height width... listen they dont need to be accurate but similar butsomewhat similar to whats in height width and position. take  in consideration of dominant color as well."
        """
        data = request.form.to_dict() if request.form else request.get_json() or {}
        prompt = data.get('prompt', '')
        print("this is /send prompt", flush=True)
        sys.stdout.flush()
        print(prompt, flush=True)
        sys.stdout.flush()
        chat_id = data.get('chat_id')
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
        # Process image from request.files if provided
        image_file = request.files.get('image')
        
        #image_file
        
        if image_file:
            try:
                analysis = process_image(image_file)
            except Exception as e:
                return {"error": f"Image processing failed: {str(e)}"}, 400
            prompt += f"\n[Image analysis: {analysis}]"
        chat = Chat.objects(id=chat_id).first()
        if not chat:
            return {"error": "Chat not found"}, 404
        # Build conversation history context from existing messages
        history = ""
        # Sort messages ascending by creation time
        # for msg in sorted(chat.chat_messages, key=lambda m: m.created_at):
        #     history += f"User: {msg.prompt}\nBot: {msg.response}\n"

        # Append the new user prompt
        full_prompt = history + f"User: {prompt}\nBot:"
        
        ai_response = generate_text_response(full_prompt)   #############################-------<<<<<<<

        # Save the new message
        new_msg = ChatMessage(prompt=prompt, response=ai_response)
        new_msg.save()
        chat.update(push__chat_messages=new_msg)
        print("ai_res[ponse]")
        print(f'\n\n\n{ai_response}\n\n\n\n\n', flush=True)
        sys.stdout.flush()

            
        return {
            "chat_id": str(chat.id),
            "message_id": str(new_msg.id),
            "response": ai_response,
        }, 200

@chat_ns.route('/send-code')
class ChatSend(Resource):
    @chat_ns.expect(chat_model, validate=True)
    def post(self):
        """
        Send a chat prompt to an existing chat to generate code response,
        and update the related message's code attribute with the AI response.
            "Generate a React code that displays the following UI elements with their respective "
            "positions, sizes, and color distributions according to class names, first think about them according to their extracted text and rethink that whether they should be class names if their  confidence scores  are low, for example, if extracted text is 'click me' it will be a button right? so think accordingly and use colors ... if class name is field it's an input field obviously:\n\n"
            f"\n Please generate a good website. It should look like a well-designed website. Adjust as needed—you are super good at making websites! Make a good looking website... the data that I am giving is just the reference you have to think and make it look good... also  take in consideration of positions and height width... listen they dont need to be accurate but similar butsomewhat similar to whats in height width and position. take  in consideration of dominant color as well."
        """
        data = request.form.to_dict() if request.form else request.get_json() or {}
        prompt = data.get('prompt', '')
        print("this is /send-code prompt", flush=True)
        sys.stdout.flush()
        print(prompt, flush =True)
        sys.stdout.flush()
        chat_id = data.get('chat_id')
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
        # Process image from request.files if provided
        image_file = request.files.get('image')
        if image_file:
            try:
                analysis = process_image(image_file)
            except Exception as e:
                return {"error": f"Image processing failed: {str(e)}"}, 400
            prompt += f"\n[Image analysis: {analysis}]"
        chat = Chat.objects(id=chat_id).first()
        if not chat:
            return {"error": "Chat not found"}, 404
        # Build conversation history context from existing messages
        history = ""
        # Sort messages ascending by creation time
        # for msg in sorted(chat.chat_messages, key=lambda m: m.created_at):
        #     history += f"User: {msg.prompt}\nBot: {msg.response}\n"
        # Append the new user prompt
        full_prompt = history + f"User: {prompt}\nBot: "
        ai_response = generate_code_response(full_prompt)
        # Create a new message with code response stored in the code attribute
        new_msg = EditorMessage(prompt=prompt, response=ai_response)
        new_msg.save()
        chat.update(push__editor_messages=new_msg)
        
        print("codeeeeeeeeeeeeeeeeeeeeeeeee", flush=True)
        sys.stdout.flush()

        print(f'\n\n{ai_response}\n\n\n\n\n\n\n', flush=True)
        sys.stdout.flush()

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

def generate_and_update_message(chat_id, message_id, prompt):
    # Re-fetch chat and message from DB
    chat = Chat.objects(id=chat_id).first()
    message = EditorMessage.objects(id=message_id).first()
    if not chat or not message:
        return
    # Build full prompt (here, no history because it's the first message)
    full_prompt = f"User: {prompt}\nBot: "
    ai_response = generate_text_response(full_prompt)
    print("update the message docccccccccccccccccc", flush =True)
    sys.stdout.flush()
    print(f'\n\n\n{ai_response}\n\n', flush=True)
    sys.stdout.flush()


    
    # Update the message document with AI response and code
    message.response = ai_response
    message.save()

@chat_ns.route('/create')
class ChatCreate(Resource):
    @chat_ns.expect(chat_create_model, validate=True)
    def post(self, **kwargs):
        print("create route create route", flush=True)
        sys.stdout.flush()
        token = request.cookies.get('token')
        user = None
        if token and token.strip():
            from helpers.auth_helper import verify_token
            user = verify_token(token)
        if not user:
            if request.cookies.get("anonymousCreated"):
                return {"error": "Unauthenticated user cannot create multiple chats"}, 401
        
        data = request.get_json()
        title = data.get('title')
        prompt = data.get('prompt', '')
        print("this is /create route", flush=True)
        sys.stdout.flush()
        print(prompt, flush =True)
        sys.stdout.flush()
        full_prompt = prompt  # initialize full_prompt to prompt
        # Process image if provided
        image_data = data.get('image')
        if image_data:
            try:
                analysis = process_image(image_data)
                full_prompt += f"\n[Image analysis: {analysis}]"
            except Exception as e:
                return {"error": f"Image processing failed: {str(e)}"}, 400
        
        new_chat = Chat(title=title, chat_messages=[], editor_messages=[])
        new_chat.save()
        
        if user:
            user.update(push__chatIds=new_chat)
        
        ai_response = generate_text_response(full_prompt)
        new_msg = ChatMessage(prompt=prompt, response=ai_response)
        new_msg.save()
        new_chat.update(push__chat_messages=new_msg)
        
        print("/create", flush=True)
        sys.stdout.flush()
        print(f'\n\n\n{ai_response}\n\n\n', flush=True)
        sys.stdout.flush()
        
        return {
            "chat_id": str(new_chat.id), 
            "message_id": str(new_msg.id),
            "prompt": prompt,
            "response": ai_response
        }, 201

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
        return {"message": "Chat deleted"}

    @chat_ns.expect(chat_update_model)
    @token_required
    def patch(self, user, chat_id):
        """Update chat details (e.g., title)"""
        from infra.db.models import Chat
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
        from infra.db.models import Chat
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
        print("\n\n\n\n")
        print("editor messages")
        print(editor_messages_list, flush=True)
        sys.stdout.flush()
        print("\n\n\n\n")
            
        return {
            "chat_messages": chat_messages_list,
            "editor_message": editor_messages_list[-1] if editor_messages_list else None
            }, 200

@chat_ns.route('/<chat_id>/message/<message_id>/like')
class MessageLike(Resource):
    @token_required
    def post(self, user, chat_id, message_id):
        from infra.db.models import Chat
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
        from infra.db.models import Chat
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
        from infra.db.models import Chat  # ensure Chat is imported here if not already
        chat = Chat.objects(id=chat_id).first()
        if not chat or not chat.editor_messages:
            return {"error": "EditorMessage not found"}, 404

        # Grab the last EditorMessage from the chat's editor_messages list
        editor_msg = chat.editor_messages[-1]

        data = request.get_json()
        # Merge or overwrite existing JSON response
        try:
            existing_response = json.loads(editor_msg.response) if editor_msg.response else {}
        except ValueError:
            existing_response = {}

        # If data contains 'files', overwrite the response with its content
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
        }, 201

@chat_ns.route('/feedback')
class ChatFeedback(Resource):
    @chat_ns.expect(feedback_model, validate=True)
    @token_required
    def post(self, user):
        """Send user feedback to developers."""
        data = request.get_json() or {}
        feedback_body = data.get('feedback', '')
        from helpers.email_helper import send_user_feedback
        send_user_feedback(user.email, feedback_body)
        return {"message": "Feedback sent"}, 200
