#!/usr/bin/env python3
"""
Script to directly test and fix chat data.
"""

import sys
import os
import json
import traceback
from bson import ObjectId

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.db.db_config import init_db
from infra.db.models import Chat, ChatMessage, EditorMessage, User

def fix_chat_data(chat_id=None):
    """Directly read and potentially fix chat data"""
    init_db()  # Initialize database connection
    
    if not chat_id:
        # Get the most recent chat
        chat = Chat.objects().order_by('-created_at').first()
        if chat:
            chat_id = str(chat.id)
    
    if not chat_id:
        print("No chats found in database")
        return
    
    try:
        chat = Chat.objects(id=chat_id).first()
        if not chat:
            print(f"Chat not found with ID: {chat_id}")
            return
            
        print(f"Chat: {chat.id} - {chat.title}")
        print(f"Message count: {len(chat.chat_messages)}")
        
        for i, msg in enumerate(chat.chat_messages):
            print(f"\nMessage {i+1}:")
            print(f"ID: {msg.id}")
            print(f"Prompt: {msg.prompt[:50]}...")
            
            # Check and print raw response
            response = msg.response
            print(f"Response length: {len(response) if response else 0}")
            print(f"Response sample: {response[:100]}..." if response else "No response")
            
            # Check if valid JSON
            try:
                if response:
                    json_data = json.loads(response)
                    print(f"Valid JSON with keys: {list(json_data.keys())}")
            except:
                print("Not valid JSON")
        
        # Ask if user wants to export chat data
        export = input("\nDo you want to export this chat data for debugging? (y/n): ")
        if export.lower() == 'y':
            export_path = f"chat_{chat_id}_export.json"
            with open(export_path, 'w') as f:
                # Create export object
                export_data = {
                    "chat_id": str(chat.id),
                    "title": chat.title,
                    "messages": []
                }
                
                for msg in chat.chat_messages:
                    export_data["messages"].append({
                        "id": str(msg.id),
                        "prompt": msg.prompt,
                        "response": msg.response
                    })
                
                json.dump(export_data, f, indent=2)
                print(f"Chat data exported to {export_path}")
                
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # Can specify a chat ID as command line argument
    chat_id = sys.argv[1] if len(sys.argv) > 1 else None
    fix_chat_data(chat_id)
