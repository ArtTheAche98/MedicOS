from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Medication management
    path('medications/', views.medication_list, name='medication_list'),
    path('medications/<int:medication_id>/', views.remove_medication, name='remove_medication'),
    path('medications/<int:medication_id>/details/', views.medication_details, name='medication_details'),
    path('medications/schedule/', views.medication_schedule, name='medication_schedule'),
    path('medications/interactions/', views.medication_interactions, name='medication_interactions'),
    
    # Reminders
    path('reminders/send/', views.send_reminder, name='send_reminder'),
    path('reminders/schedule/', views.schedule_reminders, name='schedule_reminders'),
    
    # Drug information
    path('drugs/alternatives/', views.get_alternatives, name='get_alternatives'),
    path('drugs/interactions/check/', views.check_current_interactions, name='check_interactions'),
    
    # Adverse events
    path('adverse-events/report/', views.report_adverse_event, name='report_adverse_event'),
]