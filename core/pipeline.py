from django.utils import timezone
from core.models import Patient

def create_patient(backend, user, response, *args, **kwargs):
    """Create a Patient profile for users who sign up via social auth"""
    # Only create a profile if one doesn't exist
    if not hasattr(user, 'patient'):
        Patient.objects.create(
            user=user,
            dob=timezone.now().date(),  # Default date, user can update later
            phone='',  # Empty default, user can update later
            language='en'  # Default to English
        )