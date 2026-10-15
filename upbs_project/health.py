"""
Lightweight Health Check and Database Keep-Alive View for Render & Supabase.
Touches Supabase PostgreSQL to prevent inactivity pause, and serves as an external
ping target to prevent Render free-tier spin down.
"""
import logging
from django.http import JsonResponse
from django.db import connection
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@csrf_exempt
def health_check_view(request):
    """
    Lightweight health check endpoint.
    1. Executes a lightweight SQL query (SELECT 1) on the database.
       This resets the Supabase 7-day inactivity pause counter.
    2. Returns HTTP 200 JSON.
       External incoming HTTP requests to this endpoint reset Render's 15-minute inactivity idle timer.
    """
    db_status = "unknown"
    error_message = None

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row and row[0] == 1:
                db_status = "connected"
            else:
                db_status = "degraded"
    except Exception as exc:
        db_status = "error"
        error_message = str(exc)
        logger.error("Health check database probe failed: %s", exc)

    status_code = 200 if db_status == "connected" else 503

    response_data = {
        "status": "healthy" if status_code == 200 else "unhealthy",
        "service": "UPBS Campus Safety Command",
        "database": db_status,
        "timestamp": timezone.now().isoformat(),
    }
    if error_message:
        response_data["error"] = error_message

    return JsonResponse(response_data, status=status_code)
