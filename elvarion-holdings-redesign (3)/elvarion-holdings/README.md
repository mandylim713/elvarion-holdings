# Elvarion Holdings (`elvarionholdings.com`)
### Institutional Wealth Management & Tiered Private Credit Platform

Elvarion Holdings is a multi-asset private equity, wealth management, and private credit web application built with Python & Django.

---

## Key Features

### 1. Multi-Sector Investment Architecture
- **Real-Estate Investment**: Commercial REITs, prime logistics syndicates, and luxury developments.
- **Gold Investment**: Physical vaulted LBMA-grade bullion reserve and arbitrage yields.
- **Trust Fund Investment**: Multi-generational fiduciary trusts and sovereign high-watermark endowment funds.
- **Money Market Mutual Funds**: Sovereign Treasury bills, commercial paper, and overnight repurchase liquidity.

### 2. Flexible Admin Duration & ROI Controls
- Administrators can dynamically configure investment durations on each area/plan:
  - **Daily**
  - **Weekly**
  - **Monthly**
  - **Yearly**
- Customize ROI percentages, minimum/maximum deposit limits, and capital return guarantees.

### 3. Client Dashboard & Live Reading ROI
- Simultaneous investment allocations across multiple distinct sectors.
- Real-time high-precision ROI accrual reader updating micro-fractions on client dashboards in real-time.

### 4. Private Credit & Loan Session
- Dynamic borrowing limits calibrated to verified cumulative deposits:
  - **$25,000 Deposit** &rarr; Eligible for **$300,000 – $799,000**
  - **$50,000 Deposit** &rarr; Eligible for **$800,000 – $1,000,000**
  - **$100,000 Deposit** &rarr; Eligible for **$2,000,000 – $4,990,000**
  - **$150,000 Deposit** &rarr; Eligible for **$5,000,000**
- Configurable repayment terms:
  - **6 Months Repayment**: 0.5% interest per month (3.0% total)
  - **12 Months Repayment**: 1.0% interest per month (12.0% total)
- Amortization calculator and Director approval/decline review workflow.

### 5. Hybrid Deposit & Treasury Gateways
- Multi-cryptocurrency support: Bitcoin (BTC), USDT (TRC-20 & ERC-20), and Ethereum (ETH).
- Segregated institutional bank wire coordinates (JPMorgan Chase Private Bank).
- Deposit proof upload and transaction verification workflow.

---

## Local Setup & Quickstart

```bash
# 1. Activate virtual environment
venv\Scripts\activate   # Windows
# or source venv/bin/activate  # Linux/macOS

# 2. Run migrations
python manage.py migrate

# 3. Seed demo data (Areas, Plans, Loan Tiers, Test Accounts)
python seed_data.py

# 4. Start local development server
python manage.py runserver
```

---

## Ready-to-Test Credentials

- **VIP Investor Account**:
  - Username: `vip_investor`
  - Password: `Investor@12345`
  - *Preloaded with $75,000 deposit (unlocks Gold Executive $800k–$1M Loan Tier) and 3 active investments.*
- **Director Admin Account**:
  - Username: `admin`
  - Password: `Admin@12345`
  - Access to: `/management/` and `/admin/`
