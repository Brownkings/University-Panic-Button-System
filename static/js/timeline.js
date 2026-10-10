/**
 * University Panic Button System (UPBS)
 * timeline.js - Live Incident Telemetry Polling & 4-Stage Pipeline Visualization
 */

document.addEventListener('DOMContentLoaded', () => {
    const alertIdEl = document.getElementById('currentAlertId');
    if (!alertIdEl) return;

    const alertId = alertIdEl.value;
    if (!alertId) return;

    const SVG_CHECK = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"></polyline></svg>`;

    const SVG_RADIO = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #60a5fa; flex-shrink: 0;" aria-hidden="true"><circle cx="12" cy="12" r="2"></circle><path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14"></path></svg>`;
    const SVG_EYE = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #fbbf24; flex-shrink: 0;" aria-hidden="true"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
    const SVG_SHIELD_ALERT = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #f87171; flex-shrink: 0;" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    const SVG_CHECK_CIRCLE = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #34d399; flex-shrink: 0;" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
    const SVG_X_CIRCLE = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #94a3b8; flex-shrink: 0;" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`;

    function setStepState(stepEl, stageNum, state) {
        if (!stepEl) return;
        stepEl.classList.remove('completed', 'active');
        if (state) {
            stepEl.classList.add(state);
        }
        const nodeEl = stepEl.querySelector('.timeline-node');
        if (nodeEl) {
            nodeEl.innerHTML = state === 'completed' ? SVG_CHECK : String(stageNum);
        }
    }

    function checkStatus() {
        fetch(`/alerts/api/status/${alertId}/`)
            .then(res => res.json())
            .then(data => {
                if (data.status) {
                    updateTimelineUI(data.status);
                }
            })
            .catch(err => console.error("Error polling timeline status:", err));
    }

    checkStatus();
    const interval = setInterval(checkStatus, 3000);

    function updateTimelineUI(status) {
        const progressFill = document.getElementById('timelineFill');
        const step1 = document.getElementById('step-sent');
        const step2 = document.getElementById('step-received');
        const step3 = document.getElementById('step-dispatched');
        const step4 = document.getElementById('step-resolved');
        const statusText = document.getElementById('statusAnnouncement');
        const feedbackPrompt = document.getElementById('feedbackPrompt');

        if (status === 'SENT') {
            if (progressFill) progressFill.style.width = '0%';
            setStepState(step1, 1, 'active');
            setStepState(step2, 2, '');
            setStepState(step3, 3, '');
            setStepState(step4, 4, '');
            if (statusText) {
                statusText.innerHTML = `${SVG_RADIO}<span>Alert transmitted to Campus Security CAD dispatch queue...</span>`;
            }
        } else if (status === 'RECEIVED') {
            if (progressFill) progressFill.style.width = '33%';
            setStepState(step1, 1, 'completed');
            setStepState(step2, 2, 'active');
            setStepState(step3, 3, '');
            setStepState(step4, 4, '');
            if (statusText) {
                statusText.innerHTML = `${SVG_EYE}<span>Alert acknowledged by Control Room Operator.</span>`;
            }
        } else if (status === 'DISPATCHED') {
            if (progressFill) progressFill.style.width = '66%';
            setStepState(step1, 1, 'completed');
            setStepState(step2, 2, 'completed');
            setStepState(step3, 3, 'active');
            setStepState(step4, 4, '');
            if (statusText) {
                statusText.innerHTML = `${SVG_SHIELD_ALERT}<span>Security Patrol Unit Dispatched - Remain in place if safe.</span>`;
            }
        } else if (status === 'RESOLVED') {
            if (progressFill) progressFill.style.width = '100%';
            setStepState(step1, 1, 'completed');
            setStepState(step2, 2, 'completed');
            setStepState(step3, 3, 'completed');
            setStepState(step4, 4, 'completed');
            if (statusText) {
                statusText.innerHTML = `${SVG_CHECK_CIRCLE}<span>Incident resolved and logged by responding officers.</span>`;
            }
            if (feedbackPrompt) feedbackPrompt.style.display = 'block';
            clearInterval(interval);
        } else if (status === 'CANCELLED') {
            setStepState(step1, 1, '');
            setStepState(step2, 2, '');
            setStepState(step3, 3, '');
            setStepState(step4, 4, '');
            if (statusText) {
                statusText.innerHTML = `${SVG_X_CIRCLE}<span>Alert cancelled (False Alarm logged).</span>`;
            }
            clearInterval(interval);
        }
    }
});
