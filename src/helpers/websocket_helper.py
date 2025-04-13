import jwt
from flask import current_app
from infra.db.models import User
from bson import ObjectId

def verify_websocket_token(token):
    try:
        payload = jwt.decode(token, current_app.config['JWT_SECRET'], algorithms=['HS256'])
        return User.objects(id=ObjectId(payload['sub'])).first()
    except:
        return None