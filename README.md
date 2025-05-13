# DevDistruct Backend

Flask-based backend service for the DevDistruct application.

## Setup

### Prerequisites
- Python 3.8+
- pip (Python package manager)

### Installation

1. Clone the repository
2. Set up the environment using the setup script:

```bash
# Make the setup script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

Or manually set up your environment:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

3. Create a `.env` file in the project root with the following variables:
```
JWT_SECRET=your_jwt_secret
SECRET_KEY=your_secret_key
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
PORT=5000
```

## Running the Application

```bash
# Activate virtual environment (if not already activated)
source venv/bin/activate

# Run the application
python src/run.py
```

The server will start at http://localhost:5000

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

