from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from friend_bot import views
from friend_bot.api_views import IngestMessageView, SendMessageView, StatisticsView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard_view, name='dashboard'),
    path('group/<int:group_id>/summary/', views.group_summary_view, name='group_summary'),
    path('group/<int:group_id>/statistics/', views.group_statistics_view, name='group_statistics'),
    path('api/ingest/message/', IngestMessageView.as_view(), name='ingest_message'),
    path('api/send/message/', SendMessageView.as_view(), name='send_message'),
    path('api/statistics/', StatisticsView.as_view(), name='statistics'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
