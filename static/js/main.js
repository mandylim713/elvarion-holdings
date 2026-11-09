// Elvarion Holdings Interactive Engine

document.addEventListener('DOMContentLoaded', () => {
    initToastAutoDismiss();
    initRoiTickers();
    initLoanCalculators();
    initPublicRoiEstimator();
    initTabs();
    initCopyButtons();
});

// Toast Auto-dismiss
function initToastAutoDismiss() {
    const toasts = document.querySelectorAll('.toast-msg');
    toasts.forEach(t => {
        setTimeout(() => {
            t.style.opacity = '0';
            t.style.transform = 'translateX(100%)';
            t.style.transition = 'all 0.5s ease';
            setTimeout(() => t.remove(), 500);
        }, 5000);
    });
}

// Accurate ROI display: real server values, 2 decimals, refreshed every 30s (no ticking)
function initRoiTickers() {
    const totalEl = document.getElementById('live-total-roi');
    const cards = document.querySelectorAll('[data-investment-id]');
    if (!totalEl && cards.length === 0) return;
    const fmt = v => '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

    function syncRoi() {
        fetch('/api/realtime-roi/', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(data => {
                if (data.status !== 'success') return;
                if (totalEl) totalEl.innerText = fmt(data.total_accrued_roi);
                data.investments.forEach(inv => {
                    const el = document.getElementById('inv-roi-' + inv.id);
                    const prog = document.getElementById('inv-prog-' + inv.id);
                    if (el) el.innerText = fmt(inv.accrued_roi);
                    if (prog) prog.style.width = inv.progress_percentage + '%';
                });
                const u = document.getElementById('roi-updated');
                if (u) u.innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            })
            .catch(() => {});
    }
    setInterval(syncRoi, 30000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) syncRoi(); });
}

// Interactive Loan Calculator
function initLoanCalculators() {
    const loanAmountSlider = document.getElementById('loan-amount-slider');
    const loanAmountInput = document.getElementById('loan-amount-input');
    const termSelect = document.getElementById('loan-term-select');

    if (!loanAmountSlider && !loanAmountInput) return;

    function updateLoanDisplay() {
        const amount = parseFloat(loanAmountSlider ? loanAmountSlider.value : (loanAmountInput ? loanAmountInput.value : 300000)) || 300000;
        const term = parseInt(termSelect ? termSelect.value : 6) || 6;

        if (loanAmountInput && loanAmountSlider && document.activeElement === loanAmountSlider) {
            loanAmountInput.value = amount;
        } else if (loanAmountSlider && loanAmountInput && document.activeElement === loanAmountInput) {
            loanAmountSlider.value = amount;
        }

        // Calculate based on configured terms: 0.5% for 6m, 1.0% for 12m
        const monthlyRate = term === 6 ? 0.5 : 1.0;
        const totalInterestRate = (monthlyRate * term) / 100.0;
        const totalInterest = amount * totalInterestRate;
        const totalRepayable = amount + totalInterest;
        const monthlyInstallment = totalRepayable / term;

        const elAmountDisplay = document.getElementById('calc-loan-amount');
        const elInterestDisplay = document.getElementById('calc-loan-interest');
        const elInstallmentDisplay = document.getElementById('calc-loan-monthly');
        const elTotalDisplay = document.getElementById('calc-loan-total');
        const elRateLabel = document.getElementById('calc-loan-rate-label');

        if (elAmountDisplay) elAmountDisplay.innerText = `$${amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
        if (elInterestDisplay) elInterestDisplay.innerText = `$${totalInterest.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (elInstallmentDisplay) elInstallmentDisplay.innerText = `$${monthlyInstallment.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (elTotalDisplay) elTotalDisplay.innerText = `$${totalRepayable.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (elRateLabel) elRateLabel.innerText = `${monthlyRate}% / month (${(monthlyRate * term).toFixed(1)}% total)`;
    }

    if (loanAmountSlider) loanAmountSlider.addEventListener('input', updateLoanDisplay);
    if (loanAmountInput) loanAmountInput.addEventListener('input', updateLoanDisplay);
    if (termSelect) termSelect.addEventListener('change', updateLoanDisplay);

    updateLoanDisplay();
}

// Public Homepage Interactive ROI Estimator
function initPublicRoiEstimator() {
    const depositInput = document.getElementById('hero-calc-amount');
    const areaSelect = document.getElementById('hero-calc-area');
    const durationSelect = document.getElementById('hero-calc-duration');

    if (!depositInput || !areaSelect || !durationSelect) return;

    // Every plan pays a monthly rate; terms are 1, 3, 6 or 12 months. Rate shown is the sector's top monthly plan.
    const MONTHLY = { 'real-estate': 12.5, 'gold': 4.8, 'trust-fund': 8.5, 'money-market': 6.2, 'crypto': 8.0 };

    function calculateEstimatedYield() {
        const deposit = parseFloat(depositInput.value) || 25000;
        const rate = MONTHLY[areaSelect.value] || 6;
        const months = parseInt(durationSelect.value, 10) || 6;
        const totalRoiPct = rate * months;
        const totalProfit = deposit * (totalRoiPct / 100);
        const totalPayout = deposit + totalProfit;

        const profitEl = document.getElementById('hero-calc-profit');
        const payoutEl = document.getElementById('hero-calc-total');
        const rateLabelEl = document.getElementById('hero-calc-rate-badge');

        if (profitEl) profitEl.innerText = `+$${totalProfit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (payoutEl) payoutEl.innerText = `$${totalPayout.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (rateLabelEl) rateLabelEl.innerText = `${rate}% MONTHLY (${totalRoiPct.toFixed(1)}% TOTAL)`;
    }

    depositInput.addEventListener('input', calculateEstimatedYield);
    areaSelect.addEventListener('change', calculateEstimatedYield);
    durationSelect.addEventListener('change', calculateEstimatedYield);

    calculateEstimatedYield();
}

// Tabs
function initTabs() {
    const tabButtons = document.querySelectorAll('[data-tab-target]');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab-target');
            const parent = btn.closest('.tabs-container') || document;

            // Remove active from peers
            btn.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Hide all tab panes in this container
            parent.querySelectorAll('.tab-pane').forEach(pane => {
                pane.style.display = 'none';
                pane.classList.remove('active');
            });

            // Show target
            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.style.display = 'block';
                targetPane.classList.add('active');
            }
        });
    });
}

// Copy to Clipboard with Feedback
function initCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const textToCopy = btn.getAttribute('data-clipboard-text');
            if (textToCopy) {
                navigator.clipboard.writeText(textToCopy).then(() => {
                    const originalHtml = btn.innerHTML;
                    btn.innerHTML = `<i class="fas fa-check text-emerald"></i> Copied!`;
                    btn.classList.add('btn-emerald');
                    setTimeout(() => {
                        btn.innerHTML = originalHtml;
                        btn.classList.remove('btn-emerald');
                    }, 2000);
                });
            }
        });
    });
}

// Modal open/close helpers
function openModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.add('open');
}

function closeModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.remove('open');
}

// Quick fill for Investment modal
let _planMonthlyRate = 0;
function updateInvestQuote() {
    const amt = parseFloat((document.getElementById('invest-amount-input') || {}).value) || 0;
    const t = document.querySelector('#invest-terms input[name=term]:checked');
    const pctEl = document.getElementById('invest-quote-pct');
    const totEl = document.getElementById('invest-quote-total');
    if (!t || !pctEl || !totEl) return;
    const months = parseInt(t.value, 10);
    const pct = _planMonthlyRate * months;
    pctEl.innerText = `${pct.toFixed(2).replace(/\.?0+$/, '')}%  (+$${(amt * pct / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })})`;
    totEl.innerText = `$${(amt * (1 + pct / 100)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
document.addEventListener('change', (e) => { if (e.target.closest && e.target.closest('#invest-terms')) updateInvestQuote(); });
document.addEventListener('input', (e) => { if (e.target.id === 'invest-amount-input') updateInvestQuote(); });

function selectPlanForInvest(planId, planTitle, areaName, minDeposit, maxDeposit, monthlyRate) {
    const modal = document.getElementById('investModal');
    if (!modal) return;

    const inputPlanId = document.getElementById('invest-plan-id');
    const labelPlan = document.getElementById('invest-modal-title');
    const labelArea = document.getElementById('invest-modal-area');
    const labelRoi = document.getElementById('invest-modal-roi');
    const inputAmount = document.getElementById('invest-amount-input');
    const minMaxLabel = document.getElementById('invest-min-max-label');

    if (inputPlanId) inputPlanId.value = planId;
    if (labelPlan) labelPlan.innerText = planTitle;
    if (labelArea) labelArea.innerText = areaName;
    _planMonthlyRate = parseFloat(monthlyRate) || 0;
    if (labelRoi) labelRoi.innerText = `${_planMonthlyRate}% per month`;
    if (inputAmount) {
        inputAmount.value = minDeposit;
        inputAmount.min = minDeposit;
        inputAmount.max = maxDeposit;
    }
    if (minMaxLabel) minMaxLabel.innerText = `Range: $${parseFloat(minDeposit).toLocaleString()} - $${parseFloat(maxDeposit).toLocaleString()}`;

    updateInvestQuote();
    openModal('investModal');
}
