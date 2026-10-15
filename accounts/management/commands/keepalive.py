"""
Management command to keep Render web services and Supabase PostgreSQL active.
Pings the external public HTTP health endpoint and executes database heartbeat queries.
"""
import time
import os
import logging
import requests
from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)


def perform_keepalive_pulse(target_url=None):
    """
    Executes a single keepalive pulse:
    1. Direct DB query (Supabase activity pulse)
    2. External HTTP GET to healthz endpoint (Render router traffic pulse)
    """
    result = {
        'db_ok': False,
        'http_ok': False,
        'url_pinged': None,
        'http_status': None,
    }

    # 1. Supabase / Database pulse
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            result['db_ok'] = bool(row and row[0] == 1)
    except Exception as exc:
        logger.error("Keepalive DB pulse failed: %s", exc)

    # 2. Render HTTP pulse (must be public URL through Render edge router)
    url = target_url or os.environ.get('KEEPALIVE_URL')
    if not url:
        render_ext = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
        if render_ext:
            url = f"https://{render_ext}/healthz/"
        else:
            url = "https://youthalliance.co.za/healthz/"

    result['url_pinged'] = url
    try:
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'UPBS-KeepAlive-Pulse/1.0'})
        result['http_status'] = resp.status_code
        result['http_ok'] = (resp.status_code == 200)
    except Exception as exc:
        logger.warning("Keepalive HTTP pulse to %s failed: %s", url, exc)

    return result


class Command(BaseCommand):
    help = "Runs a continuous keepalive daemon to prevent Render spin-down and Supabase pausing"

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=600,
            help='Interval in seconds between pulses (default: 600s / 10min)'
        )
        parser.add_argument(
            '--url',
            type=str,
            default=None,
            help='Target public URL to ping (e.g. https://youthalliance.co.za/healthz/)'
        )
        parser.add_argument(
            '--once',
            action='store_true',
            help='Run a single pulse and exit'
        )

    def handle(self, *args, **options):
        interval = options['interval']
        target_url = options['url']
        once = options['once']

        self.stdout.write(self.style.SUCCESS(
            f"Starting UPBS Keep-Alive Pulse (Interval: {interval}s)..."
        ))

        while True:
            res = perform_keepalive_pulse(target_url)
            status_str = f"DB: {'OK' if res['db_ok'] else 'FAIL'} | HTTP ({res['url_pinged']}): {res['http_status']}"
            if res['db_ok'] and res['http_ok']:
                self.stdout.write(self.style.SUCCESS(f"✓ Pulse successful: {status_str}"))
            else:
                self.stdout.write(self.style.WARNING(f"⚠ Pulse warning: {status_str}"))

            if once:
                break

            time.sleep(interval)
