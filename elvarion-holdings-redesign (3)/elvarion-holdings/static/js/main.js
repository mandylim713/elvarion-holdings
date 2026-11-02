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

// Live High-Frequency ROI Pulsing Ticker
let liveRoiInterval = null;
function initRoiTickers() {
    const totalTickerEl = document.getElementById('live-total-roi');
    const investmentCards = document.querySelectorAll('[data-investment-id]');

    if (!totalTickerEl && investmentCards.length === 0) return;

    // Periodically sync with backend every 8 seconds
    function syncLiveRoi() {
        fetch('/api/realtime-roi/')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    if (totalTickerEl) {
                        totalTickerEl.setAttribute('data-target-value', data.total_accrued_roi);
                    }
                    data.investments.forEach(inv => {
                        const el = document.getElementById(`inv-roi-${inv.id}`);
                        const prog = document.getElementById(`inv-prog-${inv.id}`);
                        if (el) el.setAttribute('data-target-value', inv.accrued_roi);
                        if (prog) prog.style.width = `${inv.progress_percentage}%`;
                    });
                }
            })
            .catch(err => console.debug('Sync interval note:', err));
    }

    // Micro-ticker for high precision visual reading (ticks up fractions every 120ms)
    liveRoiInterval = setInterval(() => {
        if (totalTickerEl) {
            let current = parseFloat(totalTickerEl.innerText.replace(/[^0-9.-]+/g, "")) || 0;
            let target = parseFloat(totalTickerEl.getAttribute('data-target-value')) || current;
            if (target > current) {
                current += Math.max(0.0001, (target - current) * 0.1);
            } else {
                current += 0.0001; // subtle live drift
            }
            totalTickerEl.innerText = `$${current.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;
        }

        investmentCards.forEach(card => {
            const id = card.getAttribute('data-investment-id');
            const roiEl = document.getElementById(`inv-roi-${id}`);
            if (roiEl) {
                let current = parseFloat(roiEl.innerText.replace(/[^0-9.-]+/g, "")) || 0;
                let target = parseFloat(roiEl.getAttribute('data-target-value')) || current;
                if (target > current) {
                    current += Math.max(0.0001, (target - current) * 0.1);
                } else {
                    current += 0.0001;
                }
                roiEl.innerText = `$${current.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 })}`;
            }
        });
    }, 120);

    // Initial sync
    syncLiveRoi();
    setInterval(syncLiveRoi, 8000);
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

    function calculateEstimatedYield() {
        const deposit = parseFloat(depositInput.value) || 25000;
        const selectedArea = areaSelect.value;
        const durationType = durationSelect.value;

        // Estimated returns based on areas
        let rate = 12.5; // default monthly %
        let termUnits = 6;
        let unitName = 'Months';

        if (selectedArea === 'real-estate') {
            if (durationType === 'daily') { rate = 0.8; termUnits = 30; unitName = 'Days'; }
            else if (durationType === 'weekly') { rate = 3.2; termUnits = 12; unitName = 'Weeks'; }
            else if (durationType === 'monthly') { rate = 12.5; termUnits = 6; unitName = 'Months'; }
            else { rate = 32.0; termUnits = 1; unitName = 'Year'; }
        } else if (selectedArea === 'gold') {
            if (durationType === 'daily') { rate = 1.1; termUnits = 30; unitName = 'Days'; }
            else if (durationType === 'weekly') { rate = 2.4; termUnits = 10; unitName = 'Weeks'; }
            else if (durationType === 'monthly') { rate = 4.8; termUnits = 3; unitName = 'Months'; }
            else { rate = 24.0; termUnits = 1; unitName = 'Year'; }
        } else if (selectedArea === 'trust-fund') {
            if (durationType === 'weekly') { rate = 2.1; termUnits = 16; unitName = 'Weeks'; }
            else if (durationType === 'monthly') { rate = 8.5; termUnits = 12; unitName = 'Months'; }
            else { rate = 45.0; termUnits = 2; unitName = 'Years'; }
        } else { // money market
            if (durationType === 'daily') { rate = 0.65; termUnits = 14; unitName = 'Days'; }
            else if (durationType === 'monthly') { rate = 6.2; termUnits = 6; unitName = 'Months'; }
            else { rate = 18.5; termUnits = 1; unitName = 'Year'; }
        }

        const totalRoiPct = (rate * termUnits);
        const totalProfit = deposit * (totalRoiPct / 100);
        const totalPayout = deposit + totalProfit;

        const profitEl = document.getElementById('hero-calc-profit');
        const payoutEl = document.getElementById('hero-calc-total');
        const rateLabelEl = document.getElementById('hero-calc-rate-badge');

        if (profitEl) profitEl.innerText = `+$${totalProfit.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (payoutEl) payoutEl.innerText = `$${totalPayout.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        if (rateLabelEl) rateLabelEl.innerText = `${rate}% ${durationType.toUpperCase()} (${totalRoiPct.toFixed(1)}% TOTAL)`;
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
function selectPlanForInvest(planId, planTitle, areaName, minDeposit, maxDeposit, roiDisplay) {
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
    if (labelRoi) labelRoi.innerText = roiDisplay;
    if (inputAmount) {
        inputAmount.value = minDeposit;
        inputAmount.min = minDeposit;
        inputAmount.max = maxDeposit;
    }
    if (minMaxLabel) minMaxLabel.innerText = `Range: $${parseFloat(minDeposit).toLocaleString()} - $${parseFloat(maxDeposit).toLocaleString()}`;

    openModal('investModal');
}
