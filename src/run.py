from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    PORT = os.getenv("PORT", 5000)
    app.run(host='0.0.0.0', port=PORT, debug=True)
    app.logger.info(f"Server Running on port http://localhost:{PORT}")