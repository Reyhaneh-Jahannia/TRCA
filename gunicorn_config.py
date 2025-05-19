import os

port = int(os.environ.get("PORT", 10000))
bind = f"0.0.0.0:{port}"
workers = 1  # Reduce to 1 worker to save resources
timeout = 600  # Increase timeout to 10 minutes