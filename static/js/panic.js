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
    let userCoords = {
        latitude: null,
        longitude: null,
        accuracy: null
    };

    const ICON_GPS_LOCKED = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="22" y1="12" x2="18" y2="12"></line><line x1="6" y1="12" x2="2" y2="12"></line><line x1="12" y1="6" x2="12" y2="2"></line><line x1="12" y1="22" x2="12" y2="18"></line><circle cx="12" cy="12" r="3"></circle></svg>`;
    const ICON_GPS_FALLBACK = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`;

    function updateGeoStatusBanner(modeText, colorHex) {
        if (!geoStatusEl) return;
        const icon = colorHex === '#34d399' ? ICON_GPS_LOCKED : ICON_GPS_FALLBACK;
        const coordStr = (userCoords.latitude !== null && userCoords.longitude !== null)
            ? ` [${userCoords.latitude.toFixed(6)}, ${userCoords.longitude.toFixed(6)} &plusmn;${Math.round(userCoords.accuracy || 5)}m]`
            : '';
        geoStatusEl.innerHTML = `<span style="color: ${colorHex}; display: inline-flex; align-items: center; gap: 0.45rem; font-variant-numeric: tabular-nums;">${icon} ${modeText}${coordStr}</span>`;
    }

    function applyRealPositionFix(pos) {
        userCoords.latitude = pos.coords.latitude;
        userCoords.longitude = pos.coords.longitude;
        userCoords.accuracy = pos.coords.accuracy || 5.0;
        hasRealGpsFix = true;
        updateGeoStatusBanner('Live Hardware GPS Locked', '#34d399');
    }

    function handleGpsError(err) {
        console.warn("Geolocation error:", err);
        if (!hasRealGpsFix) {
            updateGeoStatusBanner('Please allow Browser Location Permission for real GPS', '#fbbf24');
        }
    }

    // 1. Acquire and continuously watch real hardware GPS from the user's device
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            applyRealPositionFix,
            handleGpsError,
            { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
        );
        navigator.geolocation.watchPosition(
            applyRealPositionFix,
            handleGpsError,
            { enableHighAccuracy: true, maximumAge: 0, timeout: 15000 }
        );
    } else {
        updateGeoStatusBanner('Geolocation API unsupported on this browser', '#f87171');
    }

    if (!panicBtn) return;

    // 2. User presses Panic Button -> Start 3-second abort window & refresh live GPS
    panicBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                applyRealPositionFix,
                () => {},
                { enableHighAccuracy: true, maximumAge: 0, timeout: 3000 }
            );
        }
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
        const desc = locationInput ? locationInput.value : "Live GPS Location";
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

        if (hasRealGpsFix && userCoords.latitude !== null && userCoords.longitude !== null) {
            sendTriggerPost();
        } else if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    applyRealPositionFix(pos);
                    sendTriggerPost();
                },
                () => {
                    alert("Location access is required to dispatch your real GPS coordinates. Please allow location access in your browser.");
                },
                { enableHighAccuracy: true, maximumAge: 0, timeout: 8000 }
            );
        } else {
            alert("Geolocation is not supported by your browser.");
        }
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
