# Rimo2.0 Backend

## Overview
This project is a Flask-based backend that provides:
- User authentication (custom login, registration, and OAuth with GitHub/Google)
- AI features (text understanding and computer vision)
- Persistent storage in MongoDB
- Automatic API documentation with Flask-RESTX

## Installation
1. Clone the repository and navigate to the project folder.
2. Ensure Python 3.10+ is installed.
3. Install dependencies:
   ```bash
   pip install -r src/requirements.txt
   ```
4. Provide environment variables provided in `.env.example` file
5. Run the application:
   ```bash
   python src/run.py
   ```

## Usage
- Check out the Swagger UI at /swagger/.

## Project Structure
```bash
src/
├── app/
│   └── __init__.py        # Creates and configures the Flask app
├── controllers/           # Routes (Flask-Restx resources)
├── helpers/               # Utility/helpers (JWT, email, etc.)
├── infra/
│   ├── db/                # Database configuration and models
│   ├── oauth/             # OAuth setup with GitHub & Google
│   └── swagger/           # API documentation initialization
└── run.py                 # Entry point
```

