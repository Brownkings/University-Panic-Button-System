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
                }
            })
            .catch(() => {});
    }

    function applyRealCoordinates(lat, lng, acc, labelText, preResolvedAddress) {
        userCoords.latitude = Number(lat);
        userCoords.longitude = Number(lng);
        userCoords.accuracy = Number(acc || 10.0);
        hasRealGpsFix = true;

        if (preResolvedAddress) {
            setLiveAddressOption(preResolvedAddress);
            updateGeoStatusBanner(`Real Location Locked: ${preResolvedAddress}`, '#34d399');
        } else {
            updateGeoStatusBanner(labelText || 'Live GPS Locked', '#34d399');
            reverseGeocodeRealCoords(userCoords.latitude, userCoords.longitude, userCoords.accuracy);
        }
    }

    function resolveViaNetworkGeoFallback() {
        if (hasRealGpsFix) return;
        // Fallback when Linux/desktop browser OS GeoClue returns POSITION_UNAVAILABLE despite permission granted
        fetch('https://ipwho.is/')
            .then(res => res.json())
            .then(data => {
                if (!hasRealGpsFix && data && data.latitude && data.longitude) {
                    const addrParts = [data.city, data.region].filter(Boolean).join(', ');
                    applyRealCoordinates(data.latitude, data.longitude, 25.0, 'Live Network Geolocation Locked', addrParts || null);
                    reverseGeocodeRealCoords(Number(data.latitude), Number(data.longitude), 25.0);
                } else if (!hasRealGpsFix) {
                    throw new Error('Primary GeoIP incomplete');
                }
            })
            .catch(() => {
                fetch('/alerts/api/resolve-location/')
                    .then(res => res.json())
                    .then(data => {
                        if (!hasRealGpsFix && data && data.success) {
                            applyRealCoordinates(data.latitude, data.longitude, data.accuracy || 25.0, 'Live Network Geolocation Locked', data.address);
                        }
                    })
                    .catch(err => {
                        console.warn("All geolocation providers failed:", err);
                        if (!hasRealGpsFix) {
                            updateGeoStatusBanner('Unable to lock GPS — check browser Location settings', '#fbbf24');
                        }
                    });
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
