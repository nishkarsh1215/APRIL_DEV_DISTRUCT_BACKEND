from flask_restx import Namespace as RestxNamespace, Resource
from flask import request, jsonify
from infra.db.models import Chat, ChatMessage, EditorMessage
from helpers.auth_helper import token_required
import json
import traceback
import sys

# Create a dedicated namespace for these fixed endpoints
fix_ns = RestxNamespace('chat-fix', description='Fixed chat retrieval endpoints')

@fix_ns.route('/get-chat/<chat_id>')
class FixedChatDetail(Resource):
    """
    Endpoint that directly retrieves chat data with minimal processing
    """
    def get(self, chat_id):
        """Get raw chat content directly from database"""
        try:
            # Bypass token check temporarily for testing
            chat = Chat.objects(id=chat_id).first()
            if not chat:
                return {"error": "Chat not found"}, 404
            
            # Create simple dictionary to hold chat data
            result = {
                "id": str(chat.id),
                "title": chat.title,
                "created_at": str(chat.created_at),
                "messages": []
            }
            
            # Add messages with minimal processing
            for msg in chat.chat_messages:
                result["messages"].append({
                    "id": str(msg.id),
                    "prompt": msg.prompt,
                    "raw_response": msg.response  # Return raw database content
                })
            
            print(f"Successfully retrieved chat {chat_id} with {len(result['messages'])} messages", file=sys.stderr)
            if result['messages']:
                print(f"First message response sample: {result['messages'][0]['raw_response'][:100]}...", file=sys.stderr)
            
            return result
        except Exception as e:
            print(f"Error in fixed chat detail: {e}", file=sys.stderr)
            traceback.print_exc()
            return {"error": str(e)}, 500

@fix_ns.route('/raw-message/<message_id>')
class FixedRawMessage(Resource):
    """
    Endpoint that returns a single message exactly as stored in database
    """
    def get(self, message_id):
        """Get raw message content directly from database"""
        try:
            # First try ChatMessage
            chat_msg = ChatMessage.objects(id=message_id).first()
            if chat_msg:
                return {
                    "id": str(chat_msg.id),
                    "type": "chat",
                    "prompt": chat_msg.prompt,
                    "raw_response": chat_msg.response,  # Unmodified from database
                    "response_length": len(chat_msg.response) if chat_msg.response else 0
                }
            
            # Then try EditorMessage
            editor_msg = EditorMessage.objects(id=message_id).first()
            if editor_msg:
                return {
                    "id": str(editor_msg.id),
                    "type": "editor",
                    "prompt": editor_msg.prompt,
                    "raw_response": editor_msg.response,  # Unmodified from database
                    "response_length": len(editor_msg.response) if editor_msg.response else 0
                }
                
            return {"error": "Message not found"}, 404
        except Exception as e:
            print(f"Error in fixed raw message: {e}", file=sys.stderr)
            traceback.print_exc()
            return {"error": str(e)}, 500

@fix_ns.route('/recent')
class FixedRecentChats(Resource):
    """
    Endpoint that retrieves recent chats with minimal processing
    """
    def get(self):
        """Get recent chats directly from database"""
        try:
            # Skip authentication for testing
            recent_chats = Chat.objects().order_by('-created_at')[:5]
            
            result = []
            for chat in recent_chats:
                chat_data = {
                    "id": str(chat.id),
                    "title": chat.title,
                    "message_count": len(chat.chat_messages),
                    "created_at": str(chat.created_at)
                }
                
                # For simplicity, just include the most recent message
                if chat.chat_messages:
                    latest_msg = chat.chat_messages[-1]
                    chat_data["latest_message"] = {
                        "id": str(latest_msg.id),
                        "prompt": latest_msg.prompt,
                        "raw_response": latest_msg.response  # Original from database
                    }
                
                result.append(chat_data)
            
            return {"chats": result}
        except Exception as e:
            print(f"Error in fixed recent chats: {e}", file=sys.stderr)
            traceback.print_exc()
            return {"error": str(e)}, 500

@fix_ns.route('/message-direct/<message_id>')
class DirectMessageContent(Resource):
    """Return message content with no JSON processing at all"""
    def get(self, message_id):
        try:
            chat_msg = ChatMessage.objects(id=message_id).first()
            if chat_msg:
                # Return raw text directly from database with no JSON processing
                return chat_msg.response, 200, {'Content-Type': 'text/plain'}
            
            editor_msg = EditorMessage.objects(id=message_id).first()
            if editor_msg:
                # Return raw text directly from database with no JSON processing
                return editor_msg.response, 200, {'Content-Type': 'text/plain'}
                
            return "Message not found", 404, {'Content-Type': 'text/plain'}
        except Exception as e:
            print(f"Error in direct message content: {e}", file=sys.stderr)
            traceback.print_exc()
            return str(e), 500, {'Content-Type': 'text/plain'}
