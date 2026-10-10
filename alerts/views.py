import json
import urllib.request
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from .models import PanicDevice, EmergencyAlert, Location, SecurityOfficer, AlertResponse, Notification


@login_required
def home_view(request):
    """
    Home Interface (Phase 3 Section 3.1):
    Features centralized pulsing panic button, 3-second abort window, GPS status, and emergency contacts.
    """
    return render(request, 'alerts/home.html')


@login_required
@csrf_protect
def trigger_alert_api(request):
    """
    API endpoint invoked after 3-second countdown window concludes.
    Creates EmergencyAlert, Location (1:1), PanicDevice linkage, and triggers Notification.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    alert_type = data.get('alert_type', EmergencyAlert.TYPE_STANDARD)
    lat_val = data.get('latitude', -28.742050)
    lng_val = data.get('longitude', 24.765100)
    accuracy_val = data.get('accuracy', 10.0)
    description = data.get('description', 'Main Campus Area').strip()

    # Rate limiting check: user cannot spam more than 3 active alerts within 5 minutes
    recent_alerts = EmergencyAlert.objects.filter(
        user=request.user,
        timestamp__gte=timezone.now() - timezone.timedelta(minutes=5)
    ).count()
    if recent_alerts >= 3:
        return JsonResponse({'error': 'Rate limit reached. Please call security directly.'}, status=429)

    # Find or associate client device
    device, _ = PanicDevice.objects.get_or_create(
        user=request.user,
        device_type='WEB_CLIENT',
        defaults={'device_identifier': f"WEB-{request.user.institutional_id}"}
    )

    alert = EmergencyAlert.objects.create(
        user=request.user,
        panic_device=device,
        status=EmergencyAlert.STATUS_SENT,
        alert_type=alert_type,
    )

    Location.objects.create(
        alert=alert,
        latitude=Decimal(str(lat_val)),
        longitude=Decimal(str(lng_val)),
        accuracy_meters=float(accuracy_val) if accuracy_val else None,
        description=description
    )

    # Multi-channel Notification Hub (Phase 3 Redundancy)
    Notification.objects.create(
        alert=alert,
        recipient="+27829991111", # Central security dispatch line
        channel=Notification.CHANNEL_SMS,
        message=f"CRITICAL ALERT #{alert.id}: {request.user.full_name} ({request.user.institutional_id}) triggered {alert.get_alert_type_display()} at {description}.",
        delivery_status=Notification.STATUS_DELIVERED
    )

    return JsonResponse({
        'success': True,
        'alert_id': alert.id,
        'status': alert.status,
        'redirect_url': '/dashboard/'
    })


@login_required
def user_dashboard_view(request):
    """
    User Dashboard (Phase 3 Section 3.1 & Iteration 3):
    Displays active alert tracking timeline and past history.
    """
    active_alert = EmergencyAlert.objects.filter(
        user=request.user
    ).exclude(status__in=[EmergencyAlert.STATUS_CANCELLED]).order_by('-timestamp').first()

    alerts_history = EmergencyAlert.objects.filter(
        user=request.user
    ).select_related('location').prefetch_related('feedbacks', 'responses__officer').order_by('-timestamp')

    return render(request, 'alerts/dashboard.html', {
        'active_alert': active_alert,
        'alerts_history': alerts_history
    })


@login_required
def security_dashboard_view(request):
    """
    Admin / Security Dashboard (Phase 3 Section 3.1):
    Live radar map, real-time alert polling queue, and officer dispatch controls.
    """
    if not (request.user.is_security or request.user.is_admin_user):
        return HttpResponseForbidden("Access restricted to Campus Security personnel.")

    return render(request, 'alerts/security_console.html')


@login_required
def api_live_alerts(request):
    """
    JSON stream/polling endpoint for Security Console.
    Returns all non-resolved/non-cancelled active alerts.
    """
    if not (request.user.is_security or request.user.is_admin_user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    alerts = EmergencyAlert.objects.filter(
        status__in=[EmergencyAlert.STATUS_SENT, EmergencyAlert.STATUS_RECEIVED, EmergencyAlert.STATUS_DISPATCHED]
    ).select_related('user', 'location').order_by('-timestamp')

    data = []
    for a in alerts:
        data.append({
            'id': a.id,
            'alert_type': a.get_alert_type_display(),
            'status': a.status,
            'timestamp_formatted': a.timestamp.strftime('%H:%M:%S'),
            'user_full_name': a.user.full_name,
            'institutional_id': a.user.institutional_id,
            'contact_number': a.user.contact_number,
            'location_description': a.location.description if hasattr(a, 'location') else "Campus Grounds",
            'latitude': float(a.location.latitude) if hasattr(a, 'location') else -28.742050,
            'longitude': float(a.location.longitude) if hasattr(a, 'location') else 24.765100,
        })

    return JsonResponse({'alerts': data})


@login_required
def api_alert_status(request, alert_id):
    """
    Endpoint for student dashboard timeline tracking (Iteration 3).
    """
    alert = get_object_or_404(EmergencyAlert, id=alert_id)
    if alert.user != request.user and not (request.user.is_security or request.user.is_admin_user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    return JsonResponse({
        'id': alert.id,
        'status': alert.status,
        'status_display': alert.get_status_display(),
        'updated_at': alert.updated_at.isoformat()
    })


@login_required
@csrf_protect
def api_update_alert_status(request, alert_id):
    """
    Updates emergency alert state machine:
    SENT -> RECEIVED -> DISPATCHED -> RESOLVED
    Associates responding security officer via AlertResponse (M:N).
    """
    if not (request.user.is_security or request.user.is_admin_user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    alert = get_object_or_404(EmergencyAlert, id=alert_id)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    new_status = body.get('status')
    notes = body.get('response_notes', '').strip()

    valid_statuses = [
        EmergencyAlert.STATUS_RECEIVED,
        EmergencyAlert.STATUS_DISPATCHED,
        EmergencyAlert.STATUS_RESOLVED,
        EmergencyAlert.STATUS_CANCELLED
    ]
    if new_status not in valid_statuses:
        return JsonResponse({'error': f'Invalid status: {new_status}'}, status=400)

    alert.status = new_status
    if new_status == EmergencyAlert.STATUS_RESOLVED:
        alert.resolved_at = timezone.now()
    alert.save()

    # Link SecurityOfficer profile
    officer = getattr(request.user, 'officer_profile', None)
    if not officer:
        officer, _ = SecurityOfficer.objects.get_or_create(
            user=request.user,
            defaults={
                'officer_name': request.user.full_name or request.user.username,
                'badge_number': f"OP-{request.user.id:04d}",
                'on_duty': True
            }
        )

    response_record, _ = AlertResponse.objects.get_or_create(
        alert=alert,
        officer=officer,
        defaults={'status': AlertResponse.STATUS_ASSIGNED}
    )

    if new_status == EmergencyAlert.STATUS_RECEIVED and not response_record.acknowledged_at:
        response_record.acknowledged_at = timezone.now()
    elif new_status == EmergencyAlert.STATUS_DISPATCHED:
        response_record.status = AlertResponse.STATUS_EN_ROUTE
    elif new_status == EmergencyAlert.STATUS_RESOLVED:
        response_record.status = AlertResponse.STATUS_RESOLVED
        response_record.resolved_at = timezone.now()

    if notes:
        response_record.response_notes = notes
    response_record.save()

    return JsonResponse({
        'success': True,
        'alert_id': alert.id,
        'new_status': alert.status
    })


def kimberley_map_tile(request, z, x, y):
    """
    Serves self-hosted Kimberley Campus GIS map tiles directly from static/tiles/kimberley/{z}/{x}/{y}.png.
    If a higher zoom tile (z=17..18) within Kimberley is requested, fetches and caches it server-side
    so the browser never encounters third-party API key prompts or 403 Referer blocks.
    """
    if z < 13 or z > 19:
        return HttpResponseNotFound("Zoom level outside Kimberley campus bounds.")

    local_tile = Path(settings.BASE_DIR) / 'static' / 'tiles' / 'kimberley' / str(z) / str(x) / f"{y}.png"
    if local_tile.exists():
        return HttpResponse(
            local_tile.read_bytes(),
            content_type='image/png',
            headers={'Cache-Control': 'public, max-age=604800, immutable'}
        )

    # Fallback server-side fetch for zoom 17-18 within Kimberley
    upstream_urls = [
        f"https://tile.openstreetmap.de/{z}/{x}/{y}.png",
        f"https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    ]
    for url in upstream_urls:
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'UPBS-Campus-Safety-Kimberley/1.0 (+https://youthalliance.co.za)',
                'Referer': 'https://youthalliance.co.za/'
            })
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = resp.read()
                if len(data) > 7500 or resp.status == 200:
                    try:
                        local_tile.parent.mkdir(parents=True, exist_ok=True)
                        local_tile.write_bytes(data)
                    except OSError:
                        pass
                    return HttpResponse(
                        data,
                        content_type='image/png',
                        headers={'Cache-Control': 'public, max-age=604800'}
                    )
        except Exception:
            continue

    return HttpResponseNotFound("Kimberley tile unavailable.")

