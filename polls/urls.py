from django.urls import path
from . import views

app_name = "polls"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("<int:pk>/", views.DetailView.as_view(), name="detail"), 
    path("<int:pk>/results/", views.ResultsView.as_view(), name="results"),
    path("<int:question_id>/vote/", views.vote, name="vote"),
    path('this-or-that/', views.this_or_that_home, name='this_or_that_home'),
    path('this-or-that/<int:category_id>/', views.this_or_that_game, name='this_or_that'),
    path('vote/<int:question_id>/', views.vote_this_or_that, name='vote_this_or_that'),

    # This or That URLs
    path("this-or-that/", views.this_or_that_home, name="this_or_that_home"),
    path("this-or-that/<int:category_id>/", views.this_or_that_game, name="this_or_that"),
    path("this-or-that/vote/<int:question_id>/", views.vote_this_or_that, name="vote_this_or_that"),
    path('quiz-summary/<int:category_id>/', views.quiz_summary, name='quiz_summary'),


    #Analytics
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path("analytics/update/", views.update_analytics, name="update_analytics"),
    path("analytics/export/", views.export_analytics, name="export_analytics"),
    
]