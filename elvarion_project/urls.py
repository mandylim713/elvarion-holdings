from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('management/django-admin/', admin.site.urls),
    path('mail/', include('mailer.urls', namespace='mailer')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
