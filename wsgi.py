import os
from app import app

if __name__ == "__main__":
    # This is only used when running locally
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))