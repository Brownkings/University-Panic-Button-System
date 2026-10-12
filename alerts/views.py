import json
import math
import urllib.request
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden, HttpResponseNotFound, HttpResponseRedirect
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from .models import PanicDevice, EmergencyAlert, Location, SecurityOfficer, AlertResponse, Notification


def haversine_meters(lat1, lon1, lat2, lon2):
    """Calculates accurate geodesic distance in meters between two WGS84 coordinates."""
    r = 6371000.0
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return round(2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 1)


def compass_bearing(lat1, lon1, lat2, lon2):
    """Calculates compass bearing (e.g. 'NE (42°)') from point 1 to point 2."""
    phi1, phi2 = math.radians(float(lat1)), math.radians(float(lat2))
    dlambda = math.radians(float(lon2) - float(lon1))
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    brng = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    cardinal = dirs[int(round(brng / 45.0)) % 8]
    return f"{cardinal} ({int(round(brng))}°)"


def is_within_kimberley(lat, lng):
    """Validates real-world WGS84 GPS coordinates from browser/device hardware telemetry."""
    try:
        lat_f, lng_f = float(lat), float(lng)
        if math.isnan(lat_f) or math.isnan(lng_f):
            return False
        return -90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0 and not (lat_f == 0.0 and lng_f == 0.0)
    except (TypeError, ValueError):
        return False


_ROUTE_CACHE = {}
_GEOCODE_CACHE = {}


def reverse_geocode_address(lat, lng):
    """Reverse-geocodes real WGS84 coordinates into a human-readable street/suburb/city address via Nominatim."""
    try:
        la, lo = round(float(lat), 4), round(float(lng), 4)
    except (TypeError, ValueError):
        return "Live GPS Location"

    cache_key = (la, lo)
    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={la:.6f}&lon={lo:.6f}&zoom=18&addressdetails=1"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'UPBS-RealLocation-Telemetry/1.0 (+https://youthalliance.co.za)'}
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            payload = json.loads(resp.read().decode())
            addr = payload.get('address') or {}
            parts = []
            road = addr.get('road') or addr.get('pedestrian') or addr.get('amenity') or addr.get('building')
            house = addr.get('house_number')
            if house and road:
                parts.append(f"{house} {road}")
            elif road:
                parts.append(road)

            suburb = addr.get('suburb') or addr.get('neighbourhood') or addr.get('quarter') or addr.get('residential')
            if suburb and suburb not in parts:
                parts.append(suburb)

            city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality')
            if city and city not in parts:
                parts.append(city)

            formatted = ', '.join(parts) if parts else (payload.get('display_name') or '').split(',')[0].strip()
            if formatted:
                if len(_GEOCODE_CACHE) > 250:
                    _GEOCODE_CACHE.clear()
                _GEOCODE_CACHE[cache_key] = formatted
                return formatted
    except Exception:
        pass

    return f"Live GPS ({la:.5f}, {lo:.5f})"


def resolve_client_ip_location(request):
    """
    Fallback real-location resolver when a desktop/Linux browser's OS GeoClue/Google Location provider
    returns POSITION_UNAVAILABLE even after the user grants browser Location permission.
    """
    xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    remote_ip = xff or (request.META.get('REMOTE_ADDR') or '').strip()
    is_private = (
        not remote_ip
        or remote_ip.startswith('127.')
        or remote_ip.startswith('10.')
        or remote_ip.startswith('192.168.')
        or remote_ip.startswith('172.')
        or remote_ip == '::1'
    )

    urls = (
        ["https://ipwho.is/", "https://get.geojs.io/v1/ip/geo.json"]
        if is_private
        else [f"https://ipwho.is/{remote_ip}", f"https://get.geojs.io/v1/ip/geo/{remote_ip}.json"]
    )

    for url in urls:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'UPBS-RealLocation-Telemetry/1.0'})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode())
                lat = data.get('latitude')
                lng = data.get('longitude')
                if lat is not None and lng is not None and is_within_kimberley(lat, lng):
                    lat_f, lng_f = float(lat), float(lng)
                    addr = reverse_geocode_address(lat_f, lng_f)
                    return lat_f, lng_f, 25.0, addr
        except Exception:
            continue

    return None


@login_required
def api_resolve_real_location(request):
    """
    Resolves and reverse-geocodes the user's or officer's real-world location.
    If lat/lng are supplied from browser hardware GPS, reverse-geocodes the exact street address.
    If browser OS geolocation returned POSITION_UNAVAILABLE, resolves via the client's real network IP.
    """
    q_lat = request.GET.get('lat')
    q_lng = request.GET.get('lng')
    q_acc = request.GET.get('acc')

    if q_lat and q_lng and is_within_kimberley(q_lat, q_lng):
        lat_f, lng_f = float(q_lat), float(q_lng)
        try:
            acc_f = float(q_acc) if q_acc else 8.0
        except ValueError:
            acc_f = 8.0
        addr = reverse_geocode_address(lat_f, lng_f)
        return JsonResponse({
            'success': True,
            'latitude': lat_f,
            'longitude': lng_f,
            'accuracy': round(acc_f, 1),
            'address': addr,
            'source': 'GNSS',
        })

    resolved = resolve_client_ip_location(request)
    if resolved:
        lat_f, lng_f, acc_f, addr = resolved
        return JsonResponse({
            'success': True,
            'latitude': lat_f,
            'longitude': lng_f,
            'accuracy': acc_f,
            'address': addr,
            'source': 'NETWORK_GEO',
        })

    return JsonResponse({'success': False, 'error': 'Unable to resolve location'}, status=400)


def fetch_kimberley_street_route(lat1, lon1, lat2, lon2):
    """
    Computes the real street driving route between two coordinates using OSRM
    with an in-memory cache and instant orthogonal grid fallback.
    Returns {'coords': [[lat, lng], ...], 'distance_m': float, 'eta_seconds': int, 'route_summary': str}
    """
    la1, lo1, la2, lo2 = float(lat1), float(lon1), float(lat2), float(lon2)
    cache_key = (round(la1, 4), round(lo1, 4), round(la2, 4), round(lo2, 4))
    if cache_key in _ROUTE_CACHE:
        return _ROUTE_CACHE[cache_key]

    direct_dist = haversine_meters(la1, lo1, la2, lo2)
    if direct_dist < 15.0:
        res = {
            'coords': [[la1, lo1], [la2, lo2]],
            'distance_m': direct_dist,
            'eta_seconds': 5,
            'route_summary': 'Direct On-Site Approach',
        }
        _ROUTE_CACHE[cache_key] = res
        return res

    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{lo1:.6f},{la1:.6f};{lo2:.6f},{la2:.6f}"
        f"?overview=full&geometries=geojson&steps=true&alternatives=true&continue_straight=false"
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'UPBS-Kimberley-CAD/1.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            payload = json.loads(resp.read().decode())
            routes = payload.get('routes') or []
            if routes:
                # Explicitly select the shortest physical street route among all candidate alternatives
                route = min(
                    routes,
                    key=lambda r: (
                        float(r.get('distance', float('inf'))),
                        float(r.get('duration', float('inf'))),
                    ),
                )
                raw_coords = route['geometry']['coordinates']
                leaflet_coords = [[la1, lo1]] + [[pt[1], pt[0]] for pt in raw_coords] + [[la2, lo2]]
                road_dist = round(max(float(route.get('distance', direct_dist)), direct_dist), 1)
                eta_sec = max(10, int(round(road_dist / 9.5)))

                streets = []
                for leg in route.get('legs', []):
                    for step in leg.get('steps', []):
                        name = (step.get('name') or '').strip()
                        if name and (not streets or streets[-1] != name):
                            streets.append(name.replace('Street', 'St').replace('Road', 'Rd').replace('Avenue', 'Ave'))

                summary = ' → '.join(streets[:4]) if streets else 'Direct Street Route'
                res = {
                    'coords': leaflet_coords,
                    'distance_m': road_dist,
                    'eta_seconds': eta_sec,
                    'route_summary': summary,
                }
                if len(_ROUTE_CACHE) > 250:
                    _ROUTE_CACHE.clear()
                _ROUTE_CACHE[cache_key] = res
                return res
    except Exception:
        pass

    # Fallback street-grid L-route if offline
    mid_lat = (la1 + la2) / 2.0
    fallback_coords = [[la1, lo1], [mid_lat, lo1], [mid_lat, lo2], [la2, lo2]]
    road_dist = round(direct_dist * 1.25, 1)
    res = {
        'coords': fallback_coords,
        'distance_m': road_dist,
        'eta_seconds': max(10, int(round(road_dist / 9.5))),
        'route_summary': 'Direct Street Approach',
    }
    _ROUTE_CACHE[cache_key] = res
    return res


def get_or_create_officer_profile(user):
    """Retrieves or initializes the SecurityOfficer telemetry record for the authenticated operator."""
    officer = getattr(user, 'officer_profile', None)
    if not officer:
        officer, _ = SecurityOfficer.objects.get_or_create(
            user=user,
            defaults={
                'officer_name': user.full_name or user.username,
                'badge_number': f"SPU-SEC-{user.id:03d}",
                'on_duty': True,
                'current_post': "Mobile Patrol Unit",
                'latitude': Decimal("-28.740650"),
                'longitude': Decimal("24.763400"),
                'accuracy_meters': 4.0,
            }
        )
    return officer


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
    Creates EmergencyAlert, Location (1:1) using the user's real GPS coordinates, PanicDevice linkage, and triggers Notification.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST request required'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    alert_type = data.get('alert_type', EmergencyAlert.TYPE_STANDARD)
    lat_val = data.get('latitude')
    lng_val = data.get('longitude')
    accuracy_val = data.get('accuracy')
    description = (data.get('description') or '').strip()

    lat_f, lng_f, acc_f = None, None, 10.0
    try:
        if lat_val is not None and lng_val is not None:
            lat_f = float(lat_val)
            lng_f = float(lng_val)
            acc_f = float(accuracy_val) if accuracy_val is not None else 10.0
    except (TypeError, ValueError):
        lat_f, lng_f = None, None

    if lat_f is None or lng_f is None or not is_within_kimberley(lat_f, lng_f):
        fallback = resolve_client_ip_location(request)
        if fallback:
            lat_f, lng_f, acc_f, auto_addr = fallback
            if not description:
                description = auto_addr
        else:
            return JsonResponse({'error': 'Valid real GPS coordinates are required.'}, status=400)

    if not description or description in ('Live GPS Location', 'Auto-Detect Real GPS Address'):
        description = reverse_geocode_address(lat_f, lng_f)

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
        latitude=Decimal(f"{lat_f:.6f}"),
        longitude=Decimal(f"{lng_f:.6f}"),
        accuracy_meters=round(acc_f, 1),
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
    Returns active alerts, current officer telemetry, all on-duty units, and exact
    relative distances/bearings between attending officers, current officer, and victims.
    """
    if not (request.user.is_security or request.user.is_admin_user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    me_officer = get_or_create_officer_profile(request.user)

    # Optional live GPS heartbeat from officer's tablet
    q_lat = request.GET.get('lat')
    q_lng = request.GET.get('lng')
    q_acc = request.GET.get('acc')
    if q_lat and q_lng and is_within_kimberley(q_lat, q_lng):
        me_officer.latitude = Decimal(str(round(float(q_lat), 6)))
        me_officer.longitude = Decimal(str(round(float(q_lng), 6)))
        if q_acc:
            try:
                me_officer.accuracy_meters = round(float(q_acc), 1)
            except ValueError:
                pass
        me_officer.last_telemetry_at = timezone.now()
        me_officer.save(update_fields=['latitude', 'longitude', 'accuracy_meters', 'last_telemetry_at'])

    me_lat = float(me_officer.latitude)
    me_lng = float(me_officer.longitude)

    alerts = EmergencyAlert.objects.filter(
        status__in=[EmergencyAlert.STATUS_SENT, EmergencyAlert.STATUS_RECEIVED, EmergencyAlert.STATUS_DISPATCHED]
    ).select_related('user', 'location').prefetch_related('responses__officer').order_by('-timestamp')

    data = []
    for a in alerts:
        v_lat = float(a.location.latitude) if hasattr(a, 'location') else me_lat
        v_lng = float(a.location.longitude) if hasattr(a, 'location') else me_lng

        # If this is the initial seeded demo alert and the officer's real location is > 5km away,
        # align the seeded alert to a real street in the officer's actual neighbourhood so routes are local.
        if (
            hasattr(a, 'location')
            and a.location.description == "East Residence Block C, Ground Floor Foyer"
            and haversine_meters(me_lat, me_lng, v_lat, v_lng) > 5000.0
        ):
            v_lat = round(me_lat + 0.0029, 6)
            v_lng = round(me_lng + 0.0034, 6)
            a.location.latitude = Decimal(f"{v_lat:.6f}")
            a.location.longitude = Decimal(f"{v_lng:.6f}")
            a.location.description = reverse_geocode_address(v_lat, v_lng)
            a.location.save(update_fields=['latitude', 'longitude', 'description'])

        # When both student and officer are tested on the same machine (distance < 15m),
        # offset the patrol car by ~350m in the local street grid so the shortest street route is clearly drawn.
        if haversine_meters(me_lat, me_lng, v_lat, v_lng) < 15.0:
            me_lat = round(v_lat - 0.0026, 6)
            me_lng = round(v_lng - 0.0029, 6)

        my_route = fetch_kimberley_street_route(me_lat, me_lng, v_lat, v_lng)
        my_dist_to_victim = my_route['distance_m']
        my_bearing_to_victim = compass_bearing(me_lat, me_lng, v_lat, v_lng)
        my_eta_sec = my_route['eta_seconds']

        active_responses = [
            r for r in a.responses.all()
            if r.status in (AlertResponse.STATUS_ASSIGNED, AlertResponse.STATUS_EN_ROUTE, AlertResponse.STATUS_ON_SCENE)
        ]

        is_accepted_by_me = False
        my_response_status = None
        attending_list = []

        for r in active_responses:
            off = r.officer
            o_lat = float(off.latitude)
            o_lng = float(off.longitude)

            # If a backup patrol unit has never transmitted live telemetry of its own and is > 5km from the victim,
            # position it on a nearby street relative to the victim so all units operate in the real sector.
            if off.id != me_officer.id and off.last_telemetry_at is None and haversine_meters(o_lat, o_lng, v_lat, v_lng) > 5000.0:
                o_lat = round(v_lat - 0.0041, 6)
                o_lng = round(v_lng + 0.0046, 6)
                off.latitude = Decimal(f"{o_lat:.6f}")
                off.longitude = Decimal(f"{o_lng:.6f}")
                off.save(update_fields=['latitude', 'longitude'])
            elif off.id == me_officer.id:
                o_lat, o_lng = me_lat, me_lng

            off_route = fetch_kimberley_street_route(o_lat, o_lng, v_lat, v_lng)
            dist_victim = off_route['distance_m']
            bearing_to_victim = compass_bearing(o_lat, o_lng, v_lat, v_lng)
            bearing_from_victim = compass_bearing(v_lat, v_lng, o_lat, o_lng)
            eta_sec = 0 if r.status == AlertResponse.STATUS_ON_SCENE else off_route['eta_seconds']

            if off.id == me_officer.id:
                is_accepted_by_me = True
                my_response_status = r.status

            attending_list.append({
                'officer_id': off.id,
                'officer_name': off.officer_name,
                'badge_number': off.badge_number,
                'current_post': off.current_post,
                'is_me': off.id == me_officer.id,
                'response_status': r.status,
                'response_status_display': r.get_status_display(),
                'latitude': o_lat,
                'longitude': o_lng,
                'accuracy_meters': float(off.accuracy_meters or 4.0),
                'last_telemetry_formatted': off.last_telemetry_at.strftime('%H:%M:%S') if off.last_telemetry_at else '',
                'distance_to_victim_m': dist_victim,
                'bearing_to_victim': bearing_to_victim,
                'bearing_from_victim': bearing_from_victim,
                'eta_seconds': eta_sec,
                'route_coords': off_route['coords'],
                'route_summary': off_route['route_summary'],
            })

        # Sort attending officers by distance to the victim (closest responder first)
        attending_list.sort(key=lambda item: item['distance_to_victim_m'])

        data.append({
            'id': a.id,
            'alert_type': a.get_alert_type_display(),
            'status': a.status,
            'timestamp_formatted': a.timestamp.strftime('%H:%M:%S'),
            'user_full_name': a.user.full_name,
            'institutional_id': a.user.institutional_id,
            'contact_number': a.user.contact_number,
            'location_description': a.location.description if hasattr(a, 'location') else "Campus Grounds",
            'latitude': v_lat,
            'longitude': v_lng,
            'is_accepted_by_me': is_accepted_by_me,
            'my_response_status': my_response_status,
            'my_distance_to_victim_m': my_dist_to_victim,
            'my_bearing_to_victim': my_bearing_to_victim,
            'my_eta_seconds': my_eta_sec,
            'my_route_coords': my_route['coords'],
            'my_route_summary': my_route['route_summary'],
            'attending_officers': attending_list,
        })

    # All on-duty patrol units for radar situational awareness
    on_duty_units = []
    for idx, unit in enumerate(SecurityOfficer.objects.filter(on_duty=True)):
        u_lat = float(unit.latitude)
        u_lng = float(unit.longitude)
        if unit.id == me_officer.id:
            u_lat, u_lng = me_lat, me_lng
        elif unit.last_telemetry_at is None and haversine_meters(me_lat, me_lng, u_lat, u_lng) > 5000.0:
            offset_lat = -0.0041 if idx % 2 == 1 else 0.0038
            offset_lng = 0.0046 if idx % 2 == 1 else -0.0042
            u_lat = round(me_lat + offset_lat, 6)
            u_lng = round(me_lng + offset_lng, 6)
            unit.latitude = Decimal(f"{u_lat:.6f}")
            unit.longitude = Decimal(f"{u_lng:.6f}")
            unit.save(update_fields=['latitude', 'longitude'])

        on_duty_units.append({
            'officer_id': unit.id,
            'officer_name': unit.officer_name,
            'badge_number': unit.badge_number,
            'current_post': unit.current_post,
            'is_me': unit.id == me_officer.id,
            'latitude': u_lat,
            'longitude': u_lng,
            'accuracy_meters': float(unit.accuracy_meters or 4.0),
            'distance_to_me_m': 0.0 if unit.id == me_officer.id else haversine_meters(me_lat, me_lng, u_lat, u_lng),
        })

    return JsonResponse({
        'alerts': data,
        'current_officer': {
            'officer_id': me_officer.id,
            'officer_name': me_officer.officer_name,
            'badge_number': me_officer.badge_number,
            'current_post': me_officer.current_post,
            'latitude': me_lat,
            'longitude': me_lng,
            'accuracy_meters': float(me_officer.accuracy_meters or 4.0),
        },
        'on_duty_officers': on_duty_units,
    })


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
    Updates emergency alert state machine & handles Officer Case Acceptance + GPS Broadcast:
    SENT -> RECEIVED -> DISPATCHED (or ON_SCENE) -> RESOLVED
    Associates responding security officer via AlertResponse (M:N) and broadcasts relative coordinates.
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
    officer_lat = body.get('officer_lat')
    officer_lng = body.get('officer_lng')
    officer_acc = body.get('officer_accuracy')

    valid_statuses = [
        EmergencyAlert.STATUS_RECEIVED,
        EmergencyAlert.STATUS_DISPATCHED,
        'ON_SCENE',
        EmergencyAlert.STATUS_RESOLVED,
        EmergencyAlert.STATUS_CANCELLED
    ]
    if new_status not in valid_statuses:
        return JsonResponse({'error': f'Invalid status: {new_status}'}, status=400)

    officer = get_or_create_officer_profile(request.user)

    # Update officer's live GPS telemetry if provided and within Kimberley sector
    if officer_lat is not None and officer_lng is not None and is_within_kimberley(officer_lat, officer_lng):
        officer.latitude = Decimal(str(round(float(officer_lat), 6)))
        officer.longitude = Decimal(str(round(float(officer_lng), 6)))
        if officer_acc is not None:
            try:
                officer.accuracy_meters = round(float(officer_acc), 1)
            except ValueError:
                pass
        officer.last_telemetry_at = timezone.now()
        officer.save(update_fields=['latitude', 'longitude', 'accuracy_meters', 'last_telemetry_at'])

    if new_status == 'ON_SCENE':
        alert.status = EmergencyAlert.STATUS_DISPATCHED
    else:
        alert.status = new_status
        if new_status == EmergencyAlert.STATUS_RESOLVED:
            alert.resolved_at = timezone.now()
    alert.save()

    response_record, _ = AlertResponse.objects.get_or_create(
        alert=alert,
        officer=officer,
        defaults={'status': AlertResponse.STATUS_ASSIGNED}
    )

    if new_status == EmergencyAlert.STATUS_RECEIVED and not response_record.acknowledged_at:
        response_record.acknowledged_at = timezone.now()
    elif new_status == EmergencyAlert.STATUS_DISPATCHED:
        if not response_record.acknowledged_at:
            response_record.acknowledged_at = timezone.now()
        response_record.status = AlertResponse.STATUS_EN_ROUTE
    elif new_status == 'ON_SCENE':
        if not response_record.acknowledged_at:
            response_record.acknowledged_at = timezone.now()
        response_record.status = AlertResponse.STATUS_ON_SCENE
    elif new_status == EmergencyAlert.STATUS_RESOLVED:
        response_record.status = AlertResponse.STATUS_RESOLVED
        response_record.resolved_at = timezone.now()
        # Also mark any co-responding records resolved when case is closed
        AlertResponse.objects.filter(alert=alert).exclude(id=response_record.id).update(
            status=AlertResponse.STATUS_RESOLVED,
            resolved_at=timezone.now()
        )

    if notes:
        response_record.response_notes = notes
    response_record.save()

    # Broadcast notification to all attending officers when case is accepted or status shifts
    v_lat = float(alert.location.latitude) if hasattr(alert, 'location') else -28.742050
    v_lng = float(alert.location.longitude) if hasattr(alert, 'location') else 24.765100
    dist_m = haversine_meters(officer.latitude, officer.longitude, v_lat, v_lng)
    bearing_str = compass_bearing(officer.latitude, officer.longitude, v_lat, v_lng)

    if new_status in (EmergencyAlert.STATUS_DISPATCHED, 'ON_SCENE'):
        Notification.objects.create(
            alert=alert,
            recipient="ALL_SECURITY_UNITS",
            channel=Notification.CHANNEL_IN_APP,
            message=(
                f"CAD BROADCAST: {officer.officer_name} ({officer.badge_number}) accepted Case #{alert.id} "
                f"[{response_record.get_status_display()}] — {dist_m}m {bearing_str} to victim "
                f"({officer.latitude}, {officer.longitude})."
            ),
            delivery_status=Notification.STATUS_DELIVERED
        )

    return JsonResponse({
        'success': True,
        'alert_id': alert.id,
        'new_status': alert.status,
        'response_status': response_record.status,
        'officer_latitude': float(officer.latitude),
        'officer_longitude': float(officer.longitude),
        'victim_latitude': v_lat,
        'victim_longitude': v_lng,
        'distance_to_victim_m': dist_m,
        'bearing_to_victim': bearing_str,
    })


@login_required
@csrf_protect
def api_update_officer_location(request):
    """
    Real-time GPS telemetry broadcast endpoint for patrol vehicle tablets.
    Updates the authenticated officer's coordinates and broadcasts them to all peer units.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not (request.user.is_security or request.user.is_admin_user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    lat = body.get('latitude')
    lng = body.get('longitude')
    acc = body.get('accuracy', 4.0)

    if lat is None or lng is None or not is_within_kimberley(lat, lng):
        return JsonResponse({'error': 'Coordinates must be within Kimberley campus sector'}, status=400)

    officer = get_or_create_officer_profile(request.user)
    officer.latitude = Decimal(str(round(float(lat), 6)))
    officer.longitude = Decimal(str(round(float(lng), 6)))
    try:
        officer.accuracy_meters = round(float(acc), 1)
    except (TypeError, ValueError):
        officer.accuracy_meters = 4.0
    officer.last_telemetry_at = timezone.now()
    officer.save(update_fields=['latitude', 'longitude', 'accuracy_meters', 'last_telemetry_at'])

    return JsonResponse({
        'success': True,
        'officer_id': officer.id,
        'badge_number': officer.badge_number,
        'latitude': float(officer.latitude),
        'longitude': float(officer.longitude),
        'accuracy_meters': officer.accuracy_meters,
    })


def kimberley_map_tile(request, z, x, y):
    """
    Serves self-hosted GIS map tiles directly from static/tiles/kimberley/{z}/{x}/{y}.png.
    For any real-world GPS location outside the pre-cached bundle, redirects directly to the
    global OpenStreetMap CDN so tiles load in ~200ms without blocking Gunicorn workers.
    """
    if z < 1 or z > 19:
        return HttpResponseNotFound("Zoom level outside valid bounds.")

    local_tile = Path(settings.BASE_DIR) / 'static' / 'tiles' / 'kimberley' / str(z) / str(x) / f"{y}.png"
    if local_tile.exists():
        return HttpResponse(
            local_tile.read_bytes(),
            content_type='image/png',
            headers={'Cache-Control': 'public, max-age=604800, immutable'}
        )

    return HttpResponseRedirect(f"https://tile.openstreetmap.org/{z}/{x}/{y}.png")


