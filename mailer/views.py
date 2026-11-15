"""mailer/views.py — Standalone mail system views with dedicated login."""
import json
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Broadcast, EmailLog, EmailTemplate
from .sender import send_email, send_broadcast


# ── Standalone Authentication ──────────────────────────────────────────────────

def mail_login(request):
    """Dedicated standalone sign-in for the Mailer Suite at /mail/login/."""
    nxt = request.GET.get('next', '') or request.POST.get('next', '')
    if request.user.is_authenticated and request.user.is_staff:
        if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
            return redirect(nxt)
        return redirect('mailer:dashboard')

    if request.method == 'POST':
        ident = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')

        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '127.0.0.1')).split(',')[0].strip()
        throttle_key = f'mail_login_throttle_{client_ip}_{ident.lower()}'
        attempts = cache.get(throttle_key, 0)
        if attempts >= 5:
            messages.error(request, 'Too many login attempts. Please wait 15 minutes before trying again.')
            return render(request, 'mailer/login.html', {'ident': ident, 'next': nxt}, status=429)

        user = authenticate(request, username=ident, password=password)
        if not user and '@' in ident:
            u = User.objects.filter(email__iexact=ident).first()
            if u:
                user = authenticate(request, username=u.username, password=password)

        if user is not None and user.is_staff and user.is_active:
            cache.delete(throttle_key)
            login(request, user)
            request.session.set_expiry(60 * 60 * 8)
            messages.success(request, f'Signed in to Mailbox Suite as {user.username}.')
            if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
                return redirect(nxt)
            return redirect('mailer:dashboard')

        cache.set(throttle_key, attempts + 1, 15 * 60)
        messages.error(request, 'Invalid credentials or account does not have mailroom staff authorization.')
        return render(request, 'mailer/login.html', {'ident': ident, 'next': nxt}, status=200)

    return render(request, 'mailer/login.html', {'next': nxt})


def mail_logout(request):
    """Sign out of Mailbox Suite."""
    logout(request)
    messages.info(request, 'You have signed out of the Mailbox Suite.')
    return redirect('mailer:login')


# ── dashboard ──────────────────────────────────────────────────────────────────

@staff_member_required(login_url='/mail/login/')
def dashboard(request):
    total_sent   = EmailLog.objects.filter(status='sent').count()
    total_failed = EmailLog.objects.filter(status='failed').count()
    recent_logs  = EmailLog.objects.select_related('template')[:10]
    broadcasts   = Broadcast.objects.order_by('-created_at')[:5]
    templates    = EmailTemplate.objects.count()

    ctx = {
        'total_sent':     total_sent,
        'total_failed':   total_failed,
        'recent_logs':    recent_logs,
        'broadcasts':     broadcasts,
        'template_count': templates,
        'section':        'dashboard',
    }
    return render(request, 'mailer/dashboard.html', ctx)


# ── compose & send single email ───────────────────────────────────────────────

@staff_member_required(login_url='/mail/login/')
def compose(request):
    templates = EmailTemplate.objects.all()
    investors = User.objects.filter(is_staff=False, is_active=True).order_by('email')

    if request.method == 'POST':
        to_address = request.POST.get('to_address', '').strip()
        to_name    = request.POST.get('to_name', '').strip()
        subject    = request.POST.get('subject', '').strip()
        body_html  = request.POST.get('body_html', '').strip()
        reply_to   = request.POST.get('reply_to', '').strip()
        cc_raw     = request.POST.get('cc', '').strip()
        cc         = [e.strip() for e in cc_raw.split(',') if e.strip()] if cc_raw else []

        if not to_address or not subject or not body_html:
            messages.error(request, 'To, Subject and Body are required.')
        else:
            log = send_email(
                to_address=to_address,
                subject=subject,
                body_html=body_html,
                to_name=to_name,
                reply_to=reply_to,
                cc=cc,
                sent_by=request.user.username,
            )
            if log.status == 'sent':
                messages.success(request, f'Email sent to {to_address} (Resend ID: {log.resend_id})')
            else:
                messages.error(request, f'Failed to send: {log.error_msg}')
            return redirect('mailer:logs')

    ctx = {
        'templates': templates,
        'investors': investors,
        'section':   'compose',
    }
    return render(request, 'mailer/compose.html', ctx)


# ── email logs ─────────────────────────────────────────────────────────────────

@staff_member_required(login_url='/mail/login/')
def logs(request):
    qs = EmailLog.objects.select_related('template', 'broadcast').all()

    status = request.GET.get('status', '')
    q      = request.GET.get('q', '')
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(to_address__icontains=q) | Q(subject__icontains=q))

    ctx = {
        'logs':    qs[:200],
        'status':  status,
        'q':       q,
        'section': 'logs',
    }
    return render(request, 'mailer/logs.html', ctx)


@staff_member_required(login_url='/mail/login/')
def log_detail(request, pk):
    log = get_object_or_404(EmailLog, pk=pk)
    return render(request, 'mailer/log_detail.html', {'log': log, 'section': 'logs'})


# ── templates ──────────────────────────────────────────────────────────────────

@staff_member_required(login_url='/mail/login/')
def template_list(request):
    templates = EmailTemplate.objects.all()
    return render(request, 'mailer/templates.html', {'templates': templates, 'section': 'templates'})


@staff_member_required(login_url='/mail/login/')
def template_edit(request, pk=None):
    obj = get_object_or_404(EmailTemplate, pk=pk) if pk else None

    if request.method == 'POST':
        name      = request.POST.get('name', '').strip()
        subject   = request.POST.get('subject', '').strip()
        body_html = request.POST.get('body_html', '').strip()
        body_text = request.POST.get('body_text', '').strip()

        if not name or not subject or not body_html:
            messages.error(request, 'Name, Subject and Body are required.')
        else:
            if obj is None:
                obj = EmailTemplate()
            obj.name      = name
            obj.subject   = subject
            obj.body_html = body_html
            obj.body_text = body_text
            obj.save()
            messages.success(request, f'Template "{name}" saved.')
            return redirect('mailer:templates')

    ctx = {'obj': obj, 'section': 'templates'}
    return render(request, 'mailer/template_edit.html', ctx)


@staff_member_required(login_url='/mail/login/')
@require_POST
def template_delete(request, pk):
    obj = get_object_or_404(EmailTemplate, pk=pk)
    obj.delete()
    messages.success(request, 'Template deleted.')
    return redirect('mailer:templates')


# ── broadcast ──────────────────────────────────────────────────────────────────

@staff_member_required(login_url='/mail/login/')
def broadcast_list(request):
    bcs = Broadcast.objects.all()
    return render(request, 'mailer/broadcast_list.html', {'broadcasts': bcs, 'section': 'broadcast'})


@staff_member_required(login_url='/mail/login/')
def broadcast_new(request):
    templates = EmailTemplate.objects.all()

    if request.method == 'POST':
        subject       = request.POST.get('subject', '').strip()
        body_html     = request.POST.get('body_html', '').strip()
        audience      = request.POST.get('audience', 'all')
        custom_emails = request.POST.get('custom_emails', '').strip()
        tpl_id        = request.POST.get('template_id', '')
        action        = request.POST.get('action', 'save')

        if not subject or not body_html:
            messages.error(request, 'Subject and Body are required.')
        else:
            tpl = EmailTemplate.objects.filter(pk=tpl_id).first() if tpl_id else None
            bc = Broadcast.objects.create(
                subject=subject,
                body_html=body_html,
                audience=audience,
                custom_emails=custom_emails,
                template=tpl,
                sent_by=request.user.username,
            )
            if action == 'send':
                bc = send_broadcast(bc.pk, sent_by=request.user.username)
                messages.success(
                    request,
                    f'Broadcast sent! {bc.total_sent} delivered, {bc.total_failed} failed.'
                )
            else:
                messages.success(request, 'Broadcast saved as draft.')
            return redirect('mailer:broadcast_list')

    ctx = {'templates': templates, 'section': 'broadcast'}
    return render(request, 'mailer/broadcast_new.html', ctx)


@staff_member_required(login_url='/mail/login/')
def broadcast_detail(request, pk):
    bc   = get_object_or_404(Broadcast, pk=pk)
    logs = bc.logs.all()[:200]
    return render(request, 'mailer/broadcast_detail.html', {'bc': bc, 'logs': logs, 'section': 'broadcast'})


@staff_member_required(login_url='/mail/login/')
@require_POST
def broadcast_send(request, pk):
    bc = get_object_or_404(Broadcast, pk=pk)
    bc = send_broadcast(bc.pk, sent_by=request.user.username)
    messages.success(request, f'Broadcast dispatched — {bc.total_sent} sent, {bc.total_failed} failed.')
    return redirect('mailer:broadcast_detail', pk=bc.pk)


@staff_member_required(login_url='/mail/login/')
@require_POST
def broadcast_delete(request, pk):
    bc = get_object_or_404(Broadcast, pk=pk)
    bc.delete()
    messages.success(request, 'Broadcast deleted.')
    return redirect('mailer:broadcast_list')


# ── AJAX: load template body ───────────────────────────────────────────────────

@staff_member_required(login_url='/mail/login/')
def api_template(request, pk):
    tpl = get_object_or_404(EmailTemplate, pk=pk)
    return JsonResponse({'subject': tpl.subject, 'body_html': tpl.body_html})
