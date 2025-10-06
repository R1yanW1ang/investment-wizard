from django.urls import path
from . import views

urlpatterns = [
    path('articles/', views.ArticleListView.as_view(), name='article-list'),
    path('articles/<int:pk>/', views.ArticleDetailView.as_view(), name='article-detail'),
    path('scrape/', views.trigger_scraping, name='trigger-scraping'),
    path('get-result/', views.get_result, name='get-result'),
    path('health/', views.health_check, name='health-check'),
    path('email/test/', views.test_email_config, name='test-email-config'),
    path('email/status/', views.email_config_status, name='email-config-status'),
]
