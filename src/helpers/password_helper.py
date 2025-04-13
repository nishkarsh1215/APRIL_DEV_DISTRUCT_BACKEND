import jwt
from flask import current_app
from datetime import datetime, timedelta, timezone

def generate_password_reset_token(user_id):
    """Generate JWT token valid for 5 minutes"""
    payload = {
        'exp': datetime.now(timezone.utc) + timedelta(minutes=5),
        'iat': datetime.now(timezone.utc),
        'sub': str(user_id),
        'type': 'password_reset'
    }
    return jwt.encode(
        payload,
        current_app.config['JWT_SECRET'],
        algorithm='HS256'
    )

def verify_password_reset_token(token):
    """Verify password reset token"""
    try:
        payload = jwt.decode(
            token, 
            current_app.config['JWT_SECRET'],
            algorithms=['HS256']
        )
        if payload.get('type') != 'password_reset':
            return None
        return payload['sub']
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None