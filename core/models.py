from django.db import models
from django.contrib.auth.models import User
from django_cryptography.fields import encrypt

class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    dob = models.DateField()
    phone = models.CharField(max_length=20)
    language = models.CharField(max_length=2, default='en')
    telegram_chat_id = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.phone}"

class Medication(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=50)
    schedule = models.JSONField()  # {time: "08:00", days: [0-6]}
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.dosage}"

class AdverseEvent(models.Model):
    SEVERITY_CHOICES = [
        (1, 'Mild'),
        (2, 'Moderate'),
        (3, 'Severe')
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    medication = models.ForeignKey(Medication, on_delete=models.CASCADE)
    reaction = models.CharField(max_length=255)
    severity = models.IntegerField(choices=SEVERITY_CHOICES)
    notes = encrypt(models.TextField(blank=True))
    reported_date = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.patient} - {self.medication} - {self.get_severity_display()}"

class DrugInteraction(models.Model):
    drug_a = models.CharField(max_length=255)
    drug_b = models.CharField(max_length=255)
    severity = models.IntegerField(choices=AdverseEvent.SEVERITY_CHOICES)
    description = models.TextField()
    confidence_score = models.FloatField(default=0.0)  # Score from 0 to 1
    references = models.JSONField(default=list)  # List of reference links/citations
    source = models.CharField(max_length=100, default='OpenFDA')
    last_updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)  # To soft-disable outdated interactions
    
    class Meta:
        unique_together = ['drug_a', 'drug_b']
        indexes = [
            models.Index(fields=['drug_a', 'active']),
            models.Index(fields=['drug_b', 'active']),
        ]
    
    def __str__(self):
        return f"{self.drug_a} + {self.drug_b} - {self.get_severity_display()}"
        
    def save(self, *args, **kwargs):
        # Always store drug names in alphabetical order for consistency
        if self.drug_a > self.drug_b:
            self.drug_a, self.drug_b = self.drug_b, self.drug_a
        super().save(*args, **kwargs)
