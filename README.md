# 🩺 MedicOS – Medication Safety Assistant

**MedicOS** is a Django-based web application designed to **enhance medication safety** for patients and healthcare providers. It helps prevent harmful drug interactions, suggests safer alternatives using AI, and improves medication adherence with reminders and voice instructions.

[![Demo Video]([https://img.shields.io/badge/Demo-Coming_Soon-blue](https://youtu.be/rTztGg673XE))](#)

---

## 🔍 Key Features

- **⚠️ Drug Interaction Checker**  
  Instantly check for dangerous drug combinations using OpenFDA or MediShield APIs.

- **🤖 AI-Powered Alternatives**  
  Get safer substitute suggestions via the DeepSeek API.

- **📱 Patient Reminders**  
  Send SMS/WhatsApp alerts using Twilio or free messaging APIs.

- **🗣️ Voice-Based Instructions**  
  Provide medication guidance with synthesized voice via Amazon Polly or open alternatives.

- **📊 Smart Dashboard**  
  View alerts, manage medications, and monitor compliance in real time.

- **🌐 Mobile-Optimized UI**  
  Access through a responsive PWA or FlutterFlow-based frontend for patients.

---

## ⚙️ Tech Stack

| Layer               | Tech                              |
|--------------------|------------------------------------|
| Backend            | Django, Python                     |
| Task Queue         | Celery + Redis                     |
| APIs               | OpenFDA / MediShield, DeepSeek     |
| Messaging          | Twilio, SMTP (or alternatives)     |
| Voice              | Amazon Polly                       |
| Frontend (Mobile)  | PWA / FlutterFlow                  |
| Hosting            | Docker + Azure App Service         |

---

## 📦 Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/medicos.git
   cd medicos

	2.	Create Virtual Environment

python3 -m venv .venv
source .venv/bin/activate


	3.	Install Dependencies

pip install -r requirements.txt


	4.	Configure Environment Variables
Create a .env file and add:

OPENFDA_API_KEY=your_openfda_key
DEEPSEEK_API_KEY=your_deepseek_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
TWILIO_PHONE=your_twilio_number
PATIENT_PHONE=recipient_number
AWS_POLLY_KEY=your_aws_key
AWS_POLLY_SECRET=your_aws_secret


	5.	Apply Migrations & Collect Static Files

python manage.py migrate
python manage.py collectstatic


	6.	Run Redis

redis-server


	7.	Start Celery Workers

celery -A medicos worker --loglevel=info
celery -A medicos beat --loglevel=info


	8.	Run the Development Server

python manage.py runserver



⸻

🔐 Environment Variables Reference

Variable	Purpose
OPENFDA_API_KEY	Drug interaction API key
DEEPSEEK_API_KEY	AI suggestion API key
PATIENT_PHONE	Patient’s phone number
AWS_POLLY_KEY	Amazon Polly Key
AWS_POLLY_SECRET	Amazon Polly Secret


⸻

🧑‍⚕️ Use Cases
	•	Clinicians – Get real-time interaction alerts during prescription.
	•	Patients – Receive reminders and spoken instructions for better compliance.
	•	Pharmacists – Offer AI-suggested alternatives tailored to patients.

⸻

🚧 Roadmap
	•	Interaction checker with OpenFDA
	•	AI-powered suggestions
	•	SMS reminders
	•	Voice instructions
	•	User authentication for patients
	•	Multi-patient dashboard for clinicians
	•	Full mobile version with Flutter

⸻

🤝 Contributing

Contributions and feedback are welcome! Whether you’re a developer, healthcare professional, or designer — join the mission to improve medication safety.
	1.	Fork this repo
	2.	Create a new branch
	3.	Submit a PR

⸻

📝 License

This project is licensed under the MIT License.
