/**
 * University Panic Button System (UPBS)
 * security.js - In-Vehicle Tablet (MDT) Full-Bleed GIS Radar, Case Acceptance & Multi-Officer Broadcast
 */

let map = null;
let victimMarkers = {};
let victimMarkerStatuses = {};
let officerMarkers = {};
let vectorLayerGroup = null;
let knownAlertIds = new Set();
let latestAlerts = [];
let currentOfficer = null;
let onDutyOfficers = [];
let activeQueueFilter = 'ALL';
let focusedAlertId = null;
let soundEnabled = true;
let nightPatrolMode = false;
let movePatrolMode = false;

const KIMBERLEY_CENTER = [-28.742050, 24.765100];

const SVG_VOLUME_ON = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
const SVG_VOLUME_OFF = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>`;
const SVG_SHIELD_CHECK = `<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #34d399;" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>`;
const SVG_PHONE = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>`;
const SVG_STATUS_DOT = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="3"></circle></svg>`;
const SVG_ACK = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
const SVG_DISPATCH = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="3 11 22 2 13 21 11 13 3 11"></polygon></svg>`;
const SVG_RESOLVE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
const SVG_CROSSHAIR = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line></svg>`;
const SVG_BEACON_PIN = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle></svg>`;
const SVG_SHIELD_UNIT = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>`;

document.addEventListener('DOMContentLoaded', () => {
    initCampusMap();
    initOfficerHardwareGPS();
    startLiveAlertPolling();

    const soundToggle = document.getElementById('soundToggle');
    if (soundToggle) {
        soundToggle.addEventListener('click', () => {
            soundEnabled = !soundEnabled;
            soundToggle.innerHTML = soundEnabled
                ? `${SVG_VOLUME_ON}<span>Sound: ON</span>`
                : `${SVG_VOLUME_OFF}<span>Sound: OFF</span>`;
            soundToggle.className = soundEnabled ? 'btn btn-outline mdt-touch-btn' : 'btn btn-danger mdt-touch-btn';
        });
    }
});

function initCampusMap() {
    const mapEl = document.getElementById('map');
    if (!mapEl) return;

    const kimberleyBounds = L.latLngBounds(
        L.latLng(-28.765, 24.740),
        L.latLng(-28.720, 24.790)
    );

    map = L.map('map', {
        center: KIMBERLEY_CENTER,
        zoom: 16,
        minZoom: 14,
        maxZoom: 18,
        zoomControl: false,
        maxBounds: kimberleyBounds,
        maxBoundsViscosity: 1.0
    });

    L.control.zoom({ position: 'topleft' }).addTo(map);

    const kimberleyStreetLayer = L.tileLayer('/alerts/tiles/kimberley/{z}/{x}/{y}.png', {
        minZoom: 14,
        maxZoom: 18,
        bounds: kimberleyBounds,
        attribution: 'Kimberley Campus Tactical Dark GIS | &copy; OpenStreetMap contributors'
    });

    kimberleyStreetLayer.addTo(map);
    vectorLayerGroup = L.layerGroup().addTo(map);

    const topLeftCorner = document.querySelector('.leaflet-top.leaflet-left');
    if (topLeftCorner) {
        topLeftCorner.style.marginTop = '72px';
        topLeftCorner.style.marginLeft = '4px';
    }

    // Allow officer to tap on map when "Set My GPS" mode is active
    map.on('click', (e) => {
        if (movePatrolMode) {
            broadcastOfficerLocation(e.latlng.lat, e.latlng.lng, 3.0, true);
            toggleMovePatrolMode(false);
        }
    });

    setTimeout(() => {
        if (map) map.invalidateSize();
    }, 100);
    window.addEventListener('resize', () => {
        if (map) map.invalidateSize();
    });
}

function initOfficerHardwareGPS() {
    if (!navigator.geolocation) return;
    navigator.geolocation.watchPosition(
        (pos) => {
            const lat = pos.coords.latitude;
            const lng = pos.coords.longitude;
            const acc = pos.coords.accuracy || 5.0;
            // Only overwrite if device is physically inside Kimberley campus bounds with high-precision GNSS lock (<= 100m)
            if (acc <= 100.0 && lat >= -28.765 && lat <= -28.720 && lng >= 24.740 && lng <= 24.790) {
                broadcastOfficerLocation(lat, lng, acc, false);
            }
        },
        () => {},
        { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }
    );
}

function toggleMovePatrolMode(forceState) {
    movePatrolMode = typeof forceState === 'boolean' ? forceState : !movePatrolMode;
    const btn = document.getElementById('repositionUnitBtn');
    const label = document.getElementById('repositionUnitLabel');
    const mapEl = document.getElementById('map');

    if (btn) btn.classList.toggle('active-mode', movePatrolMode);
    if (label) label.textContent = movePatrolMode ? 'Tap Map to Place Unit...' : 'Set My GPS';
    if (mapEl) mapEl.style.cursor = movePatrolMode ? 'crosshair' : '';
}

function broadcastOfficerLocation(lat, lng, accuracy, adjustMapAfter) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    fetch('/alerts/api/officer-location/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify({
            latitude: lat,
            longitude: lng,
            accuracy: accuracy || 3.5
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            pollAlerts(adjustMapAfter ? (focusedAlertId || 'FIRST') : null);
        }
    })
    .catch(err => console.error("Error broadcasting officer GPS:", err));
}

function fitAllTacticalUnits() {
    if (!map) return;
    const points = [];
    latestAlerts.forEach(a => {
        points.push([a.latitude, a.longitude]);
        (a.attending_officers || []).forEach(o => {
            points.push([o.latitude, o.longitude]);
        });
    });
    if (currentOfficer) {
        points.push([currentOfficer.latitude, currentOfficer.longitude]);
    }
    if (points.length >= 2) {
        const drawerCollapsed = document.getElementById('mdtViewport')?.classList.contains('drawer-collapsed');
        map.fitBounds(points, {
            paddingTopLeft: [75, 95],
            paddingBottomRight: [drawerCollapsed ? 60 : 435, 80],
            maxZoom: 17,
            animate: true,
            duration: 0.9
        });
    } else {
        map.flyTo(KIMBERLEY_CENTER, 16, { animate: true, duration: 0.8 });
    }
}

function fitAlertAndResponders(alertObj) {
    if (!map || !alertObj) return;
    focusedAlertId = alertObj.id;
    const points = [[alertObj.latitude, alertObj.longitude]];

    if (currentOfficer) {
        points.push([currentOfficer.latitude, currentOfficer.longitude]);
    }
    if (alertObj.my_route_coords && alertObj.my_route_coords.length > 0) {
        alertObj.my_route_coords.forEach(pt => points.push(pt));
    }
    (alertObj.attending_officers || []).forEach(o => {
        points.push([o.latitude, o.longitude]);
        if (o.route_coords && o.route_coords.length > 0) {
            o.route_coords.forEach(pt => points.push(pt));
        }
    });

    const drawerCollapsed = document.getElementById('mdtViewport')?.classList.contains('drawer-collapsed');
    map.fitBounds(points, {
        paddingTopLeft: [80, 100],
        paddingBottomRight: [drawerCollapsed ? 70 : 435, 85],
        maxZoom: 17,
        animate: true,
        duration: 0.95
    });
}

function getRouteMidpoint(coords, fallbackLat1, fallbackLng1, fallbackLat2, fallbackLng2) {
    if (Array.isArray(coords) && coords.length >= 2) {
        const midIdx = Math.floor(coords.length / 2);
        return coords[midIdx];
    }
    return [(fallbackLat1 + fallbackLat2) / 2, (fallbackLng1 + fallbackLng2) / 2];
}

function drawTacticalStreetRoute(coords, color, weight, isDashed, glowOpacity) {
    if (!vectorLayerGroup || !Array.isArray(coords) || coords.length < 2) return;
    // Outer navigation glow casing
    L.polyline(coords, {
        color: color,
        weight: weight + 5,
        opacity: glowOpacity || 0.24,
        lineCap: 'round',
        lineJoin: 'round'
    }).addTo(vectorLayerGroup);

    // Inner street-following route line
    L.polyline(coords, {
        color: color,
        weight: weight,
        dashArray: isDashed ? '8, 6' : null,
        opacity: 0.96,
        lineCap: 'round',
        lineJoin: 'round'
    }).addTo(vectorLayerGroup);
}

function flyToCampusSector(lat, lng, zoomLevel) {
    if (map) {
        map.flyTo([lat, lng], zoomLevel || 17, { animate: true, duration: 0.85 });
    }
}

function toggleNightPatrolMap() {
    nightPatrolMode = !nightPatrolMode;
    const viewport = document.getElementById('mdtViewport');
    const btn = document.getElementById('nightModeToggle');
    const label = document.getElementById('nightModeLabel');

    if (viewport) viewport.classList.toggle('mdt-night-filter', nightPatrolMode);
    if (btn) btn.classList.toggle('active-mode', nightPatrolMode);
    if (label) label.textContent = nightPatrolMode ? 'Night Radar: ON' : 'Night Radar: OFF';
}

function toggleDispatchDrawer() {
    const viewport = document.getElementById('mdtViewport');
    const btn = document.getElementById('drawerToggleBtn');
    const label = document.getElementById('drawerToggleLabel');
    if (!viewport) return;

    const collapsed = viewport.classList.toggle('drawer-collapsed');
    if (btn) btn.classList.toggle('active-mode', !collapsed);
    if (label) label.textContent = collapsed ? 'Show Queue' : 'Hide Queue';
    setTimeout(() => {
        if (map) map.invalidateSize();
    }, 260);
}

function setQueueFilter(filterVal, btnEl) {
    activeQueueFilter = filterVal;
    document.querySelectorAll('.mdt-filter-btn').forEach(b => b.classList.remove('active'));
    if (btnEl) btnEl.classList.add('active');
    renderAlertList(latestAlerts);
}

function startLiveAlertPolling() {
    pollAlerts('FIRST_IF_DISPATCHED');
    setInterval(() => pollAlerts(null), 2500);
}

function pollAlerts(fitTargetAlertId) {
    fetch('/alerts/api/live/')
        .then(res => res.json())
        .then(data => {
            if (data.current_officer) {
                currentOfficer = data.current_officer;
                const unitLabel = document.getElementById('myUnitLabel');
                if (unitLabel) {
                    unitLabel.textContent = `${currentOfficer.badge_number} (${currentOfficer.latitude.toFixed(4)}, ${currentOfficer.longitude.toFixed(4)} ±${currentOfficer.accuracy_meters}m)`;
                }
            }
            if (data.on_duty_officers) {
                onDutyOfficers = data.on_duty_officers;
            }
            if (data.alerts) {
                latestAlerts = data.alerts;
                updateTelemetryCounters(data.alerts);
                renderAlertList(data.alerts);
                updateMapMarkersAndVectors(data.alerts);
                checkForNewEmergencies(data.alerts);

                if (fitTargetAlertId === 'FIRST_IF_DISPATCHED' && data.alerts.length > 0) {
                    fitAlertAndResponders(data.alerts[0]);
                } else if (fitTargetAlertId === 'FIRST' && data.alerts.length > 0) {
                    fitAlertAndResponders(data.alerts[0]);
                } else if (typeof fitTargetAlertId === 'number') {
                    const target = data.alerts.find(a => a.id === fitTargetAlertId);
                    if (target) fitAlertAndResponders(target);
                }
            }
        })
        .catch(err => console.error("Error polling security alerts:", err));
}

function updateTelemetryCounters(alerts) {
    const sentCount = alerts.filter(a => a.status === 'SENT').length;
    const ackCount = alerts.filter(a => a.status === 'RECEIVED').length;
    const dispCount = alerts.filter(a => a.status === 'DISPATCHED').length;

    const sentEl = document.getElementById('statSentCount');
    const ackEl = document.getElementById('statAckCount');
    const dispEl = document.getElementById('statDispatchedCount');

    if (sentEl) sentEl.textContent = sentCount;
    if (ackEl) ackEl.textContent = ackCount;
    if (dispEl) dispEl.textContent = dispCount;
}

function renderAlertList(alerts) {
    const container = document.getElementById('alertsContainer');
    if (!container) return;

    const filtered = activeQueueFilter === 'ALL'
        ? alerts
        : alerts.filter(a => a.status === activeQueueFilter);

    // Compact state when no alerts match so drawer dynamically shrinks to minimal height
    if (filtered.length === 0) {
        container.innerHTML = `
            <div style="display: flex; align-items: center; gap: 0.7rem; padding: 0.55rem 0.65rem; color: #94a3b8;">
                ${SVG_SHIELD_CHECK}
                <div>
                    <div style="font-weight: 700; color: #e2e8f0; font-size: 0.86rem;">Kimberley Sectors Nominal</div>
                    <div style="font-size: 0.75rem;">No active incidents in selected queue view.</div>
                </div>
            </div>
        `;
        return;
    }

    let html = '';
    filtered.forEach(a => {
        let badgeClass = 'badge-sent';
        let cardStatusClass = 'status-sent';
        if (a.status === 'RECEIVED') {
            badgeClass = 'badge-received';
            cardStatusClass = 'status-received';
        }
        if (a.status === 'DISPATCHED') {
            badgeClass = 'badge-dispatched';
            cardStatusClass = 'status-dispatched';
        }

        const responders = a.attending_officers || [];
        let broadcastHtml = '';

        let responderRowsHtml = '';
        responders.forEach((r, idx) => {
            const isClosest = idx === 0 && responders.length > 1;
            const unitTag = r.is_me
                ? `<span style="background: rgba(37, 99, 235, 0.3); color: #93c5fd; border: 1px solid rgba(96, 165, 250, 0.45); padding: 0.05rem 0.38rem; border-radius: 4px; font-size: 0.65rem; font-weight: 700;">YOUR UNIT</span>`
                : `<span style="background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(52, 211, 153, 0.4); padding: 0.05rem 0.38rem; border-radius: 4px; font-size: 0.65rem; font-weight: 700;">${isClosest ? 'CLOSEST TO VICTIM' : 'ATTENDING UNIT'}</span>`;

            const etaText = r.response_status === 'ON_SCENE' ? 'ON SCENE' : `ETA ~${r.eta_seconds}s`;
            const distBadgeColor = r.distance_to_victim_m > 500 ? '#fbbf24' : '#38bdf8';

            responderRowsHtml += `
                <div class="mdt-responder-row">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.4rem;">
                        <span style="font-weight: 700; color: #f8fafc;">${r.officer_name} <span style="font-family: var(--font-mono); color: #94a3b8; font-size: 0.72rem;">(${r.badge_number})</span></span>
                        ${unitTag}
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; font-family: var(--font-mono); font-size: 0.72rem; color: ${distBadgeColor}; margin-top: 0.18rem;">
                        <span>Relative to Victim: <strong>${r.distance_to_victim_m}m</strong> (${r.bearing_from_victim || r.bearing_to_victim} of Victim)</span>
                        <span style="color: #34d399; font-weight: 700;">${etaText}</span>
                    </div>
                    ${r.route_summary ? `<div style="font-size: 0.7rem; color: #94a3b8; margin-top: 0.12rem;">Route to Victim: <span style="color: #e2e8f0;">${r.route_summary}</span></div>` : ''}
                </div>
            `;
        });

        // Tactical urgency indicator if current officer is closer to the victim than other attending units
        let urgencyBannerHtml = '';
        if (!a.is_accepted_by_me && responders.length > 0) {
            const closestAttendingDist = responders[0].distance_to_victim_m;
            if (a.my_distance_to_victim_m < closestAttendingDist) {
                urgencyBannerHtml = `
                    <div style="background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); color: #fde68a; padding: 0.35rem 0.5rem; border-radius: 6px; font-size: 0.71rem; font-weight: 700; margin-bottom: 0.4rem;">
                        FASTEST INTERCEPT: Your unit is ${Math.round(closestAttendingDist - a.my_distance_to_victim_m)}m closer to the victim than attending units.
                    </div>
                `;
            }
        }

        broadcastHtml = `
            <div class="mdt-broadcast-box">
                <div class="mdt-broadcast-header">
                    <span>Units Relative to Victim (${responders.length} Attending)</span>
                    <span>LIVE GPS</span>
                </div>
                ${urgencyBannerHtml}
                ${!a.is_accepted_by_me ? `
                    <div style="font-family: var(--font-mono); font-size: 0.72rem; color: #93c5fd; padding-bottom: ${responders.length ? '0.4rem' : '0'}; border-bottom: ${responders.length ? '1px dashed rgba(148, 163, 184, 0.14)' : 'none'};">
                        <div>Your Unit Relative to Victim: <strong>${a.my_distance_to_victim_m}m</strong> (ETA ~${a.my_eta_seconds}s)</div>
                        ${a.my_route_summary ? `<div style="font-family: var(--font-sans); font-size: 0.7rem; color: #94a3b8; margin-top: 0.12rem;">Route to Victim: <span style="color: #e2e8f0;">${a.my_route_summary}</span></div>` : ''}
                    </div>
                ` : ''}
                ${responderRowsHtml}
            </div>
        `;

        html += `
            <div class="mdt-incident-card ${cardStatusClass}">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.45rem; margin-bottom: 0.55rem; padding-bottom: 0.45rem; border-bottom: 1px solid rgba(148, 163, 184, 0.14);">
                    <div style="display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
                        <span class="badge ${badgeClass}" style="display: inline-flex; align-items: center; gap: 0.3rem; font-size: 0.7rem;">
                            ${SVG_STATUS_DOT}
                            ${a.status}
                        </span>
                        <strong style="font-size: 0.92rem; color: #ffffff; font-variant-numeric: tabular-nums;">#${a.id} • ${a.alert_type}</strong>
                    </div>
                    <span style="font-size: 0.75rem; color: #94a3b8; font-family: var(--font-mono); font-variant-numeric: tabular-nums;">${a.timestamp_formatted}</span>
                </div>

                <div style="display: grid; gap: 0.28rem; font-size: 0.83rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.4rem;">
                        <span style="color: #f8fafc; font-weight: 700;">Victim: ${a.user_full_name}</span>
                        <span style="font-family: var(--font-mono); font-size: 0.73rem; color: #cbd5e1; background: rgba(15, 23, 42, 0.8); padding: 0.12rem 0.45rem; border-radius: 4px; border: 1px solid rgba(148, 163, 184, 0.18);">ID: ${a.institutional_id}</span>
                    </div>

                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.4rem; flex-wrap: wrap;">
                        <span style="color: #fcd34d; font-weight: 700;">${a.location_description}</span>
                        <a href="tel:${a.contact_number}" style="color: #60a5fa; text-decoration: none; font-family: var(--font-mono); font-size: 0.76rem; font-weight: 700; display: inline-flex; align-items: center; gap: 0.25rem; background: rgba(37, 99, 235, 0.16); padding: 0.16rem 0.5rem; border-radius: 5px; border: 1px solid rgba(96, 165, 250, 0.3);">
                            ${SVG_PHONE}
                            ${a.contact_number}
                        </a>
                    </div>
                </div>

                ${broadcastHtml}

                <div class="mdt-action-grid">
                    ${!a.is_accepted_by_me ? `
                        <button type="button" class="btn btn-accept-case" onclick="acceptCase(${a.id})">
                            ${SVG_DISPATCH}
                            Accept Case &amp; Broadcast My Location
                        </button>
                    ` : `
                        <button type="button" class="btn btn-primary" onclick="acceptCase(${a.id})" title="Re-broadcast GPS &amp; dynamically fit map to Victim and Attending Units">
                            ${SVG_CROSSHAIR}
                            Sync &amp; Fit Route
                        </button>
                        ${a.my_response_status !== 'ON_SCENE' ? `
                            <button type="button" class="btn btn-outline" style="border-color: rgba(56, 189, 248, 0.45); color: #38bdf8;" onclick="updateAlertStatus(${a.id}, 'ON_SCENE')">
                                ${SVG_ACK}
                                Arrived On Scene
                            </button>
                        ` : ''}
                    `}

                    ${a.status === 'SENT' ? `
                        <button type="button" class="btn btn-outline" onclick="updateAlertStatus(${a.id}, 'RECEIVED')">
                            ${SVG_ACK}
                            Acknowledge
                        </button>
                    ` : ''}

                    <button type="button" class="btn btn-save-green" onclick="openResolveModal(${a.id})">
                        ${SVG_RESOLVE}
                        Mark Resolved
                    </button>

                    ${!a.is_accepted_by_me ? `
                        <button type="button" class="btn btn-outline" onclick="zoomToAlert(${a.latitude}, ${a.longitude}, ${a.id})">
                            ${SVG_CROSSHAIR}
                            Frame Relative Route
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function createVictimMarkerIcon(status) {
    let statusClass = 'mdt-marker-sent';
    if (status === 'RECEIVED') statusClass = 'mdt-marker-received';
    if (status === 'DISPATCHED') statusClass = 'mdt-marker-dispatched';

    return L.divIcon({
        className: 'mdt-custom-div-icon',
        html: `
            <div class="mdt-marker-wrap ${statusClass}">
                <span class="mdt-marker-ring"></span>
                <span class="mdt-marker-core">${SVG_BEACON_PIN}</span>
            </div>
        `,
        iconSize: [38, 38],
        iconAnchor: [19, 19],
        popupAnchor: [0, -19]
    });
}

function createOfficerMarkerIcon(isMe) {
    const cls = isMe ? 'mdt-officer-marker' : 'mdt-peer-officer-marker';
    return L.divIcon({
        className: 'mdt-custom-div-icon',
        html: `
            <div class="mdt-marker-wrap ${cls}">
                <span class="mdt-marker-ring"></span>
                <span class="mdt-marker-core">${SVG_SHIELD_UNIT}</span>
            </div>
        `,
        iconSize: [38, 38],
        iconAnchor: [19, 19],
        popupAnchor: [0, -19]
    });
}

function buildVictimPopupHtml(a) {
    return `
        <div style="min-width: 225px; font-family: var(--font-sans); padding: 0.15rem;">
            <div style="font-size: 0.7rem; font-family: var(--font-mono); color: #f87171; font-weight: 700; text-transform: uppercase;">
                VICTIM SOS #${a.id} • ${a.status}
            </div>
            <div style="font-weight: 700; font-size: 0.94rem; color: #ffffff; margin: 0.15rem 0 0.3rem;">
                ${a.user_full_name} (${a.alert_type})
            </div>
            <div style="font-size: 0.8rem; color: #fcd34d; font-weight: 600; margin-bottom: 0.35rem;">
                ${a.location_description}
            </div>
            <div style="font-size: 0.75rem; font-family: var(--font-mono); color: #93c5fd; margin-bottom: 0.55rem;">
                Route Distance: <strong>${a.my_distance_to_victim_m}m</strong> (ETA ~${a.my_eta_seconds}s)
            </div>
            <div style="display: flex; gap: 0.4rem;">
                <button type="button" class="btn btn-primary" style="min-height: 34px; font-size: 0.75rem; padding: 0.3rem 0.6rem; flex: 1;" onclick="acceptCase(${a.id})">
                    ${a.is_accepted_by_me ? 'Sync Route' : 'Accept Case'}
                </button>
                <button type="button" class="btn btn-save-green" style="min-height: 34px; font-size: 0.75rem; padding: 0.3rem 0.6rem; flex: 1;" onclick="openResolveModal(${a.id})">Resolve</button>
            </div>
        </div>
    `;
}

function updateMapMarkersAndVectors(alerts) {
    if (!map || !vectorLayerGroup) return;

    vectorLayerGroup.clearLayers();

    const activeAlertIds = new Set(alerts.map(a => String(a.id)));
    Object.keys(victimMarkers).forEach(existingId => {
        if (!activeAlertIds.has(String(existingId))) {
            map.removeLayer(victimMarkers[existingId]);
            delete victimMarkers[existingId];
            delete victimMarkerStatuses[existingId];
        }
    });

    const officersToRender = new Map();
    if (currentOfficer) {
        officersToRender.set(currentOfficer.officer_id, {
            ...currentOfficer,
            is_me: true,
            role_label: 'YOUR PATROL UNIT (DRAG TO MOVE)'
        });
    }

    alerts.forEach(a => {
        const key = a.id;
        if (!victimMarkers[key]) {
            const marker = L.marker([a.latitude, a.longitude], {
                icon: createVictimMarkerIcon(a.status)
            })
                .addTo(map)
                .bindPopup(buildVictimPopupHtml(a));
            victimMarkers[key] = marker;
            victimMarkerStatuses[key] = a.status;
        } else {
            victimMarkers[key].setLatLng([a.latitude, a.longitude]);
            if (victimMarkerStatuses[key] !== a.status) {
                victimMarkers[key].setIcon(createVictimMarkerIcon(a.status));
                victimMarkerStatuses[key] = a.status;
            }
            victimMarkers[key].setPopupContent(buildVictimPopupHtml(a));
        }

        const responders = a.attending_officers || [];

        // If current officer has not accepted yet, draw street-following preview route from current officer to victim
        if (!a.is_accepted_by_me && currentOfficer) {
            const myCoords = (a.my_route_coords && a.my_route_coords.length >= 2)
                ? a.my_route_coords
                : [[currentOfficer.latitude, currentOfficer.longitude], [a.latitude, a.longitude]];

            drawTacticalStreetRoute(myCoords, '#3b82f6', 4, true, 0.22);

            const [midLat, midLng] = getRouteMidpoint(myCoords, currentOfficer.latitude, currentOfficer.longitude, a.latitude, a.longitude);
            L.marker([midLat, midLng], {
                icon: L.divIcon({
                    className: '',
                    html: `<div class="mdt-vector-label">YOU → VICTIM: ${a.my_distance_to_victim_m}m • ETA ${a.my_eta_seconds}s</div>`,
                    iconSize: [195, 24],
                    iconAnchor: [97, 12]
                }),
                interactive: false
            }).addTo(vectorLayerGroup);
        }

        // Draw street-following driving routes for all attending officers strictly relative to the VICTIM
        responders.forEach(r => {
            officersToRender.set(r.officer_id, {
                ...r,
                role_label: r.is_me ? 'YOUR PATROL UNIT (ATTENDING)' : `ATTENDING UNIT • ${r.distance_to_victim_m}m FROM VICTIM`
            });

            const lineColor = r.is_me ? '#38bdf8' : '#10b981';
            const rCoords = (r.route_coords && r.route_coords.length >= 2)
                ? r.route_coords
                : [[r.latitude, r.longitude], [a.latitude, a.longitude]];

            drawTacticalStreetRoute(rCoords, lineColor, 5, false, 0.30);

            const [midLat, midLng] = getRouteMidpoint(rCoords, r.latitude, r.longitude, a.latitude, a.longitude);
            L.marker([midLat, midLng], {
                icon: L.divIcon({
                    className: '',
                    html: `<div class="mdt-vector-label" style="border-color: ${lineColor};">${r.badge_number} → VICTIM: ${r.distance_to_victim_m}m • ETA ${r.eta_seconds}s</div>`,
                    iconSize: [215, 24],
                    iconAnchor: [107, 12]
                }),
                interactive: false
            }).addTo(vectorLayerGroup);
        });
    });

    // Update or create officer markers on map
    const activeOfficerIds = new Set(Array.from(officersToRender.keys()).map(String));
    Object.keys(officerMarkers).forEach(existingOffId => {
        if (!activeOfficerIds.has(String(existingOffId))) {
            map.removeLayer(officerMarkers[existingOffId]);
            delete officerMarkers[existingOffId];
        }
    });

    officersToRender.forEach((off, offId) => {
        const popupHtml = `
            <div style="min-width: 200px; font-family: var(--font-sans);">
                <div style="font-size: 0.68rem; font-family: var(--font-mono); color: ${off.is_me ? '#60a5fa' : '#34d399'}; font-weight: 700;">
                    ${off.role_label}
                </div>
                <div style="font-weight: 700; font-size: 0.9rem; color: #ffffff; margin: 0.15rem 0;">
                    ${off.officer_name} (${off.badge_number})
                </div>
                <div style="font-size: 0.76rem; color: #cbd5e1;">
                    ${off.current_post || 'Kimberley Mobile Patrol'}
                </div>
                <div style="font-size: 0.72rem; font-family: var(--font-mono); color: #94a3b8; margin-top: 0.25rem;">
                    GPS: ${off.latitude.toFixed(5)}, ${off.longitude.toFixed(5)} (±${off.accuracy_meters || 4.0}m)
                </div>
            </div>
        `;

        if (!officerMarkers[offId]) {
            const m = L.marker([off.latitude, off.longitude], {
                icon: createOfficerMarkerIcon(off.is_me),
                draggable: Boolean(off.is_me)
            })
                .addTo(map)
                .bindPopup(popupHtml);

            if (off.is_me) {
                m.on('dragend', (ev) => {
                    const pos = ev.target.getLatLng();
                    broadcastOfficerLocation(pos.lat, pos.lng, 3.0, true);
                });
            }
            officerMarkers[offId] = m;
        } else {
            officerMarkers[offId].setLatLng([off.latitude, off.longitude]);
            officerMarkers[offId].setPopupContent(popupHtml);
        }
    });
}

function acceptCase(alertId) {
    focusedAlertId = alertId;
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    const payload = {
        status: 'DISPATCHED',
        officer_lat: currentOfficer ? currentOfficer.latitude : undefined,
        officer_lng: currentOfficer ? currentOfficer.longitude : undefined,
        officer_accuracy: currentOfficer ? currentOfficer.accuracy_meters : 3.5
    };

    fetch(`/alerts/api/update-status/${alertId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Immediately poll and dynamically adjust the map to frame the Officer(s) relative to the Victim
            pollAlerts(alertId);
        } else {
            alert("Error accepting case: " + (data.error || "Server rejected update"));
        }
    });
}

function checkForNewEmergencies(alerts) {
    alerts.forEach(a => {
        if (!knownAlertIds.has(a.id)) {
            knownAlertIds.add(a.id);
            if (a.status === 'SENT' && soundEnabled) {
                playEmergencySiren();
            }
        }
    });
}

function zoomToAlert(lat, lng, alertId) {
    if (!map) return;
    const targetAlert = latestAlerts.find(a => a.id === alertId);
    if (targetAlert) {
        fitAlertAndResponders(targetAlert);
        setTimeout(() => {
            if (victimMarkers[alertId]) victimMarkers[alertId].openPopup();
        }, 500);
    } else {
        map.flyTo([lat, lng], 17, { animate: true, duration: 0.85 });
    }
}

function updateAlertStatus(alertId, newStatus) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

    fetch(`/alerts/api/update-status/${alertId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify({
            status: newStatus,
            officer_lat: currentOfficer ? currentOfficer.latitude : undefined,
            officer_lng: currentOfficer ? currentOfficer.longitude : undefined
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            pollAlerts(alertId);
        } else {
            alert("Error updating status: " + (data.error || "Server rejected update"));
        }
    });
}

function openResolveModal(alertId) {
    const modal = document.getElementById('resolveModal');
    const idInput = document.getElementById('resolveAlertId');
    const badge = document.getElementById('resolveModalAlertBadge');
    const notesInput = document.getElementById('resolveNotesInput');

    if (modal && idInput) {
        idInput.value = alertId;
        if (badge) badge.textContent = `#${alertId}`;
        if (notesInput) notesInput.value = '';
        modal.style.display = 'flex';
        modal.classList.add('active');
        setTimeout(() => {
            if (notesInput) notesInput.focus();
        }, 60);
        return;
    }

    const notes = prompt("Enter resolution notes / action taken by dispatch officers:");
    if (notes !== null) {
        submitResolutionRequest(alertId, notes);
    }
}

function fillResolutionPreset(presetText) {
    const notesInput = document.getElementById('resolveNotesInput');
    if (notesInput) {
        notesInput.value = presetText;
    }
}

function closeResolveModal() {
    const modal = document.getElementById('resolveModal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = '';
    }
}

function confirmResolveModal() {
    const idInput = document.getElementById('resolveAlertId');
    const notesInput = document.getElementById('resolveNotesInput');
    if (!idInput || !idInput.value) return;

    const notes = notesInput ? notesInput.value.trim() : 'Resolved by patrol unit on scene.';
    submitResolutionRequest(idInput.value, notes || 'Resolved by patrol unit on scene.');
    closeResolveModal();
}

function submitResolutionRequest(alertId, notes) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    fetch(`/alerts/api/update-status/${alertId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken || ''
        },
        body: JSON.stringify({
            status: 'RESOLVED',
            response_notes: notes,
            officer_lat: currentOfficer ? currentOfficer.latitude : undefined,
            officer_lng: currentOfficer ? currentOfficer.longitude : undefined
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            if (String(focusedAlertId) === String(alertId)) {
                focusedAlertId = null;
            }
            if (map) map.closePopup();
            pollAlerts(null);
        } else {
            alert("Error resolving alert: " + (data.error || "Server rejected update"));
        }
    })
    .catch(err => {
        console.error("Resolution request error:", err);
        alert("Network error while resolving incident.");
    });
}

function playEmergencySiren() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(659.25, ctx.currentTime);
        osc.frequency.linearRampToValueAtTime(880, ctx.currentTime + 0.3);
        osc.frequency.linearRampToValueAtTime(659.25, ctx.currentTime + 0.6);

        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 1.2);

        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start();
        osc.stop(ctx.currentTime + 1.2);
    } catch (e) {
        console.warn("Audio autoplay blocked by browser policy until user interacts", e);
    }
}
