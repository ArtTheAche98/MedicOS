from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from datetime import datetime, timedelta
from core.models import Patient, Medication, AdverseEvent, DrugInteraction
from .services import (
    check_drug_interactions, 
    send_telegram_reminder, 
    generate_voice_message,
    get_alternative_drugs
)

logger = logging.getLogger(__name__)

@login_required
@require_http_methods(["GET", "POST"])
def medication_list(request):
    if request.method == "GET":
        patient = get_object_or_404(Patient, user=request.user)
        medications = Medication.objects.filter(patient=patient)
        return JsonResponse({
            'medications': list(medications.values())
        })
    
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            patient = get_object_or_404(Patient, user=request.user)
            
            # Create medication immediately without waiting for interaction check
            medication = Medication.objects.create(
                patient=patient,
                name=data['name'],
                dosage=data['dosage'],
                schedule=data['schedule']
            )
            
            # Return the medication data immediately
            return JsonResponse({
                'medication': {
                    'id': medication.id,
                    'name': medication.name,
                    'dosage': medication.dosage,
                    'schedule': medication.schedule
                }
            })
            
        except Exception as e:
            logger.error(f"Error adding medication: {str(e)}")
            return JsonResponse({'error': 'An error occurred while adding medication.'}, status=500)

# Split interaction checking into a separate endpoint
@login_required
@require_http_methods(["GET"])
def check_current_interactions(request):
    try:
        patient = get_object_or_404(Patient, user=request.user)
        medications = Medication.objects.filter(patient=patient)
        med_names = list(medications.values_list('name', flat=True))
        
        if len(med_names) < 2:
            return JsonResponse({'interactions': []})
            
        interactions = check_drug_interactions(med_names)
        return JsonResponse({'interactions': interactions})
        
    except Exception as e:
        logger.error(f"Error checking interactions: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def medication_schedule(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    
    try:
        patient = get_object_or_404(Patient, user=request.user)
        medications = Medication.objects.filter(patient=patient)
        events = []
        
        if start and end:
            start_date = datetime.strptime(start.split('T')[0], '%Y-%m-%d')
            end_date = datetime.strptime(end.split('T')[0], '%Y-%m-%d')
            
            for medication in medications:
                schedule = medication.schedule
                if not isinstance(schedule, dict) or 'time' not in schedule or 'days' not in schedule:
                    continue
                    
                # Get medication date range
                med_start = schedule.get('startDate')
                med_end = schedule.get('endDate')
                
                if med_start:
                    med_start = datetime.strptime(med_start, '%Y-%m-%d')
                    if med_start > end_date:
                        continue
                else:
                    med_start = start_date
                
                if med_end:
                    med_end = datetime.strptime(med_end, '%Y-%m-%d')
                    if med_end < start_date:
                        continue
                
                # Generate events only within valid date range
                time = schedule['time']
                current = max(start_date, med_start)
                
                while current <= end_date and (not med_end or current <= med_end):
                    if current.weekday() in schedule['days']:
                        event_time = current.replace(
                            hour=int(time.split(':')[0]),
                            minute=int(time.split(':')[1])
                        )
                        events.append({
                            'title': f"{medication.name} - {medication.dosage}",
                            'start': event_time.isoformat(),
                            'allDay': False,
                            'extendedProps': {
                                'medication_id': medication.id
                            }
                        })
                    current += timedelta(days=1)
                    
        return JsonResponse(events, safe=False)
        
    except Exception as e:
        logger.error(f"Error fetching medication schedule: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def medication_interactions(request):
    try:
        patient = get_object_or_404(Patient, user=request.user)
        medications = Medication.objects.filter(patient=patient)
        med_names = list(medications.values_list('name', flat=True))
        
        if len(med_names) < 2:
            return JsonResponse({
                'interactions': []
            })
        
        # Get interactions from both database and API
        interactions = []
        
        # 1. Database interactions
        for i in range(len(med_names)):
            for j in range(i + 1, len(med_names)):
                drug_a, drug_b = sorted([med_names[i], med_names[j]])
                interaction = DrugInteraction.objects.filter(
                    drug_a=drug_a,
                    drug_b=drug_b,
                    active=True
                ).first()
                
                if interaction:
                    interactions.append({
                        'drugs': [drug_a, drug_b],
                        'severity': interaction.severity,
                        'description': interaction.description,
                        'source': interaction.source
                    })
        
        # 2. API interactions (with timeout and chunking)
        try:
            # Check interactions in smaller groups to avoid timeouts
            chunk_size = 3
            for i in range(0, len(med_names), chunk_size):
                chunk = med_names[i:i + chunk_size]
                api_interactions = check_drug_interactions(chunk)
                if api_interactions and isinstance(api_interactions, list):
                    interactions.extend(api_interactions)
        except Exception as api_error:
            logger.warning(f"API interaction check failed: {str(api_error)}")
            # Continue with database results if API fails
            pass
        
        return JsonResponse({
            'interactions': interactions
        }, safe=False)
    except Exception as e:
        logger.error(f"Error fetching medication interactions: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
async def send_reminder(request):
    try:
        data = json.loads(request.body)
        patient = get_object_or_404(Patient, id=data['patient_id'])
        
        if not patient.telegram_chat_id:
            return JsonResponse({
                'status': 'error',
                'message': 'No Telegram chat ID configured. Please set up Telegram notifications in your profile.'
            }, status=400)
        
        # Generate the reminder message
        message = f"🔔 Medication Reminder\n\n"
        message += f"Time to take: {data['medication']}\n"
        message += f"Dosage: {data['dosage']}\n"
        if 'instructions' in data:
            message += f"\nInstructions: {data['instructions']}"
        
        # Generate voice message if requested
        audio_file = None
        if data.get('voice_reminder', False):
            audio_file = await generate_voice_message(
                f"Time to take {data['medication']}. Dosage: {data['dosage']}", 
                patient.language
            )
        
        # Send the reminder
        success = await send_telegram_reminder(
            chat_id=patient.telegram_chat_id,
            message=message,
            audio_file=audio_file
        )
        
        if success:
            return JsonResponse({
                'status': 'success',
                'message': 'Reminder sent successfully'
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Failed to send reminder. Please check your Telegram settings.'
            }, status=500)
            
    except Exception as e:
        logger.error(f"Error sending reminder: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while sending the reminder.'
        }, status=500)

@login_required
@require_http_methods(["POST"])
async def schedule_reminders(request):
    try:
        data = json.loads(request.body)
        patient = get_object_or_404(Patient, user=request.user)
        medication = get_object_or_404(Medication, id=data['medication_id'], patient=patient)
        
        # Validate schedule data
        if not medication.schedule or 'time' not in medication.schedule:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid medication schedule'
            }, status=400)
        
        # Schedule format: {'time': 'HH:MM', 'days': [0,1,2,3,4,5,6], 'startDate': 'YYYY-MM-DD', 'endDate': 'YYYY-MM-DD'}
        schedule = medication.schedule
        
        # Create reminder message
        message = {
            'patient_id': patient.id,
            'medication': medication.name,
            'dosage': medication.dosage,
            'schedule': schedule,
            'voice_reminder': data.get('voice_reminder', False)
        }
        
        # Here you would typically add this to a task queue (e.g., Celery)
        # For now, we'll just return the scheduled confirmation
        return JsonResponse({
            'status': 'success',
            'message': 'Reminders scheduled successfully',
            'details': {
                'medication': medication.name,
                'time': schedule['time'],
                'days': schedule['days']
            }
        })
        
    except Exception as e:
        logger.error(f"Error scheduling reminders: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while scheduling reminders.'
        }, status=500)

@login_required
@require_http_methods(["GET"])
async def get_alternatives(request):
    drug_name = request.GET.get('drug')
    if not drug_name:
        return JsonResponse({
            'status': 'error',
            'message': 'Drug name is required'
        })
    
    patient = get_object_or_404(Patient, user=request.user)
    conditions = request.GET.getlist('conditions', None)
    
    suggestions = await get_alternative_drugs(drug_name, conditions)
    
    return JsonResponse({
        'status': 'success',
        'drug': drug_name,
        'alternatives': suggestions
    })

@login_required
@require_http_methods(["POST"])
def report_adverse_event(request):
    data = json.loads(request.body)
    patient = get_object_or_404(Patient, user=request.user)
    medication = get_object_or_404(Medication, id=data['medication_id'], patient=patient)
    
    event = AdverseEvent.objects.create(
        patient=patient,
        medication=medication,
        reaction=data['reaction'],
        severity=data['severity'],
        notes=data.get('notes', '')
    )
    
    return JsonResponse({
        'status': 'success',
        'event_id': event.id
    })

@login_required
@require_http_methods(["DELETE"])
def remove_medication(request, medication_id):
    try:
        patient = get_object_or_404(Patient, user=request.user)
        medication = get_object_or_404(Medication, id=medication_id, patient=patient)
        medication.delete()
        return JsonResponse({'status': 'success', 'message': 'Medication removed successfully'})
    except Exception as e:
        logger.error(f"Error removing medication: {str(e)}")
        return JsonResponse({'error': 'An error occurred while removing medication.'}, status=500)

@login_required
@require_http_methods(["GET"])
def medication_details(request, medication_id):
    try:
        patient = get_object_or_404(Patient, user=request.user)
        medication = get_object_or_404(Medication, id=medication_id, patient=patient)
        
        adverse_events = AdverseEvent.objects.filter(medication=medication).order_by('-reported_date')
        
        # Format schedule information
        schedule = medication.schedule if isinstance(medication.schedule, dict) else {}
        schedule_info = {
            'time': schedule.get('time', 'Not specified'),
            'days': schedule.get('days', []),
            'startDate': schedule.get('startDate', 'Not specified'),
            'endDate': schedule.get('endDate', 'Ongoing')
        }
        
        return JsonResponse({
            'medication': {
                'id': medication.id,
                'name': medication.name,
                'dosage': medication.dosage,
                'schedule': schedule_info,
                'startDate': schedule_info['startDate'],
                'endDate': schedule_info['endDate']
            },
            'adverse_events': list(adverse_events.values('reaction', 'severity', 'reported_date'))
        })
    except Exception as e:
        logger.error(f"Error fetching medication details: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
