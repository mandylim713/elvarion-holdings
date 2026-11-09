"""Automatic jobs: pay out investment ROI, mature plans, settle Quick Trades.

Every function is safe to run repeatedly and from several processes at once: each
row is locked inside a transaction and the amount to pay is worked out after the lock.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN

from django.db import transaction
from django.utils import timezone

from .models import UserInvestment, UserProfile, Transaction, OptionTrade, CompanySetting
from .market import quote

CENT = Decimal('0.01')
MAX_OPEN_OPTIONS = 10
OPTION_DURATIONS = (30, 60, 300, 900, 3600)


def _target_roi(inv, now):
    if now >= inv.end_date:
        return inv.total_projected_roi
    total = (inv.end_date - inv.start_date).total_seconds()
    if total <= 0:
        return Decimal('0')
    frac = max(0.0, min(1.0, (now - inv.start_date).total_seconds() / total))
    return (inv.total_projected_roi * Decimal(str(frac))).quantize(Decimal('0.0001'))


def accrue_investment(inv_id, now=None):
    """Pay out the ROI earned since the last run; mature the plan when its term ends."""
    now = now or timezone.now()
    with transaction.atomic():
        inv = UserInvestment.objects.select_for_update().select_related('plan', 'user').get(id=inv_id)
        if inv.status != 'active':
            return Decimal('0')
        target = _target_roi(inv, now)
        due = (target - inv.accumulated_roi).quantize(CENT, rounding=ROUND_DOWN)
        matured = now >= inv.end_date
        if due <= 0 and not matured:
            return Decimal('0')
        profile = UserProfile.objects.select_for_update().get(user=inv.user)
        if due > 0:
            profile.wallet_balance += due
            profile.total_roi_earned += due
            ref = f"roi-{inv.reference_id}-{now:%Y%m%d}"
            txn, created = Transaction.objects.get_or_create(
                reference=ref,
                defaults=dict(user=inv.user, txn_type='roi_payout', amount=due, is_credit=True,
                              description=f"ROI paid - {inv.plan.title}"[:255]))
            if not created:
                txn.amount += due
                txn.save(update_fields=['amount'])
            inv.accumulated_roi += due
        inv.last_roi_update = now
        if matured:
            inv.accumulated_roi = inv.total_projected_roi
            inv.status = 'completed'
            if inv.plan.capital_returned:
                profile.wallet_balance += inv.amount
                Transaction.objects.get_or_create(
                    reference=f"cap-{inv.reference_id}",
                    defaults=dict(user=inv.user, txn_type='capital_return', amount=inv.amount, is_credit=True,
                                  description=f"Capital returned - {inv.plan.title}"[:255]))
        profile.save()
        inv.save()
        return due


def accrue_all(now=None):
    n = 0
    for inv_id in UserInvestment.objects.filter(status='active').values_list('id', flat=True):
        try:
            if accrue_investment(inv_id, now) > 0:
                n += 1
        except UserInvestment.DoesNotExist:
            pass
    return n


def settle_option(opt_id, now=None):
    now = now or timezone.now()
    with transaction.atomic():
        opt = OptionTrade.objects.select_for_update().select_related('asset', 'user').get(id=opt_id)
        if opt.status != 'open' or opt.expires_at > now:
            return None
        exit_price = quote(opt.asset, wait=True)[0]
        opt.exit_price = exit_price
        profile = UserProfile.objects.select_for_update().get(user=opt.user)
        if exit_price == opt.entry_price:
            opt.status, opt.result_amount = 'draw', Decimal('0.00')
            profit = Decimal('0.00')
        elif (exit_price > opt.entry_price) == (opt.direction == 'up'):
            opt.status = 'won'
            profit = (opt.stake * opt.payout_pct / Decimal('100')).quantize(CENT)
            opt.result_amount = profit
        else:
            opt.status, opt.result_amount = 'lost', -opt.stake
            profit = None
        if profit is not None:
            back = opt.stake + profit
            profile.wallet_balance += back
            profile.save()
            Transaction.objects.create(
                user=opt.user, txn_type='option', amount=back, is_credit=True,
                description=(f"Quick Trade won +${profit:,.2f} - {opt.asset.symbol} {opt.direction}" if profit
                             else f"Quick Trade refunded - {opt.asset.symbol}")[:255])
        opt.save()
        return opt


def settle_options(user=None, now=None):
    now = now or timezone.now()
    qs = OptionTrade.objects.filter(status='open', expires_at__lte=now)
    if user is not None:
        qs = qs.filter(user=user)
    n = 0
    for oid in qs.values_list('id', flat=True):
        if settle_option(oid, now):
            n += 1
    return n


def run_all_jobs():
    """One full pass - used by the scheduler, the run_jobs command and the ping URL."""
    from . import market
    market.refresh()
    paid = accrue_all()
    settled = settle_options()
    s = CompanySetting.get_settings()
    s.last_cron_run = timezone.now()
    s.save(update_fields=['last_cron_run'])
    return {'roi_paid': paid, 'options_settled': settled}
