/* =========================================================
   auth.js — Elvarion Holdings auth portals
   (login vault sign-in, register wizard, directorate terminal)
   Moved out of inline <script> blocks during the design-system
   refactor. Step visibility is class-driven (.step-content.active),
   never by writing inline display on the elements.
   ========================================================= */

/* ---------- Password reveal toggle (all auth pages) ---------- */
function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    const icon = btn.querySelector('i');
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
    }
}

/* ---------- Concierge recovery modal (login) ---------- */
function openConciergeModal() {
    const m = document.getElementById('conciergeModal');
    if (m) m.classList.add('open');
}

function closeConciergeModal() {
    const m = document.getElementById('conciergeModal');
    if (m) m.classList.remove('open');
}

// Allow closing modal by clicking outside content or pressing Escape
document.addEventListener('DOMContentLoaded', function() {
    const m = document.getElementById('conciergeModal');
    if (m) {
        m.addEventListener('click', function(e) {
            if (e.target === m) closeConciergeModal();
        });
    }
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeConciergeModal();
    });
});

/* ---------- Register wizard ---------- */
function selectAccountType(type, element) {
    document.querySelectorAll('.type-option-card').forEach(el => el.classList.remove('selected'));
    element.classList.add('selected');
    document.getElementById('selected-account-type').value = type;
}

function switchStep(stepNum) {
    document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.step-indicator').forEach(el => el.classList.remove('active'));

    const activeContent = document.getElementById(`step-content-${stepNum}`);
    const activeTab = document.getElementById(`step-tab-${stepNum}`);
    if (activeContent) activeContent.classList.add('active');
    if (activeTab) activeTab.classList.add('active');
}

function validateAndGoStep(nextStep) {
    if (nextStep === 2) {
        const fullname = document.getElementById('reg-fullname').value.trim();
        const email = document.getElementById('reg-email').value.trim();
        if (!fullname || !email) {
            alert('Please provide your Full Legal Name and Email before proceeding.');
            return;
        }
    } else if (nextStep === 3) {
        const username = document.getElementById('reg-username').value.trim();
        const password = document.getElementById('reg-password').value;
        const confirm = document.getElementById('reg-confirm').value;

        if (!username || !password) {
            alert('Please choose a username and enter a password.');
            return;
        }
        if (password.length < 6) {
            alert('Password must be at least 6 characters.');
            return;
        }
        if (password !== confirm) {
            alert('Passwords do not match.');
            return;
        }
    }
    switchStep(nextStep);
}

/* ---------- Password strength meter & match feedback ---------- */
function checkPasswordStrength() {
    const password = document.getElementById('reg-password').value;
    const bar = document.getElementById('strength-bar');
    const label = document.getElementById('strength-label');

    bar.className = 'strength-meter-bar';
    if (!password) {
        label.innerText = 'Password strength: Empty';
        label.style.color = 'var(--text-dim)';
        return;
    }

    let score = 0;
    if (password.length >= 6) score++;
    if (password.length >= 10) score++;
    if (/[A-Z]/.test(password) && /[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;

    if (score <= 1) {
        bar.classList.add('weak');
        label.innerText = 'Strength: Basic';
        label.style.color = 'var(--danger-accent)';
    } else if (score <= 3) {
        bar.classList.add('medium');
        label.innerText = 'Strength: Moderate';
        label.style.color = 'var(--gold-primary)';
    } else {
        bar.classList.add('strong');
        label.innerText = 'Strength: Sovereign-Grade';
        label.style.color = 'var(--emerald-accent)';
    }
    checkPasswordMatch();
}

function checkPasswordMatch() {
    const password = document.getElementById('reg-password').value;
    const confirm = document.getElementById('reg-confirm').value;
    const feedback = document.getElementById('match-feedback');

    if (!confirm) {
        feedback.innerText = '';
        return;
    }
    if (password === confirm) {
        feedback.innerText = '\u2713 Passwords match';
        feedback.style.color = 'var(--emerald-accent)';
    } else {
        feedback.innerText = '\u2715 Passwords do not match';
        feedback.style.color = 'var(--danger-accent)';
    }
}
