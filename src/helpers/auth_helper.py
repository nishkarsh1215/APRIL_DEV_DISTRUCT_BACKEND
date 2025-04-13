import jwt
from datetime import datetime, timedelta, timezone
from flask import current_app
import jwt.utils
from infra.db.models import User
from functools import wraps
from flask import request

def generate_token(user_id):
    payload = {
        'exp': datetime.now(timezone.utc) + timedelta(days=7),
        'iat': datetime.now(timezone.utc),
        'sub': str(user_id)
    }
    secret = current_app.config.get('JWT_SECRET')
    return jwt.encode(
        payload,
        str(secret),
        algorithm='HS256'
    )

def verify_token(token):
    try:
        payload = jwt.decode(
            token, 
            current_app.config['JWT_SECRET'],
            algorithms=['HS256']
        )
        return User.objects(id=payload['sub']).first()  # changed 'query.get' to 'objects'
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('token')  # read token from cookie first
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        if not token:
            return {"error": "Missing or invalid token"}, 401
        
        user = verify_token(token)
        if not user:
            return {"error": "Unauthorized"}, 401
        
        # Pass user as a keyword argument without disturbing positional args.
        return f(*args, user=user, **kwargs)
    return decorated