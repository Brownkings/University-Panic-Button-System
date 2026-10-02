/**
 * University Panic Button System (UPBS)
 * security.js - Security Control Room Command Radar & Dispatch Console
 */

let map = null;
let markers = {};
let knownAlertIds = new Set();
let soundEnabled = true;

document.addEventListener('DOMContentLoaded', () => {
    initCampusMap();
    startLiveAlertPolling();

    const soundToggle = document.getElementById('soundToggle');
    if (soundToggle) {
        soundToggle.addEventListener('click', () => {
            soundEnabled = !soundEnabled;
            soundToggle.textContent = soundEnabled ? '🔊 Sound Alerts: ON' : '🔇 Sound Alerts: OFF';
            soundToggle.className = soundEnabled ? 'btn btn-outline' : 'btn btn-danger';
        });
    }
});

function initCampusMap() {
    const mapEl = document.getElementById('map');
    if (!mapEl) return;

    // Centered at Campus coordinates
    map = L.map('map').setView([-28.742050, 24.765100], 16);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors | UPBS Campus Security'
    }).addTo(map);
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
            <div style="text-align: center; padding: 2rem; color: #94a3b8;">
                <p>✓ All quiet. No active emergency alerts at this time.</p>
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

        html += `
            <div class="card" style="border-left: 5px solid ${a.status === 'SENT' ? '#ef4444' : '#3b82f6'}; margin-bottom: 1rem;">
                <div class="card-header">
                    <div>
                        <span class="badge ${badgeClass}">${a.status}</span>
                        <strong style="margin-left: 0.5rem; font-size: 1.1rem; color: #ffffff;">#${a.id} - ${a.alert_type}</strong>
                    </div>
                    <span style="font-size: 0.85rem; color: #94a3b8;">${a.timestamp_formatted}</span>
                </div>
                <div style="margin-bottom: 1rem;">
                    <p style="margin-bottom: 0.3rem;"><strong>Student:</strong> ${a.user_full_name} (${a.institutional_id})</p>
                    <p style="margin-bottom: 0.3rem;"><strong>Contact:</strong> <a href="tel:${a.contact_number}" style="color: #60a5fa;">${a.contact_number}</a></p>
                    <p style="margin-bottom: 0.3rem;"><strong>Location:</strong> <span style="color: #fcd34d;">${a.location_description}</span></p>
                    <p style="font-size: 0.85rem; color: #94a3b8;">GPS: ${a.latitude}, ${a.longitude}</p>
                </div>
                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    ${a.status === 'SENT' ? `
                        <button class="btn btn-primary" onclick="updateAlertStatus(${a.id}, 'RECEIVED')">
                            Acknowledge
                        </button>
                    ` : ''}
                    ${a.status === 'RECEIVED' || a.status === 'SENT' ? `
                        <button class="btn btn-danger" onclick="updateAlertStatus(${a.id}, 'DISPATCHED')">
                            Dispatch Response Team
                        </button>
                    ` : ''}
                    ${a.status === 'DISPATCHED' ? `
                        <button class="btn btn-save-green" onclick="openResolveModal(${a.id})">
                            Mark Resolved & Save Notes
                        </button>
                    ` : ''}
                    <button class="btn btn-outline" onclick="zoomToAlert(${a.latitude}, ${a.longitude})">
                        📍 Center on Map
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
                    Student: ${a.user_full_name}<br>
                    Location: ${a.location_description}<br>
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
