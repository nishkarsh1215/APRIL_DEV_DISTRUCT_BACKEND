import bcrypt
import jwt
import json
from datetime import datetime
from flask import url_for, current_app
from infra.db.models import User
from flask import make_response, request, redirect
from infra.oauth.oauth_config import oauth
from flask_restx import Namespace, Resource, fields
from authlib.integrations.flask_client import OAuthError
from helpers.auth_helper import generate_token, verify_token, token_required

from helpers.email_helper import send_verification_email, send_password_reset_email
from helpers.password_helper import generate_password_reset_token, verify_password_reset_token

auth_ns = Namespace('auth', description='Authentication operations')

# Request/Response Models
register_model = auth_ns.model('Register', {
    'email': fields.String(required=True, example="user@example.com"),
    'password': fields.String(required=True, example="password123"),
    'name': fields.String(example="John Doe")
})

login_model = auth_ns.model('Login', {
    'email': fields.String(required=True, example="user@example.com"),
    'password': fields.String(required=True, example="password123")
})

user_model = auth_ns.model('User', {
    'id': fields.String,  # changed to string
    'email': fields.String,
    'name': fields.String,
    'freeCredits': fields.Integer
})

password_reset_request_model = auth_ns.model('PasswordResetRequest', {
    'email': fields.String(required=True, example="user@example.com")
})

password_reset_model = auth_ns.model('PasswordReset', {
    'password': fields.String(required=True, example="newpassword123"),
    'confirm_password': fields.String(required=True, example="newpassword123")
})

user_token_model = auth_ns.model('UserToken', {
    'tokens': fields.Integer(example=5),
    'emailVerified': fields.Boolean
})

resend_verification_model = auth_ns.model('ResendVerificationRequest', {
    'email': fields.String(required=True, example="user@example.com")
})

@auth_ns.route('/tokens')
class UserTokens(Resource):
    @token_required
    @auth_ns.marshal_with(auth_ns.models['UserToken'])
    def get(self, user):
        """Get remaining tokens"""
        return user

@auth_ns.route('/register')
class Register(Resource):
    @auth_ns.expect(register_model)
    @auth_ns.response(201, 'User created')
    @auth_ns.response(400, 'Validation error')
    def post(self):
        """Register a new user"""
        data = auth_ns.payload
        
        if User.objects(email=data['email']).first():
            return {"error": "Email already exists"}, 400
        
        hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
        
        new_user = User(
            email=data['email'],
            password=hashed_pw.decode('utf-8'),
            name=data.get('name', ''),
            profilePicture=f"https://api.dicebear.com/9.x/lorelei/svg?seed={data.get('name', '')}",
            provider='email'
        )
        
        new_user.save()
        
        # Immediately send verification link after registration
        send_verification_email(new_user)
        
        token = generate_token(new_user.id)
        resp = make_response({
            "id": str(new_user.id),
            "email": new_user.email,
            "message": "Verification email sent"
        }, 201)
        resp.set_cookie("token", token) 
        return resp

@auth_ns.route('/login')
class Login(Resource):
    @auth_ns.doc(responses={
        200: 'Success (includes remaining credits)',
        401: 'Invalid credentials'
    })
    @auth_ns.expect(login_model)
    @auth_ns.response(200, 'Login successful')
    @auth_ns.response(401, 'Invalid credentials')
    def post(self):
        """User login"""
        data = auth_ns.payload
        user = User.objects(email=data['email']).first()
        
        if not user or not bcrypt.checkpw(
            data['password'].encode('utf-8'),
            user.password.encode('utf-8')
        ):
            return {"error": "Invalid credentials"}, 401
        
        token = generate_token(user.id)
        resp = make_response({
            "id": str(user.id),
            "email": user.email
        }, 200)
        # Return JSON instead of redirect and set CORS headers
        resp.set_cookie(
            "token",
            token,
            httponly=True,
        )
        resp.headers.add("Access-Control-Allow-Origin", "http://147.93.111.242:3000")
        resp.headers.add("Access-Control-Allow-Credentials", "true")
        resp.headers.add("Access-Control-Allow-Headers", "Content-Type, Authorization")
        resp.headers.add("Access-Control-Allow-Methods", "GET, POST, PATCH, PUT, DELETE, OPTIONS")
        return resp

@auth_ns.route('/me')
class CurrentUser(Resource):
    def get(self):
        token = request.cookies.get('token')
        user = verify_token(token)
        if not user:
            return {"error": "Unauthorized"}, 401
        data = {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "freeCredits": user.freeCredits,
            "provider": user.provider
        }
        if user.provider == "google":
            google_token_str = request.cookies.get("google_token")
            if google_token_str:
                import json
                try:
                    google_token = json.loads(google_token_str)
                    resp_google = oauth.google.get("userinfo", token=google_token)
                    if resp_google.ok:
                        data["google_user_info"] = resp_google.json()
                    else:
                        data["google_user_info"] = {
                            "error": "Unable to fetch Google user info",
                            "status": resp_google.status_code
                        }
                except Exception as e:
                    data["google_user_info"] = {"error": str(e)}
        elif user.provider == "github":
            data["github_user_info"] = {"githubId": user.githubId}
        if not user.emailVerified:
            data["verificationReminder"] = "Please verify your email."
        return data, 200
    
# OAuth with GitHub
@auth_ns.route('/github')
class GitHubLogin(Resource):
    def get(self):
        """Initiate GitHub OAuth flow"""
        redirect_uri = url_for('auth_git_hub_callback', _external=True)
        return oauth.github.authorize_redirect(redirect_uri)

@auth_ns.route('/github/callback')
class GitHubCallback(Resource):
    def get(self):
        try:
            # Retrieve the access token from GitHub
            token = oauth.github.authorize_access_token()
            # Use the token for subsequent API calls
            user_data = oauth.github.get('user', token=token).json()
            emails = oauth.github.get('user/emails', token=token).json()
            
            github_id_val = user_data.get('id')
            email = next((e['email'] for e in emails if e.get('primary')), None)
            
            if github_id_val:
                user = User.objects(provider='github', githubId=str(github_id_val)).first()
            else:
                user = User.objects(provider='github', githubId=None).first()
            
            if not user:
                if github_id_val:
                    user = User(
                        name=user_data.get('name', ''),
                        email=email,
                        provider='github',
                        githubId=str(github_id_val),
                        profilePicture=f"https://api.dicebear.com/9.x/lorelei/svg?seed={user_data.get('name', '')}",
                        emailVerified=True
                    ).save()
                else:
                    user = User(
                        name=user_data.get('name', ''),
                        email=email,
                        provider='github',
                        profilePicture=f"https://api.dicebear.com/9.x/lorelei/svg?seed={user_data.get('name', '')}",
                        emailVerified=True
                    ).save()
            
            jwt_token = generate_token(user.id)
            resp = make_response({
                "id": str(user.id),
                "email": user.email,
                "token": jwt_token
            }, 200)
            resp = redirect('http://147.93.111.242:3000')
            resp.set_cookie("token", jwt_token, httponly=True)
            return resp
        except OAuthError as e:
            return {"error": str(e)}, 400

# OAuth with Google
@auth_ns.route('/google')
class GoogleLogin(Resource):
    def get(self):
        """Initiate Google OAuth flow"""
        redirect_uri = url_for('auth_google_callback', _external=True)
        return oauth.google.authorize_redirect(redirect_uri)

@auth_ns.route('/google/callback')
class GoogleCallback(Resource):
    def get(self):
        try:
            token = oauth.google.authorize_access_token()
            user_data = token.get('userinfo')
            
            sub_value = user_data.get('sub')
            user = User.objects(
                provider='google',
                googleId=sub_value
            ).first()
            
            if not user:
                if sub_value:
                    # Only set googleId if sub is present
                    user = User(
                        name=user_data.get('name', ''),
                        email=user_data['email'],
                        provider='google',
                        profilePicture=f"https://api.dicebear.com/9.x/lorelei/svg?seed={user_data.get('name', '')}",
                        googleId=str(sub_value),
                        emailVerified=True
                    ).save()
                else:
                    # If sub is missing, skip googleId assignment
                    user = User(
                        name=user_data.get('name', ''),
                        email=user_data['email'],
                        profilePicture=f"https://api.dicebear.com/9.x/lorelei/svg?seed={user_data.get('name', '')}",
                        provider='google',
                        emailVerified=True
                    ).save()
            
            jwt_token = generate_token(user.id)
            resp = make_response({
                "id": str(user.id),
                "email": user.email,
                "token": jwt_token
            }, 200)
            resp = redirect('https://devdistruct.com')
            resp.set_cookie("token", jwt_token, httponly=True)
            resp.set_cookie("google_token", json.dumps(token), httponly=True)
            return resp
            
        except OAuthError as e:
            return {"error": str(e)}, 400

@auth_ns.route('/verify-email/<token>')
class VerifyEmail(Resource):
    def get(self, token):
        """Verify the email if token is valid and unexpired."""
        try:
            payload = jwt.decode(
                token,
                current_app.config['JWT_SECRET'],
                algorithms=['HS256']
            )
            if payload.get('purpose') != 'emailVerification':
                return {"error": "Invalid token purpose"}, 400

            user = User.objects(id=payload['sub']).first()
            if not user:
                return {"error": "No user found"}, 404
            if user.emailVerified:
                return {"message": "Email already verified"}, 200

            # Mark the user as verified
            user.emailVerified = True
            user.save()
            return {"message": "Email verified successfully"}, 200
            
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return {"error": "Verification link has expired or is invalid"}, 400

@auth_ns.route('/logout')
class Logout(Resource):
    def get(self):
        resp = make_response({"message": "Logged out"}, 200)
        resp.set_cookie("token", "", expires=0)
        resp.set_cookie("google_token", "", expires=0)
        return resp  

@auth_ns.route('/request-password-reset')
class RequestPasswordReset(Resource):
    @auth_ns.expect(password_reset_request_model)
    @auth_ns.response(200, 'Reset email sent if user exists')
    def post(self):
        """Request password reset email"""
        data = request.get_json()
        user = User.objects(email=data['email']).first()
        
        if user:
            token = generate_password_reset_token(user.id)
            send_password_reset_email(user.email, token)
        
        return {"message": "A reset link has been sent"}, 200

@auth_ns.route('/reset-password/<string:token>')
class ResetPassword(Resource):
    @auth_ns.expect(password_reset_model)
    @auth_ns.response(200, 'Password updated successfully')
    @auth_ns.response(400, 'Invalid token or passwords mismatch')
    @auth_ns.response(404, 'User not found')
    def post(self, token):
        """Reset password with validation token"""
        user_id = verify_password_reset_token(token)
        if not user_id:
            return {"error": "Invalid or expired token"}, 400
        
        data = request.get_json()
        if data['password'] != data['confirm_password']:
            return {"error": "Passwords do not match"}, 400
        
        user = User.objects(id=user_id).first()
        if not user:
            return {"error": "User not found"}, 404
        
        hashed_pw = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
        user.update(
            password=hashed_pw.decode('utf-8'),
            updated_at=datetime.now()
        )
        
        return {"message": "Password updated successfully"}, 200

@auth_ns.route('/resend-verification')
class ResendVerification(Resource):
    @auth_ns.expect(resend_verification_model, validate=True)
    def post(self):
        data = request.get_json()
        email = data.get('email')
        user = User.objects(email=email).first()
        if not user:
            return {"error": "User not found"}, 404
        if user.emailVerified:
            return {"message": "Email already verified."}, 200
        from helpers.email_helper import send_verification_email
        send_verification_email(user)
        return {"message": "Verification email sent."}, 200