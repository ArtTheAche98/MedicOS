import os
import io
import requests
import logging
import hashlib
import time
import unicodedata
import re
import aiohttp
import json
from typing import Optional, Dict, List
from datetime import datetime
from gtts import gTTS
from telegram.ext import Application  # Updated import
from telegram import Bot  # Updated import
from telegram.error import TelegramError
from django.conf import settings
from django.core.cache import cache
from django.utils.text import slugify
from core.models import DrugInteraction
from itertools import combinations

logger = logging.getLogger(__name__)

def sanitize_drug_name(name):
    """Normalize and sanitize drug names for API calls"""
    # Normalize unicode characters (e.g., combining diacritical marks)
    normalized = unicodedata.normalize('NFKD', name)
    # Remove non-ASCII characters
    ascii_name = normalized.encode('ASCII', 'ignore').decode()
    # Clean up any double spaces and trim
    cleaned = re.sub(r'\s+', ' ', ascii_name).strip()
    return cleaned

def calculate_severity(description):
    """Calculate interaction severity based on description content"""
    description_lower = description.lower()
    
    high_risk_phrases = [
        'severe', 'significant', 'dangerous', 'avoid', 'contraindicated',
        'high risk', 'stop', 'do not', 'fatal', 'life-threatening'
    ]
    
    medium_risk_phrases = [
        'moderate', 'monitor', 'caution', 'may increase', 'watch for',
        'be careful', 'adjust', 'consider'
    ]
    
    if any(phrase in description_lower for phrase in high_risk_phrases):
        return 3
    elif any(phrase in description_lower for phrase in medium_risk_phrases):
        return 2
    return 1

async def send_telegram_reminder(chat_id: str, message: str, audio_file: Optional[bytes] = None) -> bool:
    """
    Send a reminder message and optionally an audio file via Telegram
    Returns True if successful, False otherwise
    """
    try:
        # Initialize bot with application
        app = Application.builder().token(settings.TELEGRAM_TOKEN).build()
        bot = app.bot
        
        # Send text message
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode='HTML'
        )
        
        # If audio file is provided, send it
        if audio_file:
            await bot.send_voice(
                chat_id=chat_id,
                voice=audio_file,
                caption="Voice reminder"
            )
        
        return True
    except TelegramError as e:
        logger.error(f"Telegram error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error sending Telegram message: {str(e)}")
        return False

async def generate_voice_message(text: str, lang: str = 'en') -> Optional[bytes]:
    """
    Generate voice message using various TTS services with fallback options
    Returns audio file bytes if successful, None otherwise
    """
    try:
        # First try MaryTTS
        marytts_url = settings.MARYTTS_URL
        
        params = {
            'INPUT_TYPE': 'TEXT',
            'OUTPUT_TYPE': 'AUDIO',
            'LOCALE': lang,
            'INPUT_TEXT': text,
            'AUDIO': 'WAVE'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(marytts_url, data=params) as response:
                    if response.status == 200:
                        return await response.read()
        except Exception as marytts_error:
            logger.warning(f"MaryTTS error, trying fallback: {str(marytts_error)}")
            
        # Fallback to VoiceRSS (they offer free tier)
        voice_rss_key = settings.VOICERSS_API_KEY
        if voice_rss_key:
            voice_rss_url = "https://api.voicerss.org/"
            params = {
                'key': voice_rss_key,
                'hl': lang,
                'src': text,
                'c': 'WAV',
                'f': '16khz_16bit_mono'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(voice_rss_url, params=params) as response:
                    if response.status == 200:
                        return await response.read()
        
        # If both services fail, log warning and return None
        logger.warning("All TTS services failed, sending text-only notification")
        return None
                    
    except Exception as e:
        logger.error(f"Error generating voice message: {str(e)}")
        return None

async def get_alternative_drugs(drug_name: str, conditions: Optional[List[str]] = None) -> Dict:
    """
    Get alternative drug suggestions using FDA API first, fallback to cached data
    """
    cache_key = f"alt_drugs_{slugify(drug_name)}_{slugify('_'.join(conditions or []))}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return cached_result

    try:
        # First try FDA API
        fda_alternatives = await _get_fda_alternatives(drug_name)
        if (fda_alternatives):
            cache.set(cache_key, fda_alternatives, timeout=86400)  # Cache for 24 hours
            return fda_alternatives
            
        # Fallback to DeepSeek if FDA fails
        if settings.DEEPSEEK_API_KEY:
            return await _get_deepseek_alternatives(drug_name, conditions)
            
        return {
            "status": "error",
            "message": "No alternative suggestions available"
        }
        
    except Exception as e:
        logger.error(f"Error getting alternative drugs: {str(e)}")
        return {
            "status": "error",
            "message": f"Error fetching alternatives: {str(e)}"
        }

async def _get_fda_alternatives(drug_name: str) -> Optional[Dict]:
    """
    Get alternative drugs from FDA API
    """
    if not settings.OPENFDA_KEY:
        return None
        
    try:
        url = "https://api.fda.gov/drug/ndc.json"
        params = {
            "api_key": settings.OPENFDA_KEY,
            "search": f"generic_name:{drug_name}",
            "limit": 5
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    alternatives = []
                    
                    for result in data.get('results', []):
                        if 'generic_name' in result:
                            alternatives.append({
                                'name': result['generic_name'],
                                'brand_name': result.get('brand_name', ''),
                                'manufacturer': result.get('labeler_name', ''),
                                'source': 'FDA'
                            })
                    
                    return {
                        "status": "success",
                        "alternatives": alternatives
                    }
                    
        return None
        
    except Exception as e:
        logger.error(f"FDA API error: {str(e)}")
        return None

async def _get_deepseek_alternatives(drug_name: str, conditions: Optional[List[str]] = None) -> Dict:
    """
    Get alternative drugs from DeepSeek API
    """
    try:
        prompt = f"Suggest alternative medications for {drug_name}"
        if conditions:
            prompt += f" considering these conditions: {', '.join(conditions)}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    suggestions = data['choices'][0]['message']['content']
                    
                    return {
                        "status": "success",
                        "alternatives": [{
                            "name": suggestion.strip(),
                            "source": "DeepSeek"
                        } for suggestion in suggestions.split(',')]
                    }
                else:
                    return {
                        "status": "error",
                        "message": "Failed to get alternatives from DeepSeek"
                    }
                    
    except Exception as e:
        logger.error(f"DeepSeek API error: {str(e)}")
        return {
            "status": "error",
            "message": str(e)
        }

def check_drug_interactions(drug_list):
    """Check drug interactions using DeepSeek API"""
    if not drug_list or len(drug_list) < 2:
        return []
    
    # Sanitize drug names while preserving original names
    drug_pairs = [(drug, sanitize_drug_name(drug)) for drug in drug_list]
    cache_key = f"drug_int_{'_'.join(sorted([pair[1] for pair in drug_pairs]))}"
    
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    interactions = []
    
    for i, (orig_a, clean_a) in enumerate(drug_pairs):
        for orig_b, clean_b in drug_pairs[i+1:]:
            try:
                # Use cleaned names for cache key
                pair_key = f"drug_pair_{min(clean_a, clean_b)}_{max(clean_a, clean_b)}"
                cached_pair = cache.get(pair_key)
                
                if cached_pair:
                    # Update with original drug names
                    cached_pair['drugs'] = [orig_a, orig_b]
                    interactions.append(cached_pair)
                    continue
                
                prompt = (
                    f"Describe the specific clinical interaction between {orig_a} and {orig_b}.\n"
                    "Focus on:\n"
                    "1. Major interaction risks\n"
                    "2. Clinical significance\n"
                    "3. Clear recommendation\n"
                    "Keep response under 3 sentences and be specific about risks."
                )
                
                max_retries = 3
                retry_delay = 2
                last_error = None
                
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Attempting API call for {orig_a} and {orig_b} (attempt {attempt + 1})")
                        
                        response = requests.post(
                            "https://api.deepseek.com/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": "deepseek-chat",
                                "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": 150,  # Increased token limit
                                "temperature": 0.3,  # Slightly increased for more detailed responses
                            },
                            timeout=15  # Increased timeout
                        )
                        
                        if response.status_code != 200:
                            logger.error(f"DeepSeek API error: Status {response.status_code}, Response: {response.text}")
                            raise Exception(f"API returned status {response.status_code}")
                        
                        data = response.json()
                        
                        if not data or 'choices' not in data:
                            logger.error(f"Unexpected API response format: {data}")
                            raise Exception("Invalid API response format")
                        
                        description = data['choices'][0]['message']['content'].strip()
                        if not description:
                            raise Exception("Empty response from API")
                        
                        severity = calculate_severity(description)
                        
                        interaction = {
                            'drugs': [orig_a, orig_b],
                            'description': description,
                            'severity': severity,
                            'source': 'DeepSeek'
                        }
                        
                        # Cache successful response for 24 hours
                        cache.set(pair_key, interaction, timeout=86400)
                        interactions.append(interaction)
                        break
                        
                    except Exception as e:
                        last_error = str(e)
                        logger.error(f"Attempt {attempt + 1} failed for {orig_a} and {orig_b}: {str(e)}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                            continue
                        
                        # If all retries failed, create a more informative fallback message
                        interaction = {
                            'drugs': [orig_a, orig_b],
                            'description': (
                                f"These medications may have significant interactions. "
                                f"Unable to fetch detailed data due to technical issues. "
                                f"Please consult with your healthcare provider before combining these medications."
                            ),
                            'severity': 2,  # Default to medium severity for safety
                            'source': 'Fallback',
                            'error': last_error  # Include error for debugging
                        }
                        # Cache failed response for shorter time
                        cache.set(pair_key, interaction, timeout=3600)
                        interactions.append(interaction)
                        
            except Exception as e:
                logger.error(f"Unexpected error processing {orig_a} and {orig_b}: {str(e)}")
                continue
    
    if interactions:
        cache.set(cache_key, interactions, timeout=86400)  # Cache for 24 hours
    
    return interactions