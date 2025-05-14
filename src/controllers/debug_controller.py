from flask_restx import Namespace as RestxNamespace, Resource
from flask import jsonify
from infra.db.models import Chat, ChatMessage, EditorMessage
from helpers.auth_helper import token_required
import json

debug_ns = RestxNamespace('debug', description='Debugging endpoints')

@debug_ns.route('/raw-message/<message_id>')
class RawMessageDebug(Resource):
    @token_required
    def get(self, user, message_id):
        """Fetch raw message data for debugging purposes"""
        # Try to find the message in chat messages
        chat_msg = ChatMessage.objects(id=message_id).first()
        if chat_msg:
            # Return the raw data from the database
            return {
                "type": "chat_message",
                "prompt": chat_msg.prompt,
                "response": chat_msg.response,
                "response_length": len(chat_msg.response) if chat_msg.response else 0,
                "created_at": str(chat_msg.created_at) if chat_msg.created_at else None
            }
            
        # If not found, try to find in editor messages
        editor_msg = EditorMessage.objects(id=message_id).first()
        if editor_msg:
            # Return the raw data from the database
            response_str = editor_msg.response
            
            # Check if it's valid JSON
            try:
                parsed = json.loads(response_str) if response_str else {}
                is_json = True
            except:
                parsed = {}
                is_json = False
                
            return {
                "type": "editor_message",
                "prompt": editor_msg.prompt,
                "response": response_str,
                "response_length": len(response_str) if response_str else 0,
                "is_valid_json": is_json,
                "parsed_sample": str(list(parsed.keys())[:5]) if is_json else None,
                "created_at": str(editor_msg.created_at) if editor_msg.created_at else None
            }
            
        return {"error": "Message not found"}, 404
