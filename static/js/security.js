/**
 * University Panic Button System (UPBS)
 * security.js - In-Vehicle Tablet (MDT) Full-Bleed GIS Radar & CAD Dispatch Controller
 */

let map = null;
let markers = {};
let markerStatuses = {};
let knownAlertIds = new Set();
let latestAlerts = [];
let activeQueueFilter = 'ALL';
let soundEnabled = true;
let nightPatrolMode = false;

const KIMBERLEY_CENTER = [-28.742050, 24.765100];

const SVG_VOLUME_ON = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
const SVG_VOLUME_OFF = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>`;
const SVG_SHIELD_CHECK = `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #34d399; margin-bottom: 0.45rem;" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>`;
const SVG_PHONE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>`;
const SVG_STATUS_DOT = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="3"></circle></svg>`;
const SVG_ACK = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
const SVG_DISPATCH = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="3 11 22 2 13 21 11 13 3 11"></polygon></svg>`;
const SVG_RESOLVE = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
const SVG_CROSSHAIR = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line></svg>`;
const SVG_BEACON_PIN = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle></svg>`;

document.addEventListener('DOMContentLoaded', () => {
    initCampusMap();
    startLiveAlertPolling();

    const soundToggle = document.getElementById('soundToggle');
    if (soundToggle) {
        soundToggle.addEventListener('click', () => {
            soundEnabled = !soundEnabled;
            soundToggle.innerHTML = soundEnabled
                ? `${SVG_VOLUME_ON}<span>Sound Alerts: ON</span>`
                : `${SVG_VOLUME_OFF}<span>Sound Alerts: OFF</span>`;
            soundToggle.className = soundEnabled ? 'btn btn-outline mdt-touch-btn' : 'btn btn-danger mdt-touch-btn';
        });
    }
});

function initCampusMap() {
    const mapEl = document.getElementById('map');
    if (!mapEl) return;

    // Strictly bounded to Kimberley / Sol Plaatje University Campus sector
    const kimberleyBounds = L.latLngBounds(
        L.latLng(-28.765, 24.740), // South-West Kimberley Campus boundary
        L.latLng(-28.720, 24.790)  // North-East Kimberley Campus boundary
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

    // Place large touch-friendly zoom & layer controls on the left below the top HUD bar
    L.control.zoom({ position: 'topleft' }).addTo(map);

    // Self-hosted Kimberley Campus Street Map (served locally — zero API keys or 403 blocks)
    const kimberleyStreetLayer = L.tileLayer('/alerts/tiles/kimberley/{z}/{x}/{y}.png', {
        minZoom: 14,
        maxZoom: 18,
        bounds: kimberleyBounds,
        attribution: 'Kimberley Campus GIS | &copy; OpenStreetMap contributors'
    });

    // Kimberley Satellite / Aerial Imagery (Esri World Imagery — no API key required)
    const kimberleySatelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        minZoom: 14,
        maxZoom: 18,
        bounds: kimberleyBounds,
        attribution: 'Kimberley Aerial | &copy; Esri'
    });

    kimberleyStreetLayer.addTo(map);

    L.control.layers(
        {
            'Kimberley Campus Street Map': kimberleyStreetLayer,
            'Kimberley Satellite Imagery': kimberleySatelliteLayer
        },
        null,
        { position: 'topleft' }
    ).addTo(map);

    // Offset top-left Leaflet controls so they sit cleanly below the top floating HUD bar
    const topLeftCorner = document.querySelector('.leaflet-top.leaflet-left');
    if (topLeftCorner) {
        topLeftCorner.style.marginTop = '72px';
        topLeftCorner.style.marginLeft = '4px';
    }

    // Ensure Leaflet recalculates full-bleed viewport dimensions immediately
    setTimeout(() => {
        if (map) map.invalidateSize();
    }, 100);
    window.addEventListener('resize', () => {
        if (map) map.invalidateSize();
    });
}

function recenterKimberleyCampus() {
    if (map) {
        map.flyTo(KIMBERLEY_CENTER, 16, { animate: true, duration: 0.8 });
    }
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

    if (viewport) {
        viewport.classList.toggle('mdt-night-filter', nightPatrolMode);
    }
    if (btn) {
        btn.classList.toggle('active-mode', nightPatrolMode);
    }
    if (label) {
        label.textContent = nightPatrolMode ? 'Night Radar: ON' : 'Night Radar: OFF';
    }
}

function toggleDispatchDrawer() {
    const viewport = document.getElementById('mdtViewport');
    const btn = document.getElementById('drawerToggleBtn');
    const label = document.getElementById('drawerToggleLabel');
    if (!viewport) return;

    const collapsed = viewport.classList.toggle('drawer-collapsed');
    if (btn) {
        btn.classList.toggle('active-mode', !collapsed);
    }
    if (label) {
        label.textContent = collapsed ? 'Show Queue' : 'Hide Queue';
    }
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
    pollAlerts();
    setInterval(pollAlerts, 2500); // 2.5s polling loop
}

function pollAlerts() {
    fetch('/alerts/api/live/')
        .then(res => res.json())
        .then(data => {
            if (data.alerts) {
                latestAlerts = data.alerts;
                updateTelemetryCounters(data.alerts);
                renderAlertList(data.alerts);
                updateMapMarkers(data.alerts);
                checkForNewEmergencies(data.alerts);
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

    if (filtered.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 2.5rem 1rem; color: #94a3b8;">
                ${SVG_SHIELD_CHECK}
                <p style="font-weight: 700; color: #e2e8f0; font-size: 0.95rem;">Kimberley Sectors Nominal</p>
                <p style="font-size: 0.82rem; margin-top: 0.25rem;">No active emergency alerts matching the selected filter.</p>
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

        html += `
            <div class="mdt-incident-card ${cardStatusClass}">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; margin-bottom: 0.65rem; padding-bottom: 0.55rem; border-bottom: 1px solid rgba(148, 163, 184, 0.14);">
                    <div style="display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap;">
                        <span class="badge ${badgeClass}" style="display: inline-flex; align-items: center; gap: 0.3rem;">
                            ${SVG_STATUS_DOT}
                            ${a.status}
                        </span>
                        <strong style="font-size: 0.95rem; color: #ffffff; font-variant-numeric: tabular-nums;">#${a.id} • ${a.alert_type}</strong>
                    </div>
                    <span style="font-size: 0.78rem; color: #94a3b8; font-family: var(--font-mono); font-variant-numeric: tabular-nums;">${a.timestamp_formatted}</span>
                </div>

                <div style="display: grid; gap: 0.35rem; font-size: 0.86rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem;">
                        <span style="color: #f8fafc; font-weight: 700;">${a.user_full_name}</span>
                        <span style="font-family: var(--font-mono); font-size: 0.76rem; color: #cbd5e1; background: rgba(15, 23, 42, 0.8); padding: 0.15rem 0.5rem; border-radius: 4px; border: 1px solid rgba(148, 163, 184, 0.18);">ID: ${a.institutional_id}</span>
                    </div>

                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                        <span style="color: #fcd34d; font-weight: 700;">${a.location_description}</span>
                        <a href="tel:${a.contact_number}" style="color: #60a5fa; text-decoration: none; font-family: var(--font-mono); font-size: 0.8rem; font-weight: 700; display: inline-flex; align-items: center; gap: 0.3rem; background: rgba(37, 99, 235, 0.16); padding: 0.2rem 0.55rem; border-radius: 5px; border: 1px solid rgba(96, 165, 250, 0.3);">
                            ${SVG_PHONE}
                            ${a.contact_number}
                        </a>
                    </div>

                    <div style="font-size: 0.75rem; color: #94a3b8; font-family: var(--font-mono); font-variant-numeric: tabular-nums;">
                        WGS84: ${a.latitude.toFixed(5)}, ${a.longitude.toFixed(5)}
                    </div>
                </div>

                <div class="mdt-action-grid">
                    ${a.status === 'SENT' ? `
                        <button type="button" class="btn btn-primary" onclick="updateAlertStatus(${a.id}, 'RECEIVED')">
                            ${SVG_ACK}
                            Acknowledge
                        </button>
                    ` : ''}
                    ${a.status === 'RECEIVED' || a.status === 'SENT' ? `
                        <button type="button" class="btn btn-danger" onclick="updateAlertStatus(${a.id}, 'DISPATCHED')">
                            ${SVG_DISPATCH}
                            Dispatch Unit
                        </button>
                    ` : ''}
                    ${a.status === 'DISPATCHED' ? `
                        <button type="button" class="btn btn-save-green" onclick="openResolveModal(${a.id})">
                            ${SVG_RESOLVE}
                            Mark Resolved
                        </button>
                    ` : ''}
                    <button type="button" class="btn btn-outline" onclick="zoomToAlert(${a.latitude}, ${a.longitude}, ${a.id})">
                        ${SVG_CROSSHAIR}
                        Lock Radar
                    </button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function createTacticalMarkerIcon(status) {
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
        iconSize: [36, 36],
        iconAnchor: [18, 18],
        popupAnchor: [0, -18]
    });
}

function buildMarkerPopupHtml(a) {
    return `
        <div style="min-width: 210px; font-family: var(--font-sans); padding: 0.15rem;">
            <div style="font-size: 0.72rem; font-family: var(--font-mono); color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;">
                INCIDENT #${a.id} • ${a.status}
            </div>
            <div style="font-weight: 700; font-size: 0.95rem; color: #ffffff; margin: 0.15rem 0 0.35rem;">
                ${a.alert_type}
            </div>
            <div style="font-size: 0.82rem; color: #e2e8f0; margin-bottom: 0.2rem;">
                <strong>Caller:</strong> ${a.user_full_name} (${a.institutional_id})
            </div>
            <div style="font-size: 0.82rem; color: #fcd34d; font-weight: 600; margin-bottom: 0.6rem;">
                ${a.location_description}
            </div>
            <div style="display: flex; gap: 0.4rem;">
                ${a.status === 'SENT' ? `<button type="button" class="btn btn-primary" style="min-height: 34px; font-size: 0.75rem; padding: 0.3rem 0.6rem; flex: 1;" onclick="updateAlertStatus(${a.id}, 'RECEIVED')">Acknowledge</button>` : ''}
                ${a.status !== 'DISPATCHED' ? `<button type="button" class="btn btn-danger" style="min-height: 34px; font-size: 0.75rem; padding: 0.3rem 0.6rem; flex: 1;" onclick="updateAlertStatus(${a.id}, 'DISPATCHED')">Dispatch</button>` : `<button type="button" class="btn btn-save-green" style="min-height: 34px; font-size: 0.75rem; padding: 0.3rem 0.6rem; flex: 1;" onclick="openResolveModal(${a.id})">Resolve</button>`}
            </div>
        </div>
    `;
}

function updateMapMarkers(alerts) {
    if (!map) return;

    const activeIds = new Set(alerts.map(a => String(a.id)));

    // Remove markers for resolved/cancelled alerts
    Object.keys(markers).forEach(existingId => {
        if (!activeIds.has(String(existingId))) {
            map.removeLayer(markers[existingId]);
            delete markers[existingId];
            delete markerStatuses[existingId];
        }
    });

    alerts.forEach(a => {
        const key = a.id;
        if (!markers[key]) {
            const marker = L.marker([a.latitude, a.longitude], {
                icon: createTacticalMarkerIcon(a.status)
            })
                .addTo(map)
                .bindPopup(buildMarkerPopupHtml(a));
            markers[key] = marker;
            markerStatuses[key] = a.status;
        } else {
            markers[key].setLatLng([a.latitude, a.longitude]);
            if (markerStatuses[key] !== a.status) {
                markers[key].setIcon(createTacticalMarkerIcon(a.status));
                markerStatuses[key] = a.status;
            }
            markers[key].setPopupContent(buildMarkerPopupHtml(a));
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
    if (map) {
        map.flyTo([lat, lng], 17, { animate: true, duration: 0.85 });
        if (alertId && markers[alertId]) {
            setTimeout(() => {
                if (markers[alertId]) markers[alertId].openPopup();
            }, 450);
        }
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
        body: JSON.stringify({ status: newStatus })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            pollAlerts();
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
        return;
    }

    // Fallback if modal element is absent
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
        modal.style.display = 'none';
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
        body: JSON.stringify({ status: 'RESOLVED', response_notes: notes })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            pollAlerts();
        } else {
            alert("Error resolving alert: " + (data.error || "Server rejected update"));
        }
    });
}

// Emergency Dispatch Siren (Multi-frequency sweep using Web Audio API)
function playEmergencySiren() {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(659.25, ctx.currentTime); // E5
        osc.frequency.linearRampToValueAtTime(880, ctx.currentTime + 0.3); // A5
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
