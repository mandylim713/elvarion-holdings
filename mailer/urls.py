from django.urls import path
from . import views

app_name = 'mailer'

urlpatterns = [
    # Standalone Auth
    path('login/',                        views.mail_login,        name='login'),
    path('logout/',                       views.mail_logout,       name='logout'),

    # Dashboard
    path('',                              views.dashboard,         name='dashboard'),

    # Compose & send single email
    path('compose/',                      views.compose,           name='compose'),

    # Email logs
    path('logs/',                         views.logs,              name='logs'),
    path('logs/<int:pk>/',                views.log_detail,        name='log_detail'),

    # Email templates
    path('templates/',                    views.template_list,     name='templates'),
    path('templates/new/',                views.template_edit,     name='template_new'),
    path('templates/<int:pk>/edit/',      views.template_edit,     name='template_edit'),
    path('templates/<int:pk>/delete/',    views.template_delete,   name='template_delete'),

    # Broadcasts
    path('broadcast/',                    views.broadcast_list,    name='broadcast_list'),
    path('broadcast/new/',                views.broadcast_new,     name='broadcast_new'),
    path('broadcast/<int:pk>/',           views.broadcast_detail,  name='broadcast_detail'),
    path('broadcast/<int:pk>/send/',      views.broadcast_send,    name='broadcast_send'),
    path('broadcast/<int:pk>/delete/',    views.broadcast_delete,  name='broadcast_delete'),

    # AJAX
    path('api/template/<int:pk>/',        views.api_template,      name='api_template'),
]
