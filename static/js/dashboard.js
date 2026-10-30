// Elvarion Holdings — Dashboard page engine
// Extracted from the inline <script> of templates/dashboard/index.html.
// The dynamic custody addresses are server-rendered by
// templates/partials/dashboard/_gateway_config.html into
// window.DASH_GATEWAY_ADDRESSES before this file loads.

// Gateway configurations dictionary
const GATEWAY_DEFINITIONS = {
    'USDT_TRC20': {
        name: 'USDT (TRC-20)',
        badge: 'TRON NETWORK (TRC-20)',
        title: 'USDT Custody Gateway',
        rate: 1.0,
        rateLabel: '1 USDT ≈ $1.00 USD',
        unit: 'USDT',
        isWire: false
    },
    'BTC': {
        name: 'Bitcoin (BTC)',
        badge: 'BITCOIN NATIVE SEGWIT',
        title: 'Bitcoin Bullion Vault Gateway',
        rate: 0.0000106,
        rateLabel: '1 BTC ≈ $94,300.00 USD',
        unit: 'BTC',
        isWire: false
    },
    'USDT_ERC20': {
        name: 'USDT (ERC-20)',
        badge: 'ETHEREUM MAINNET (ERC-20)',
        title: 'USDT Smart Contract Gateway',
        rate: 1.0,
        rateLabel: '1 USDT ≈ $1.00 USD',
        unit: 'USDT',
        isWire: false
    },
    'ETH': {
        name: 'Ethereum (ETH)',
        badge: 'ETHEREUM NATIVE / ERC-20',
        title: 'Ethereum Smart Liquidity Gateway',
        rate: 0.000305,
        rateLabel: '1 ETH ≈ $3,280.00 USD',
        unit: 'ETH',
        isWire: false
    },
    'BANK_WIRE': {
        name: 'International Bank Wire',
        badge: 'JPMORGAN CHASE PRIVATE BANK',
        title: 'Institutional FedWire / SWIFT Coordinates',
        rate: 1.0,
        rateLabel: 'Segregated Treasury Wire',
        unit: 'USD',
        isWire: true
    }
};

const GATEWAY_ADDRESSES = window.DASH_GATEWAY_ADDRESSES || {};
const GATEWAYS = {};
Object.keys(GATEWAY_DEFINITIONS).forEach((key) => {
    GATEWAYS[key] = Object.assign(
        { address: GATEWAY_ADDRESSES[key] || '' },
        GATEWAY_DEFINITIONS[key]
    );
});

let currentGatewayKey = 'USDT_TRC20';

function selectDepositGateway(gwKey, element) {
    currentGatewayKey = gwKey;
    document.querySelectorAll('.crypto-tab-card').forEach(el => el.classList.remove('active'));
    if (element) element.classList.add('active');

    const gw = GATEWAYS[gwKey];
    if (!gw) return;

    // Update Gateway card view
    const elBadge = document.getElementById('gw-badge');
    const elTitle = document.getElementById('gw-title');
    const elAddr = document.getElementById('gw-address-text');
    const elCopy = document.getElementById('gw-copy-btn');
    const qrWrap = document.getElementById('crypto-qr-wrapper');
    const addrWrap = document.getElementById('crypto-address-wrapper');
    const wireWrap = document.getElementById('bank-wire-wrapper');

    if (elBadge) elBadge.innerText = gw.badge;
    if (elTitle) elTitle.innerText = gw.title;

    if (gw.isWire) {
        if (qrWrap) qrWrap.style.display = 'none';
        if (addrWrap) addrWrap.style.display = 'none';
        if (wireWrap) wireWrap.style.display = 'block';
    } else {
        if (qrWrap) qrWrap.style.display = 'block';
        if (addrWrap) addrWrap.style.display = 'block';
        if (wireWrap) wireWrap.style.display = 'none';
        if (elAddr) elAddr.innerText = gw.address;
        if (elCopy) elCopy.setAttribute('data-clipboard-text', gw.address);
        renderInlineQRCode(gw.address);
    }

    // Update Form fields
    const formMethod = document.getElementById('form-deposit-method');
    const formMethodLabel = document.getElementById('form-selected-method-label');
    const formBadge = document.getElementById('form-selected-badge');
    if (formMethod) formMethod.value = gwKey;
    if (formMethodLabel) formMethodLabel.innerText = gw.name;
    if (formBadge) formBadge.innerText = gw.isWire ? 'WIRE AUDIT' : 'BLOCKCHAIN AUDIT';

    updateCryptoConversion();
}

function renderInlineQRCode(text) {
    const container = document.getElementById('qr-code-display');
    if (!container) return;

    // Generate clean SVG visual QR simulation grid
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
        hash = ((hash << 5) - hash) + text.charCodeAt(i);
        hash |= 0;
    }

    // 21x21 QR matrix
    const size = 21;
    let rects = '';
    const cellSize = 180 / size;

    for (let r = 0; r < size; r++) {
        for (let c = 0; c < size; c++) {
            // Finder patterns in 3 corners
            const isTopLeftFinder = (r < 7 && c < 7);
            const isTopRightFinder = (r < 7 && c >= size - 7);
            const isBottomLeftFinder = (r >= size - 7 && c < 7);

            let isBlack = false;
            if (isTopLeftFinder) {
                isBlack = (r === 0 || r === 6 || c === 0 || c === 6 || (r >= 2 && r <= 4 && c >= 2 && c <= 4));
            } else if (isTopRightFinder) {
                const cAdj = c - (size - 7);
                isBlack = (r === 0 || r === 6 || cAdj === 0 || cAdj === 6 || (r >= 2 && r <= 4 && cAdj >= 2 && cAdj <= 4));
            } else if (isBottomLeftFinder) {
                const rAdj = r - (size - 7);
                isBlack = (rAdj === 0 || rAdj === 6 || c === 0 || c === 6 || (rAdj >= 2 && rAdj <= 4 && c >= 2 && c <= 4));
            } else {
                // Pseudo pseudo-data bits based on text hash
                const bitVal = Math.sin((r * 13) + (c * 29) + hash);
                isBlack = bitVal > 0.1;
            }

            if (isBlack) {
                rects += `<rect x="${c * cellSize + 10}" y="${r * cellSize + 10}" width="${cellSize}" height="${cellSize}" fill="#0c1222" />`;
            }
        }
    }

    container.innerHTML = `
        <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" style="width:100%; height:100%;">
            <rect width="200" height="200" fill="#ffffff" rx="6" />
            ${rects}
        </svg>
    `;
}

function updateCryptoConversion() {
    const amountInput = document.getElementById('deposit-amount-input');
    const rateLabel = document.getElementById('calc-crypto-rate');
    const outputEl = document.getElementById('calc-crypto-output');
    if (!amountInput || !outputEl) return;

    const amount = parseFloat(amountInput.value) || 0;
    const gw = GATEWAYS[currentGatewayKey] || GATEWAYS['USDT_TRC20'];

    if (rateLabel) rateLabel.innerText = gw.rateLabel;

    if (gw.unit === 'BTC') {
        const cryptoUnits = amount * gw.rate;
        outputEl.innerText = `${cryptoUnits.toFixed(6)} BTC`;
    } else if (gw.unit === 'ETH') {
        const cryptoUnits = amount * gw.rate;
        outputEl.innerText = `${cryptoUnits.toFixed(4)} ETH`;
    } else {
        outputEl.innerText = `${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${gw.unit}`;
    }
}

function setPresetDeposit(amt) {
    const input = document.getElementById('deposit-amount-input');
    if (input) {
        input.value = amt;
        updateCryptoConversion();
    }
}

function handleReceiptSelected(input) {
    const label = document.getElementById('receipt-filename');
    if (input.files && input.files[0]) {
        label.innerText = `✓ Selected: ${input.files[0].name} (${(input.files[0].size / 1024).toFixed(1)} KB)`;
        label.style.display = 'block';
    }
}

function handleDocSelected(input, labelId) {
    const label = document.getElementById(labelId);
    if (input.files && input.files[0]) {
        label.innerText = `✓ Attached: ${input.files[0].name}`;
        label.style.display = 'block';
    }
}

function autofillDemoKYC() {
    document.getElementById('kyc-fullname').value = 'Lord Alexander Sterling';
    document.getElementById('kyc-dob').value = '1984-09-22';
    document.getElementById('kyc-country').value = 'United Kingdom';
    document.getElementById('kyc-address').value = '14 Grosvenor Square, Mayfair';
    document.getElementById('kyc-city').value = 'London';
    document.getElementById('kyc-postal').value = 'W1K 6HN';
    document.getElementById('kyc-idtype').value = 'passport';
    document.getElementById('kyc-idnumber').value = 'GB849028190';
}

function switchDashboardTab(tabId) {
    const btn = document.querySelector(`[data-tab-target="${tabId}"]`);
    if (btn) btn.click();
}

function recalcUserLoan() {
    const inputAmount = document.getElementById('user-loan-amount');
    const selectTerm = document.getElementById('user-loan-term');
    if (!inputAmount || !selectTerm) return;

    const amount = parseFloat(inputAmount.value) || 0;
    const term = parseInt(selectTerm.value) || 6;
    const rate = term === 6 ? 0.5 : 1.0;

    const totalInterest = amount * (rate / 100.0) * term;
    const totalRepayable = amount + totalInterest;
    const monthly = term > 0 ? (totalRepayable / term) : 0;

    const elP = document.getElementById('schedule-principal');
    const elR = document.getElementById('schedule-rate');
    const elI = document.getElementById('schedule-interest');
    const elT = document.getElementById('schedule-total');
    const elM = document.getElementById('schedule-monthly');

    if (elP) elP.innerText = `$${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (elR) elR.innerText = `${rate}% / month (${(rate * term).toFixed(1)}% total)`;
    if (elI) elI.innerText = `$${totalInterest.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (elT) elT.innerText = `$${totalRepayable.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (elM) elM.innerText = `$${monthly.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

document.addEventListener('DOMContentLoaded', () => {
    // Paint maturity bars with the server-rendered starting width
    // (the live ledger sync in main.js keeps style.width updated afterwards).
    document.querySelectorAll('.dash-progress-fill[data-initial-progress]').forEach(el => {
        el.style.width = `${parseFloat(el.getAttribute('data-initial-progress')) || 0}%`;
    });

    recalcUserLoan();
    renderInlineQRCode(GATEWAYS['USDT_TRC20'].address);
    updateCryptoConversion();
});
