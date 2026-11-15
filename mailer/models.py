from django.db import models
from django.utils import timezone


class EmailTemplate(models.Model):
    """Reusable branded email templates."""
    name       = models.CharField(max_length=120, unique=True)
    subject    = models.CharField(max_length=250)
    body_html  = models.TextField(
        help_text="HTML body. Use {{first_name}}, {{last_name}}, {{email}} as placeholders."
    )
    body_text  = models.TextField(blank=True, help_text="Plain-text fallback (auto-generated if blank).")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class EmailLog(models.Model):
    """Record of every email dispatched through the mailer."""
    STATUS_QUEUED  = 'queued'
    STATUS_SENT    = 'sent'
    STATUS_FAILED  = 'failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED,  'Queued'),
        (STATUS_SENT,    'Sent'),
        (STATUS_FAILED,  'Failed'),
    ]

    to_address = models.CharField(max_length=250)
    to_name    = models.CharField(max_length=120, blank=True)
    subject    = models.CharField(max_length=250)
    body_html  = models.TextField(blank=True)
    body_text  = models.TextField(blank=True)
    reply_to   = models.CharField(max_length=150, blank=True)
    cc         = models.CharField(max_length=500, blank=True)
    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    resend_id  = models.CharField(max_length=80, blank=True, help_text="Resend message ID")
    error_msg  = models.TextField(blank=True)
    sent_by    = models.CharField(max_length=80, blank=True, help_text="Admin username or 'system'")
    template   = models.ForeignKey(
        EmailTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name='logs'
    )
    broadcast  = models.ForeignKey(
        'Broadcast', null=True, blank=True, on_delete=models.SET_NULL, related_name='logs'
    )
    sent_at    = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"[{self.status}] {self.subject} → {self.to_address}"


class Broadcast(models.Model):
    """Bulk email campaign sent to a chosen audience."""
    AUDIENCE_ALL      = 'all'
    AUDIENCE_VERIFIED = 'verified'
    AUDIENCE_ACTIVE   = 'active'
    AUDIENCE_CUSTOM   = 'custom'
    AUDIENCE_CHOICES  = [
        (AUDIENCE_ALL,      'All Investors'),
        (AUDIENCE_VERIFIED, 'Email-Verified Investors'),
        (AUDIENCE_ACTIVE,   'Active Investors (with portfolio)'),
        (AUDIENCE_CUSTOM,   'Custom (manual list)'),
    ]
    STATUS_DRAFT  = 'draft'
    STATUS_SENT   = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_DRAFT,  'Draft'),
        (STATUS_SENT,   'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    subject       = models.CharField(max_length=250)
    body_html     = models.TextField()
    body_text     = models.TextField(blank=True)
    audience      = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    custom_emails = models.TextField(
        blank=True, help_text="Comma-separated email addresses (for Custom audience only)"
    )
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    total_sent    = models.PositiveIntegerField(default=0)
    total_failed  = models.PositiveIntegerField(default=0)
    sent_by       = models.CharField(max_length=80, blank=True)
    template      = models.ForeignKey(
        EmailTemplate, null=True, blank=True, on_delete=models.SET_NULL, related_name='broadcasts'
    )
    created_at    = models.DateTimeField(auto_now_add=True)
    sent_at       = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.status}] {self.subject} ({self.total_sent} sent)"
