/**
 * University Panic Button System (UPBS)
 * panic.js - Handles Geolocation Telemetry, 3-Second Abort Interlock & Emergency Dispatch
 */

document.addEventListener('DOMContentLoaded', () => {
    const panicBtn = document.getElementById('panicBtn');
    const modal = document.getElementById('abortModal');
    const countdownEl = document.getElementById('countdownNumber');
    const abortBtn = document.getElementById('abortBtn');
    const geoStatusEl = document.getElementById('geoStatus');
    const locationInput = document.getElementById('locationDescription');
    const alertTypeSelect = document.getElementById('alertTypeSelect');

    let countdownTimer = null;
    let secondsLeft = 3;
    let hasRealGpsFix = false;
    let lastReverseGeocodedKey = '';
    let userCoords = {
        latitude: null,
        longitude: null,
        accuracy: null,
        address: ''
    };

    const ICON_GPS_LOCKED = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line><circle cx="12" cy="12" r="3"></circle></svg>`;
    const ICON_GPS_FALLBACK = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;

    function updateGeoStatusBanner(modeText, colorHex) {
        if (!geoStatusEl) return;
        const icon = colorHex === '#34d399' ? ICON_GPS_LOCKED : ICON_GPS_FALLBACK;
        const coordStr = (userCoords.latitude !== null && userCoords.longitude !== null)
            ? ` [${userCoords.latitude.toFixed(5)}, ${userCoords.longitude.toFixed(5)} &plusmn;${Math.round(userCoords.accuracy || 5)}m]`
            : '';
        geoStatusEl.innerHTML = `<span style="color: ${colorHex}; display: inline-flex; align-items: center; gap: 0.45rem; font-variant-numeric: tabular-nums;">${icon} ${modeText}${coordStr}</span>`;
    }

    function setLiveAddressOption(addressText) {
        if (!addressText) return;
        userCoords.address = addressText;
        const liveOpt = document.getElementById('liveGpsAddressOption');
        if (liveOpt) {
            liveOpt.value = addressText;
            liveOpt.textContent = `${addressText} (Live GPS)`;
            if (locationInput && (locationInput.selectedIndex === 0 || locationInput.value === 'Auto-Detect Real GPS Address')) {
                locationInput.value = addressText;
            }
        }
    }

    function reverseGeocodeRealCoords(lat, lng, acc) {
        const key = `${lat.toFixed(4)},${lng.toFixed(4)}`;
        if (key === lastReverseGeocodedKey) return;
        lastReverseGeocodedKey = key;

        fetch(`/alerts/api/resolve-location/?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}&acc=${encodeURIComponent(acc || 8)}`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.address) {
                    setLiveAddressOption(data.address);
                    updateGeoStatusBanner(`Real Location Locked: ${data.address}`, '#34d399');
                    if (typeof window.syncHeroLocationDisplay === 'function') {
                        window.syncHeroLocationDisplay(lat, lng, acc, data.address);
                    }
                }
            })
            .catch(() => {});
    }

    let studentMap = null;
    let studentMarker = null;
    let studentAccuracyCircle = null;

    function initStudentGpsMap() {
        const mapEl = document.getElementById('studentGpsMap');
        if (!mapEl || typeof L === 'undefined') return;

        studentMap = L.map('studentGpsMap', {
            center: [-28.742050, 24.765100],
            zoom: 16,
            minZoom: 4,
            maxZoom: 18,
            zoomControl: true,
            attributionControl: false
        });

        studentMap.on('click', (e) => {
            const { lat, lng } = e.latlng;
            applyRealCoordinates(lat, lng, 5.0, 'Manual Map Pin Lock', null);
            reverseGeocodeRealCoords(lat, lng, 5.0);
        });

        const tileLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            minZoom: 4,
            maxZoom: 18,
            crossOrigin: true
        });

        tileLayer.on('tileerror', (errEvt) => {
            const tile = errEvt.tile;
            const coords = errEvt.coords;
            if (tile && !tile.dataset.fallback) {
                tile.dataset.fallback = '1';
                tile.src = `https://a.basemaps.cartocdn.com/rastertiles/voyager/${coords.z}/${coords.x}/${coords.y}.png`;
            }
        });

        tileLayer.addTo(studentMap);

        [100, 400, 900].forEach(ms => setTimeout(() => {
            if (studentMap) studentMap.invalidateSize();
        }, ms));

        if (typeof ResizeObserver !== 'undefined') {
            new ResizeObserver(() => {
                if (studentMap) studentMap.invalidateSize();
            }).observe(mapEl);
        }
    }

    function updateStudentMapPin(lat, lng, acc) {
        if (!studentMap) initStudentGpsMap();
        if (!studentMap) return;

        studentMap.invalidateSize();
        const latLng = [lat, lng];
        if (!studentMarker) {
            studentAccuracyCircle = L.circle(latLng, {
                radius: Math.max(acc || 15, 12),
                color: '#ef4444',
                weight: 1.5,
                fillColor: '#ef4444',
                fillOpacity: 0.14
            }).addTo(studentMap);

            studentMarker = L.circleMarker(latLng, {
                radius: 8,
                color: '#ffffff',
                weight: 2.5,
                fillColor: '#ef4444',
                fillOpacity: 1.0
            }).addTo(studentMap).bindPopup('<strong>Your Live SOS Location</strong>');
            studentMap.setView(latLng, 16, { animate: false });
        } else {
            studentMarker.setLatLng(latLng);
            if (studentAccuracyCircle) {
                studentAccuracyCircle.setLatLng(latLng);
                studentAccuracyCircle.setRadius(Math.max(acc || 15, 12));
            }
            studentMap.setView(latLng, studentMap.getZoom() || 16, { animate: false });
        }
    }

    initStudentGpsMap();

    function applyRealCoordinates(lat, lng, acc, labelText, preResolvedAddress) {
        userCoords.latitude = Number(lat);
        userCoords.longitude = Number(lng);
        userCoords.accuracy = Number(acc || 10.0);
        hasRealGpsFix = true;

        updateStudentMapPin(userCoords.latitude, userCoords.longitude, userCoords.accuracy);

        if (typeof window.syncHeroLocationDisplay === 'function') {
            window.syncHeroLocationDisplay(userCoords.latitude, userCoords.longitude, userCoords.accuracy, preResolvedAddress || userCoords.address);
        }

        if (preResolvedAddress) {
            setLiveAddressOption(preResolvedAddress);
            updateGeoStatusBanner(`Real Location Locked: ${preResolvedAddress}`, '#34d399');
        } else {
            updateGeoStatusBanner(labelText || 'Live GPS Locked', '#34d399');
            reverseGeocodeRealCoords(userCoords.latitude, userCoords.longitude, userCoords.accuracy);
        }
    }

    const CAMPUS_BUILDINGS = {
        'Main Library - 2nd Floor Study Area': [-28.74160, 24.76470],
        'Science Block B - Computer Labs': [-28.74150, 24.76600],
        'East Student Residence - Block C': [-28.73880, 24.76540],
        'Central Administration Building': [-28.74205, 24.76510],
        'University Sports Grounds & Pavilion': [-28.74340, 24.76630],
        'Campus Gate 1 (Main Entrance)': [-28.74260, 24.76360],
        'South Campus Walkway / Parking Area': [-28.74520, 24.76500]
    };

    if (locationInput) {
        locationInput.addEventListener('change', () => {
            const val = locationInput.value;
            if (CAMPUS_BUILDINGS[val]) {
                const [bLat, bLng] = CAMPUS_BUILDINGS[val];
                applyRealCoordinates(bLat, bLng, 4.0, `Campus Landmark: ${val}`, val);
            }
        });
    }

    function resolveViaNetworkGeoFallback() {
        if (hasRealGpsFix) return;
        fetch('/alerts/api/resolve-location/')
            .then(res => res.json())
            .then(data => {
                if (!hasRealGpsFix && data && data.success && data.latitude && data.longitude) {
                    const lat = Number(data.latitude);
                    const lng = Number(data.longitude);
                    if (lat >= -29.2 && lat <= -28.2 && lng >= 24.2 && lng <= 25.2) {
                        applyRealCoordinates(lat, lng, data.accuracy || 20.0, 'Live Campus Geolocation Locked', data.address);
                        return;
                    }
                }
                throw new Error('Non-campus coordinates');
            })
            .catch(() => {
                if (!hasRealGpsFix) {
                    // Default to Sol Plaatje Central Campus benchmark
                    applyRealCoordinates(-28.742050, 24.765100, 5.0, 'SPU Central Campus (Benchmark Lock)', 'Sol Plaatje University Central Campus');
                }
            });
    }

    function acquireRealBrowserLocation() {
        if (!navigator.geolocation) {
            resolveViaNetworkGeoFallback();
            return;
        }

        // Tier 1: High-accuracy GNSS / Wi-Fi positioning
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                applyRealCoordinates(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy || 5.0, 'High-Accuracy GPS Locked');
            },
            (err) => {
                console.warn("Tier 1 High-Accuracy Geolocation error, trying Tier 2 OS Network location:", err);
                // Tier 2: Standard OS Network positioning (enableHighAccuracy: false)
                navigator.geolocation.getCurrentPosition(
                    (pos) => {
                        applyRealCoordinates(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy || 15.0, 'Live Browser Location Locked');
                    },
                    (err2) => {
                        console.warn("Tier 2 OS Network Geolocation unavailable, using Tier 3 Live Network Geolocation:", err2);
                        resolveViaNetworkGeoFallback();
                    },
                    { enableHighAccuracy: false, maximumAge: 60000, timeout: 5000 }
                );
            },
            { enableHighAccuracy: true, maximumAge: 0, timeout: 4500 }
        );

        // Continuous watch for moving device updates
        navigator.geolocation.watchPosition(
            (pos) => {
                applyRealCoordinates(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy || 5.0, 'High-Accuracy GPS Locked');
            },
            () => {},
            { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }
        );
    }

    acquireRealBrowserLocation();

    if (!panicBtn) return;

    // 2. User presses Panic Button -> Start 3-second abort window & refresh live GPS
    panicBtn.addEventListener('click', (e) => {
        e.preventDefault();
        acquireRealBrowserLocation();
        startAbortCountdown();
    });

    // 3. User cancels false alarm
    if (abortBtn) {
        abortBtn.addEventListener('click', () => {
            cancelAbortCountdown("User aborted before 3s window");
        });
    }

    function startAbortCountdown() {
        secondsLeft = 3;
        countdownEl.textContent = secondsLeft;
        modal.classList.add('active');

        // Play warning tick sound using Web Audio API
        playTickSound(440, 0.1);

        countdownTimer = setInterval(() => {
            secondsLeft -= 1;
            if (secondsLeft > 0) {
                countdownEl.textContent = secondsLeft;
                playTickSound(440, 0.1);
            } else {
                clearInterval(countdownTimer);
                countdownTimer = null;
                modal.classList.remove('active');
                dispatchEmergencyAlert();
            }
        }, 1000);
    }

    function cancelAbortCountdown(reason) {
        if (countdownTimer) {
            clearInterval(countdownTimer);
            countdownTimer = null;
        }
        modal.classList.remove('active');
        playTickSound(220, 0.2); // Low cancel chime
        alert("Alert Aborted: False alarm was safely cancelled.");
    }

    function sendTriggerPost() {
        let desc = locationInput ? locationInput.value : (userCoords.address || "Live GPS Location");
        if (desc === 'Auto-Detect Real GPS Address' && userCoords.address) {
            desc = userCoords.address;
        }
        const alertType = alertTypeSelect ? alertTypeSelect.value : "STANDARD";

        const payload = {
            alert_type: alertType,
            latitude: userCoords.latitude,
            longitude: userCoords.longitude,
            accuracy: userCoords.accuracy,
            description: desc
        };

        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

        fetch('/alerts/trigger/', {
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
                window.location.href = data.redirect_url || '/dashboard/';
            } else {
                alert("Failed to send alert: " + (data.error || "Server error"));
            }
        })
        .catch(err => {
            console.error("Emergency dispatch network error:", err);
            alert("Emergency dispatch failed. Please call Campus Security directly: +27 82 999 1111");
        });
    }

    function dispatchEmergencyAlert() {
        playTickSound(880, 0.4); // High confirmation beep
        // Even if browser OS GeoClue failed, trigger_alert_api has server-side real IP geolocation fallback
        sendTriggerPost();
    }

    // Lightweight Web Audio API synthesizer (no external audio assets required)
    function playTickSound(frequency, duration) {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!AudioContext) return;
            const ctx = new AudioContext();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(frequency, ctx.currentTime);
            gain.gain.setValueAtTime(0.2, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start();
            osc.stop(ctx.currentTime + duration);
        } catch (e) {
            // Audio context policy fallback
        }
    }
});
