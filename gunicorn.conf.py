# Gunicorn configuration for Render deployment (auto-loaded by gunicorn)
import os
import time
import threading
import logging

workers = 2
threads = 8
worker_class = "gthread"
timeout = 60
keepalive = 5

def _keepalive_worker():
    """Background daemon thread that runs keepalive pulses every 10 minutes."""
    time.sleep(45)  # Wait for workers to bind before starting pulses
    while True:
        try:
            from accounts.management.commands.keepalive import perform_keepalive_pulse
            res = perform_keepalive_pulse()
            logging.info("UPBS Keepalive: DB=%s HTTP=%s (%s)", res['db_ok'], res['http_status'], res['url_pinged'])
        except Exception as exc:
            logging.warning("UPBS Keepalive worker exception: %s", exc)
        time.sleep(600)  # 10 minutes (safely below Render 15min idle cutoff)

def when_ready(server):
    """Triggered once Gunicorn master process is fully initialized."""
    # Launch keepalive thread when on Render or when KEEPALIVE_ENABLED is true
    if os.environ.get('RENDER') or os.environ.get('KEEPALIVE_ENABLED', 'true').lower() in ('1', 'true', 't'):
        t = threading.Thread(target=_keepalive_worker, daemon=True, name="UPBS-KeepAlive-Daemon")
        t.start()
        server.log.info("Initialized UPBS Keep-Alive background thread (10m pulse interval).")


