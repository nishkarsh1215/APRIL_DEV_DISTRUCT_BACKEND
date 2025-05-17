import os
from flask import request, jsonify
from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS

from infra.db.db_config import init_db
from infra.swagger import api

from infra.oauth.oauth_config import init_oauth

from controllers.chat_controller import chat_ns         # remains as before
from controllers.auth_controller import auth_ns
from controllers.order_controller import order_ns

load_dotenv()

def create_app():
    app = Flask(__name__, template_folder="../templates")
    app.url_map.strict_slashes = False

    @app.before_request
    def check_credits():
        if request.endpoint in ['files']:
            user = getattr(request, 'user', None)
            if user and user.freeCredits <= 0:
                return jsonify({"error": "You have no more credits left"}), 403

    app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'some-default-secret')
    app.secret_key = os.getenv('SECRET_KEY', 'change-this-secret')
    
    init_db()
    CORS(app, supports_credentials=True, resources={
        r"/api/*": {
            "origins": "http://147.93.111.242:3000",
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Length", "X-Kuma-Revision"],
            "methods": ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
        }
    })
    init_oauth(app)
    app.config.update(
        GITHUB_CLIENT_ID=os.getenv('GITHUB_CLIENT_ID'),
        GITHUB_CLIENT_SECRET=os.getenv('GITHUB_CLIENT_SECRET'),
        GOOGLE_CLIENT_ID=os.getenv('GOOGLE_CLIENT_ID'),
        GOOGLE_CLIENT_SECRET=os.getenv('GOOGLE_CLIENT_SECRET'),
        SECRET_KEY=os.getenv('JWT_SECRET')
    )
    
    @app.get('/')
    def home():
        return "Welcome to the Flask API!"
    
    api.init_app(app)
    api.add_namespace(auth_ns, path='/api/auth')
    api.add_namespace(chat_ns, path='/api/chat')
    api.add_namespace(order_ns, path='/api/order')
    
    return app
