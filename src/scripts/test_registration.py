#!/usr/bin/env python3
"""
Test script for user registration.
"""

import sys
import os
import json
import requests

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_registration(email, password, name=None):
    """Test user registration API"""
    url = "http://localhost:5000/api/auth/register"
    
    data = {
        "email": email,
        "password": password
    }
    
    if name:
        data["name"] = name
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"Sending request to: {url}")
    print(f"Request data: {json.dumps(data, indent=2)}")
    
    try:
        response = requests.post(url, json=data, headers=headers)
        print(f"Status code: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 201:
            print("Registration successful!")
        else:
            print(f"Registration failed: {response.json().get('error', 'Unknown error')}")
    except Exception as e:
        print(f"Request failed: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_registration.py <email> <password> [name]")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else None
    
    test_registration(email, password, name)
