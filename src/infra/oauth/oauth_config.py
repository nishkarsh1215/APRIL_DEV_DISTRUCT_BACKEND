from authlib.integrations.flask_client import OAuth
import os

oauth = OAuth()

def init_oauth(app):
    oauth.init_app(app)  # Initialize OAuth with Flask app

    # GitHub OAuth
    oauth.register(
        name='github',
        client_id=os.getenv("GITHUB_CLIENT_ID"),
        client_secret=os.getenv("GITHUB_CLIENT_SECRET"),
        access_token_url='https://github.com/login/oauth/access_token',
        authorize_url='https://github.com/login/oauth/authorize',
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'user:email'},
    )

    # Google OAuth
    oauth.register(
        name='google',
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        client_kwargs={
            'scope': 'openid email profile',
        },
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
    )
    
    return oauth