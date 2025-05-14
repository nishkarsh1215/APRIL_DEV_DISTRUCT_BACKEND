#!/usr/bin/env python3
"""
Script to directly check database contents.
Run with: python3 check_db.py
"""

import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.db.db_config import init_db
from infra.db.models import Chat, ChatMessage, EditorMessage, User

def check_chat_data():
    """Check data for a specific chat ID or the most recent chat"""
    init_db()  # Initialize database connection
    
    # Get chat ID from command line or use the most recent one
    if len(sys.argv) > 1:
        chat_id = sys.argv[1]
        chat = Chat.objects(id=chat_id).first()
    else:
        # Get the most recent chat
        chat = Chat.objects().order_by('-created_at').first()
    
    if not chat:
        print("No chat found")
        return
    
    print(f"Chat ID: {chat.id}")
    print(f"Title: {chat.title}")
    print(f"Created at: {chat.created_at}")
    
    print("\nChat Messages:")
    for i, msg in enumerate(chat.chat_messages):
        print(f"\nMessage {i+1}:")
        print(f"ID: {msg.id}")
        print(f"Prompt: {msg.prompt[:100]}...")
        print(f"Response (first 200 chars): {msg.response[:200]}...")
        print(f"Response length: {len(msg.response)}")
        print(f"Created at: {msg.created_at}")
    
    print("\nEditor Messages:")
    for i, msg in enumerate(chat.editor_messages):
        print(f"\nEditor Message {i+1}:")
        print(f"ID: {msg.id}")
        print(f"Prompt: {msg.prompt[:100]}...")
        print(f"Response (first 200 chars): {msg.response[:200]}...")
        print(f"Response length: {len(msg.response)}")
        
        # Try to parse JSON
        try:
            data = json.loads(msg.response)
            print(f"Valid JSON with {len(data)} keys")
            print(f"Keys: {list(data.keys())}")
        except:
            print("Not valid JSON")
        
        print(f"Created at: {msg.created_at}")

if __name__ == "__main__":
    check_chat_data()
