from django.contrib import admin
from .models import Patient, Medication, AdverseEvent, DrugInteraction

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'language', 'telegram_chat_id')
    search_fields = ('user__username', 'user__email', 'phone')
    list_filter = ('language',)

@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'patient', 'dosage', 'created_at')
    search_fields = ('name', 'patient__user__username')
    list_filter = ('created_at',)

@admin.register(AdverseEvent)
class AdverseEventAdmin(admin.ModelAdmin):
    list_display = ('patient', 'medication', 'reaction', 'severity', 'reported_date')
    search_fields = ('patient__user__username', 'medication__name', 'reaction')
    list_filter = ('severity', 'reported_date')

@admin.register(DrugInteraction)
class DrugInteractionAdmin(admin.ModelAdmin):
    list_display = ('drug_a', 'drug_b', 'severity', 'source', 'last_updated')
    search_fields = ('drug_a', 'drug_b', 'description')
    list_filter = ('severity', 'source')
