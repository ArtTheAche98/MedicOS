from django.core.cache import cache
from core.models import Patient, Medication
from .services import check_drug_interactions
import logging

logger = logging.getLogger(__name__)

def check_new_medication_interactions(patient_id, new_medication_name):
    """Check interactions for a newly added medication"""
    try:
        patient = Patient.objects.get(id=patient_id)
        medications = Medication.objects.filter(patient=patient)
        med_names = list(medications.values_list('name', flat=True))
        
        interactions = check_drug_interactions(med_names)
        if interactions:
            cache_key = f"patient_{patient_id}_interactions"
            cache.set(cache_key, interactions, timeout=3600)  # Cache for 1 hour
            
    except Exception as e:
        logger.error(f"Error in check_new_medication_interactions: {str(e)}")

def update_patient_interactions(patient_id):
    """Update all interactions for a patient's medications"""
    try:
        patient = Patient.objects.get(id=patient_id)
        medications = Medication.objects.filter(patient=patient)
        med_names = list(medications.values_list('name', flat=True))
        
        if len(med_names) >= 2:
            interactions = check_drug_interactions(med_names)
            if interactions:
                cache_key = f"patient_{patient_id}_interactions"
                cache.set(cache_key, interactions, timeout=3600)
                
    except Exception as e:
        logger.error(f"Error in update_patient_interactions: {str(e)}")