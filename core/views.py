from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .models import Patient



@login_required
def patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    return render(request, 'core/patient_detail.html', {'patient': patient})


class ExtendedUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = UserCreationForm.Meta.fields + ('email',)


@require_http_methods(["GET", "POST"])
def register(request):
    if request.method == 'POST':
        form = ExtendedUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create associated Patient profile
            Patient.objects.create(
                user=user,
                dob=request.POST.get('dob', timezone.now().date()),  # Default to current date if not provided
                phone=request.POST.get('phone', ''),
                language=request.POST.get('language', 'en')
            )
            # Authenticate and login with the default backend
            authenticated_user = authenticate(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password1']
            )
            login(request, authenticated_user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Registration successful!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ExtendedUserCreationForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def dashboard(request):
    # Try to get patient profile or create a default one
    patient, created = Patient.objects.get_or_create(
        user=request.user,
        defaults={
            'dob': timezone.now().date(),
            'phone': '',
            'language': 'en'
        }
    )

    if created:
        messages.info(request, 'Please update your profile with your information.')

    medications = patient.medication_set.all().order_by('-created_at')
    context = {
        'patient': patient,
        'medications': medications,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
def profile(request):
    # Try to get patient profile or create a default one
    patient, created = Patient.objects.get_or_create(
        user=request.user,
        defaults={
            'dob': timezone.now().date(),
            'phone': '',
            'language': 'en'
        }
    )

    if request.method == 'POST':
        # Update user profile
        patient.phone = request.POST.get('phone', patient.phone)
        patient.language = request.POST.get('language', patient.language)
        patient.telegram_chat_id = request.POST.get('telegram_chat_id', patient.telegram_chat_id)
        if 'dob' in request.POST:
            try:
                patient.dob = request.POST['dob']
            except (ValueError, TypeError):
                messages.error(request, 'Invalid date format for date of birth')
                return redirect('profile')
        patient.save()

        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')

    return render(request, 'core/profile.html', {
        'patient': patient,
        'created': created
    })


@login_required
@require_http_methods(["GET", "POST"])
def add_medication(request, patient_id):
    patient = get_object_or_404(Patient, pk=patient_id)
    if request.method == "POST":
        medication_name = request.POST.get('name', '').strip()
        if medication_name:
            # Assuming a Medication model related to Patient exists
            patient.medication_set.create(name=medication_name, created_at=timezone.now())
            messages.success(request, "Medication added successfully!")
            return redirect('patient_detail', pk=patient_id)
        else:
            messages.error(request, "Medication name is required!")
    return render(request, 'core/add_medication.html', {'patient': patient})
