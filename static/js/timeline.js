/**
 * University Panic Button System (UPBS)
 * timeline.js - Live Tracking Timeline Polling & Stage Visualization (Iteration 3)
 */

document.addEventListener('DOMContentLoaded', () => {
    const alertIdEl = document.getElementById('currentAlertId');
    if (!alertIdEl) return;

    const alertId = alertIdEl.value;
    if (!alertId) return;

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

        // Reset
        [step1, step2, step3, step4].forEach(s => s && s.classList.remove('completed', 'active'));

        if (status === 'SENT') {
            if (progressFill) progressFill.style.width = '0%';
            if (step1) step1.classList.add('active');
            if (statusText) statusText.innerHTML = "📡 Alert Sent to Campus Security dispatch queue...";
        } else if (status === 'RECEIVED') {
            if (progressFill) progressFill.style.width = '33%';
            if (step1) step1.classList.add('completed');
            if (step2) step2.classList.add('active');
            if (statusText) statusText.innerHTML = "👁️ Alert Acknowledged by Control Room Operator.";
        } else if (status === 'DISPATCHED') {
            if (progressFill) progressFill.style.width = '66%';
            if (step1) step1.classList.add('completed');
            if (step2) step2.classList.add('completed');
            if (step3) step3.classList.add('active');
            if (statusText) statusText.innerHTML = "🚨 Security Patrol Dispatched! Stay calm and remain in place.";
        } else if (status === 'RESOLVED') {
            if (progressFill) progressFill.style.width = '100%';
            if (step1) step1.classList.add('completed');
            if (step2) step2.classList.add('completed');
            if (step3) step3.classList.add('completed');
            if (step4) step4.classList.add('completed');
            if (statusText) statusText.innerHTML = "✅ Incident Resolved by Responding Officers.";
            if (feedbackPrompt) feedbackPrompt.style.display = 'block';
            clearInterval(interval);
        } else if (status === 'CANCELLED') {
            if (statusText) statusText.innerHTML = "⚪ Alert was Cancelled (False Alarm).";
            clearInterval(interval);
        }
    }
});
