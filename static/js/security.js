/**
 * University Panic Button System (UPBS)
 * security.js - Computer-Aided Dispatch (CAD) Operations Radar & Incident Queue
 */

let map = null;
let markers = {};
let knownAlertIds = new Set();
let soundEnabled = true;

const SVG_VOLUME_ON = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14"></path><path d="M15.54 8.46a5 5 0 0 1 0 7.07"></path></svg>`;
const SVG_VOLUME_OFF = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>`;
const SVG_SHIELD_CHECK = `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #34d399; margin-bottom: 0.4rem;" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg>`;
const SVG_PHONE = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"></path></svg>`;
const SVG_STATUS_DOT = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="3"></circle></svg>`;
const SVG_ACK = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
const SVG_DISPATCH = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="3 11 22 2 13 21 11 13 3 11"></polygon></svg>`;
const SVG_RESOLVE = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
const SVG_CROSSHAIR = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line></svg>`;

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
            soundToggle.className = soundEnabled ? 'btn btn-outline' : 'btn btn-danger';
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
        center: [-28.742050, 24.765100],
        zoom: 16,
        minZoom: 14,
        maxZoom: 18,
        maxBounds: kimberleyBounds,
        maxBoundsViscosity: 1.0
    });

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
        { position: 'topright' }
    ).addTo(map);
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
                renderAlertList(data.alerts);
                updateMapMarkers(data.alerts);
                checkForNewEmergencies(data.alerts);
            }
        })
        .catch(err => console.error("Error polling security alerts:", err));
}

function renderAlertList(alerts) {
    const container = document.getElementById('alertsContainer');
    if (!container) return;

    if (alerts.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 2.25rem 1rem; color: #94a3b8;">
                ${SVG_SHIELD_CHECK}
                <p style="font-weight: 600; color: #e2e8f0; font-size: 0.95rem;">All Sectors Nominal</p>
                <p style="font-size: 0.85rem; margin-top: 0.25rem;">No active emergency alerts in the CAD dispatch queue.</p>
            </div>
        `;
        return;
    }

    let html = '';
    alerts.forEach(a => {
        let badgeClass = 'badge-sent';
        if (a.status === 'RECEIVED') badgeClass = 'badge-received';
        if (a.status === 'DISPATCHED') badgeClass = 'badge-dispatched';
        if (a.status === 'RESOLVED') badgeClass = 'badge-resolved';

        const cardBorder = a.status === 'SENT'
            ? '1px solid rgba(239, 68, 68, 0.35)'
            : '1px solid rgba(148, 163, 184, 0.16)';

        html += `
            <div class="card" style="border: ${cardBorder}; margin-bottom: 1rem; padding: 1.15rem 1.25rem;">
                <div class="card-header" style="margin-bottom: 0.85rem; padding-bottom: 0.65rem;">
                    <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                        <span class="badge ${badgeClass}" style="display: inline-flex; align-items: center; gap: 0.35rem;">
                            ${SVG_STATUS_DOT}
                            ${a.status}
                        </span>
                        <strong style="font-size: 1rem; color: #ffffff; font-variant-numeric: tabular-nums;">#${a.id} - ${a.alert_type}</strong>
                    </div>
                    <span style="font-size: 0.8rem; color: #94a3b8; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-variant-numeric: tabular-nums;">${a.timestamp_formatted}</span>
                </div>
                <div style="margin-bottom: 1rem; font-size: 0.9rem; display: grid; gap: 0.35rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                        <span><strong style="color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em;">Caller:</strong> <span style="color: #f8fafc; font-weight: 600;">${a.user_full_name}</span></span>
                        <span style="font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.8rem; color: #cbd5e1; background: rgba(15, 23, 42, 0.65); padding: 0.15rem 0.5rem; border-radius: 4px; border: 1px solid rgba(148, 163, 184, 0.16);">ID: ${a.institutional_id}</span>
                    </div>
                    <div>
                        <strong style="color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em;">Voice Line:</strong>
                        <a href="tel:${a.contact_number}" style="color: #60a5fa; text-decoration: none; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-variant-numeric: tabular-nums; display: inline-flex; align-items: center; gap: 0.35rem; margin-left: 0.25rem; font-weight: 600;">
                            ${SVG_PHONE}
                            ${a.contact_number}
                        </a>
                    </div>
                    <div>
                        <strong style="color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em;">Sector:</strong>
                        <span style="color: #fcd34d; font-weight: 600; margin-left: 0.25rem;">${a.location_description}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #94a3b8; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-variant-numeric: tabular-nums;">
                        GPS: ${a.latitude}, ${a.longitude}
                    </div>
                </div>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    ${a.status === 'SENT' ? `
                        <button class="btn btn-primary" style="font-size: 0.85rem; padding: 0.5rem 0.9rem;" onclick="updateAlertStatus(${a.id}, 'RECEIVED')">
                            ${SVG_ACK}
                            Acknowledge
                        </button>
                    ` : ''}
                    ${a.status === 'RECEIVED' || a.status === 'SENT' ? `
                        <button class="btn btn-danger" style="font-size: 0.85rem; padding: 0.5rem 0.9rem;" onclick="updateAlertStatus(${a.id}, 'DISPATCHED')">
                            ${SVG_DISPATCH}
                            Dispatch Unit
                        </button>
                    ` : ''}
                    ${a.status === 'DISPATCHED' ? `
                        <button class="btn btn-save-green" style="font-size: 0.85rem; padding: 0.5rem 0.9rem;" onclick="openResolveModal(${a.id})">
                            ${SVG_RESOLVE}
                            Mark Resolved
                        </button>
                    ` : ''}
                    <button class="btn btn-outline" style="font-size: 0.85rem; padding: 0.5rem 0.9rem;" onclick="zoomToAlert(${a.latitude}, ${a.longitude})">
                        ${SVG_CROSSHAIR}
                        Center on Map
                    </button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function updateMapMarkers(alerts) {
    if (!map) return;

    alerts.forEach(a => {
        const key = a.id;
        if (!markers[key]) {
            const marker = L.marker([a.latitude, a.longitude])
                .addTo(map)
                .bindPopup(`
                    <strong>Alert #${a.id}: ${a.alert_type}</strong><br>
                    Caller: ${a.user_full_name}<br>
                    Sector: ${a.location_description}<br>
                    Status: <strong>${a.status}</strong>
                `);
            markers[key] = marker;
        } else {
            markers[key].setLatLng([a.latitude, a.longitude]);
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

function zoomToAlert(lat, lng) {
    if (map) {
        map.flyTo([lat, lng], 18, { animate: true, duration: 1 });
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
    const notes = prompt("Enter resolution notes / action taken by dispatch officers:");
    if (notes !== null) {
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
