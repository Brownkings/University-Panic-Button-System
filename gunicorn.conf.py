# Gunicorn configuration for Render deployment (auto-loaded by gunicorn)
workers = 2
threads = 8
worker_class = "gthread"
timeout = 60
keepalive = 5
