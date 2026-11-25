from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
    re_path(r'^static/(?P<path>.*)$', staticfiles_serve, {'insecure': True}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    re_path(r'^favicon\.ico$', staticfiles_serve, {'path': 'images/logo.jpg', 'insecure': True}),
]

if getattr(settings, 'ENABLE_TOOLBAR', False):
    from debug_toolbar.toolbar import debug_toolbar_urls
    urlpatterns += debug_toolbar_urls()

handler403 = 'app.views.custom_403'
handler404 = 'app.views.custom_404'
handler500 = 'app.views.custom_500'

