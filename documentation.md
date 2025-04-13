
# Project Documentation

## Overview
This project is a Flask-based backend for an AI-powered chat and code editing service.

## Prerequisites
- Python 3.7+  
- MongoDB  
- (Optional) Virtual environment for Python  
- Environment variables set in a .env file or your system environment

## Environment Variables
- `MONGO_URI` – MongoDB connection string  
- `JWT_SECRET` – Secret key for JWT  
- `GOOGLE_API_KEY` – Key for Google Generative AI  
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` – For GitHub OAuth  
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` – For Google OAuth  
- `RESEND_API_KEY` – For sending emails via Resend

## Installation & Setup
1. Clone the repository.  
2. Navigate into the project directory.  
3. (Optional) Create and activate a virtual environment.  
4. Install dependencies:  
   ```
   pip install -r requirements.txt
   ```
5. Set up the .env file with the required environment variables.
6. Run the Flask server:
   ```
   python src/run.py
   ```
   The server should start on port 5000 (configurable via `PORT`).

## Project Structure
```
/
├─ src/
│  ├─ app/
│  │  └─ __init__.py          # Creates and configures the Flask app
│  ├─ controllers/
│  │  ├─ auth_controller.py   # Authentication routes
│  │  ├─ chat_controller.py   # Chat, code generation, and editor endpoints
│  │  └─ image_controller.py  # (Placeholder)
│  ├─ helpers/
│  │  ├─ auth_helper.py       # Helper functions for JWT token generation
│  │  ├─ email_helper.py      # Email sending helpers
│  │  └─ password_helper.py   # Password reset helper
│  ├─ infra/
│  │  ├─ db/
│  │  │  ├─ db_config.py      # MongoDB connection
│  │  │  └─ models.py         # Models for Chat, EditorMessage, User, ChatMessage
│  │  ├─ oauth/
│  │  │  └─ oauth_config.py   # OAuth configuration for GitHub/Google
│  │  └─ swagger/
│  │     └─ __init__.py       # API Swagger definitions
│  ├─ middlewares/
│  │  └─ auth_middleware.py   # Middleware for credit checks
│  └─ run.py                  # Entry point for the Flask server
└─ .env (git ignored)         # Holds environment variables
```

## Notable Endpoints (groups)
- `/api/auth/` – Handles user registration, login, logout, password reset, and email verification.  
- `/api/chat/` – Handles chat creation, sending messages, code generation, and listing chats.

### Authentication
1. POST `/api/auth/register` – Register a new user  
2. POST `/api/auth/login` – Log in with email/password  
3. GET `/api/auth/me` – Fetch current user info from JWT  
4. GET `/api/auth/logout` – Clear current user session  

### Chat
1. POST `/api/chat/create` – Create a new chat with an initial prompt  
2. POST `/api/chat/send` – Send a prompt to an existing chat  
3. POST `/api/chat/send-code` – Send a prompt to generate AI-powered code suggestions  
4. GET `/api/chat/history` – List recent chats for authenticated user  
5. DELETE `/api/chat/<chat_id>` – Delete a chat and all its messages  
6. GET `/api/chat/<chat_id>/messages` – Retrieve messages of a chat  
7. PATCH `/api/chat/<chat_id>/editor_message` – Update editor message code JSON

## Email & Verification
- EmailHelper uses Resend to send verification and password reset emails.  
- Make sure `RESEND_API_KEY` is set if using email functionality.

## OAuth
- `/api/auth/github` – GitHub OAuth flow  
- `/api/auth/google` – Google OAuth flow  

## Running the App
- Default: locally on port 5000 (configured in `run.py`).  
- Access the main routes under `http://localhost:5000/api/*`

## Tips
- Ensure that you have your `.env` file and dependencies installed.  
- For code generation, be sure to set `GOOGLE_API_KEY` so the Generative AI routes work.  
- Use Swagger docs at `http://localhost:5000/swagger/` to explore the API interactively.

