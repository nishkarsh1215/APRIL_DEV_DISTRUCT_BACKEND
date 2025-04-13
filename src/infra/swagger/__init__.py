from flask_restx import Api
from flask_restx import fields

api = Api(
    version="1.0",
    title="AI Chat + Code Editor API",
    description="API Documentation for the backend",
    doc="/swagger/", 
    security="Bearer Auth",
    authorizations={
        "Bearer Auth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "JWT Token: **Bearer {token}**"
        }
    }
)

chat_model = api.model('ChatMessage', {
    'prompt': fields.String(required=True),
    'image': fields.String(description='Base64 encoded image (optional)')
})

api.namespaces[0].models.update({
    'CreditInfo': api.model('CreditInfo', {
        'remaining': fields.Integer,
        'message': fields.String
    })
})