from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Changed dashboard URL from '' to 'dashboard/' for consistency
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('patient/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('patient/<int:patient_id>/add-medication/', views.add_medication, name='add_medication'),
    # Password change URLs
    path('password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    # Optionally, redirect the root URL to dashboard
    path('', views.dashboard, name='home'),
]