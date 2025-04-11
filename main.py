import os
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from zoho_crm import ZohoCRMService
from email_handler import EmailHandler, IMAPMonitor
from ai_processor import AssistantTester
from logging_service import setup_logging
import re
from datetime import datetime,timedelta, timezone
import pytz
from flask_apscheduler import APScheduler
import requests
from apscheduler.schedulers.background import BackgroundScheduler
import random

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure logging
logger = setup_logging()

# Initialize services
zoho_crm_service = ZohoCRMService(
    client_id=os.getenv('ZOHO_CLIENT_ID'),
    client_secret=os.getenv('ZOHO_CLIENT_SECRET'),
    refresh_token=os.getenv('ZOHO_REFRESH_TOKEN')
)

email_handler = EmailHandler(
    imap_server=os.getenv('IMAP_SERVER'),
    imap_port=os.getenv('IMAP_PORT'),
    smtp_server=os.getenv('SMTP_SERVER'),
    smtp_port=os.getenv('SMTP_PORT'),
    username=os.getenv('EMAIL_USERNAME'),
    password=os.getenv('EMAIL_PASSWORD'),
    sender=os.getenv('SENDER_EMAIL')
)
imap_monitor = IMAPMonitor(
    imap_server=os.getenv('IMAP_SERVER'),
    username=os.getenv('EMAIL_USERNAME'),
    password=os.getenv('EMAIL_PASSWORD'),
    imap_port=int(os.getenv('IMAP_PORT', 993)),
    check_interval=60
)

scheduler = BackgroundScheduler()


claude_processor = AssistantTester(
    api_key= os.getenv('OPENAI_API_KEY'),
    assistant_id=os.getenv('ASSISTANT_ID')
)

# Send email using your existing email_handler
def process_monitored_emails():
    """
    process monitored emails
    """ 
    try:
        # Monitor and fetch new emails
        new_emails = imap_monitor.monitor_emails()
        if new_emails:
            print(f"Found {len(new_emails)} new emails")
            for email_data in new_emails:
                logger.info(f"Processing email: {email_data['sender']}")
                # Detailed email processing
                try:
                    # Classify email response using AI processor
                    ai_response = claude_processor.ai_assistant(email_data)
                    print(ai_response)
                    # Log AI classification
                    logger.info(f"AI Classification: {ai_response}")
                    filtered_lines = [line for line in ai_response.split('\n') if not line.startswith("STATUS:")]
                    # Join the remaining lines back together
                    body = '\n'.join(filtered_lines)
                    status_line = ai_response.split("STATUS: ")[1].split("\n")[0].strip()
                    if status_line == 'FOLLOWUP':
                        status_line='Follow Up'
                    
                    sender = email_data['sender']
                    sender_email = sender.split('<')[1].split('>')[0] if '<' in sender and '>' in sender else sender
                    logger.info(f"Sending status email to {sender_email} with status")
                    
                    success = email_handler.send_status_email(sender_email,body,)
        
                    if success:
                        logger.info(f"Successfully sent email to {sender_email}")
                    else:
                        logger.error(f"Failed to send email to {sender_email}")
                        
                    # Update CRM entry status
                    # Fetch CRM data
                    data = zoho_crm_service.fetch_zoho_record_by_email(sender_email)
                
                    if not data:
                        logger.warning(f"No Zoho record found for email {sender_email}")
                        continue
                    record_id, followup_hist = data
                    zoho_crm_service.update_entry_status(
                        entry_id=record_id,
                        status=status_line,
                        )
                        
                except Exception as email_process_error:
                    logger.error(f"Error processing individual email: {email_process_error}")
                    logger.exception(email_process_error)
        
        # Wait before next check
        time.sleep(imap_monitor.check_interval)
    
    except Exception as e:
        logger.error(f"Error in email monitoring thread: {e}")
        logger.exception(e)  # Log the full stack trace
        time.sleep(60)  # Wait before retrying after error
        

            
def extract_entry_id_from_email(email_data):
    """
    Extract CRM entry ID from email using multiple extraction strategies.
    
    Args:
        email_data (dict): Dictionary containing email information
    
    Returns:
        str or None: Extracted entry ID or None if no ID found
    """
    try:
        # 1. Extract from email subject (most precise method)
        subject_match = re.search(r'(?:Entry[-\s]?ID|CRM\s?Reference|Ticket\s?Number)[\s:]?(\d+)', 
                                  email_data['subject'], re.IGNORECASE)
        if subject_match:
            return subject_match.group(1)
        
        # 2. Extract from email body
        body_match = re.search(r'(?:Entry[-\s]?ID|CRM\s?Reference|Ticket\s?Number)[\s:]?(\d+)', 
                               email_data['body'], re.IGNORECASE)
        if body_match:
            return body_match.group(1)
        
        # 3. Extract from sender email domain or local part
        sender_email = email_data.get('sender', '')
        domain_match = re.search(r'(\d+)', sender_email)
        if domain_match:
            return domain_match.group(1)
        
        # 4. Hash-based ID generation if no explicit ID found
        if email_data.get('sender') and email_data.get('timestamp'):
            import hashlib
            
            # Create a unique hash based on sender and timestamp
            id_string = f"{email_data['sender']}_{email_data['timestamp']}"
            hash_id = hashlib.md5(id_string.encode()).hexdigest()[:10]
            return hash_id
        
        return None
    
    except Exception as e:
        logger.error(f"Error extracting entry ID: {e}")
        return None
    
@app.route('/process_email_queue', methods=['POST'])
def process_email_queue():
    """
    Endpoint to trigger email processing for CRM entries
    """
    try:
        # Fetch entries from Zoho CRM that need email processing
        entries = zoho_crm_service.get_entries_for_email_processing()
        
        for entry in entries:
            email = entry['Email']
            anrede = entry.get('Anrede', '')
            nachname = entry.get('Nachname', '')
            vorname = entry.get('Vorname', '')
            data = zoho_crm_service.fetch_zoho_record_by_email(email)
            if not data:
                logger.warning(f"No Zoho record found for email {email}")
            record_id, followup_hist = data
            if not anrede and not nachname and not vorname:
                email_handler.send_non_personalizedtemplate_email(email)
            else:
                email_handler.send_personalizedtemplate_email(
                    email, anrede, nachname, vorname
                )
            timezone =pytz.timezone('Europe/Moscow')
            current_time = datetime.now(timezone)

            formatted_time = current_time.replace(microsecond=0).isoformat()
            
            zoho_crm_service.update_mailsent_status(
                entry_id=record_id,
                mail_sent=formatted_time
            )
                        
        return jsonify({"status": "success", "processed_entries": len(entries)}), 200
    except Exception as e:
        logger.error(f"Error processing email queue: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    

@app.route('/send_followups', methods=['POST'])

def process_followup():
    try:
        # Fetch entries from Zoho CRM that need email processing
        entries = zoho_crm_service.get_entries_for_email_processing()
        for entry in entries:
            email = entry['Email']
            mail_sent = entry.get('mailSent', '')
            modified_time=entry.get('Modified_Time','')
            folcount=entry.get('Followup_Count')
            if mail_sent:
                mail_sent_dt = datetime.strptime(mail_sent, "%Y-%m-%dT%H:%M:%S%z")
                # Calculate the difference
                time_difference = modified_time - mail_sent_dt
                data = zoho_crm_service.fetch_zoho_record_by_email(email)
                if not data:
                    logger.warning(f"No Zoho record found for email {email}")
                record_id, followup_hist = data
                # Update follow-up count
                if followup_hist is None:
                    followup_count = 1
                else:
                    followup_count = followup_hist + 1
                if time_difference > timedelta(days=5):
                    if folcount > 3:
                        zoho_crm_service.update_status(
                        entry_id=record_id,
                        status='Uninteressiert'
                        )
                    email_handler.send_followup_email(entry)
                    zoho_crm_service.update_mailsent_status(
                    entry_id=record_id,
                    follow_up_count=followup_count
                )
                
        return jsonify({"status": "success", "processed_entries": len(entries)}), 200
    
    except Exception as e:
        logger.error(f"Error processing email queue: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500
    
    
def schedule_followups():
    with app.app_context():
        try:
            # Create a test request context to simulate a POST request
            with app.test_client() as client:
                response = client.post('/send_followups')
                if response.status_code == 200:
                    logger.info("Scheduled followups executed successfully")
                else:
                    logger.error(f"Scheduled followups failed with status: {response.status_code}")
        except Exception as e:
            logger.error(f"Error in scheduled followups: {str(e)}")



def schedule_email_processing():
    """Schedule process_monitored_emails() to run at 3 random times per day."""
    today = datetime.today().weekday()
    if today in [5, 6]:  # 5 = Saturday, 6 = Sunday
        logger.info("Skipping email scheduling because today is a weekend.")
        return 
    # Remove only jobs related to email processing
    for job in scheduler.get_jobs():
        if job.id.startswith("email_processing_"):
            scheduler.remove_job(job.id)
    
    base_time = 9  # Start from 9 AM
    for i in range(3):
        random_hour = base_time + random.randint(0, 3) + (i * 3)  # Ensure at least 3-hour gap
        random_minute = random.randint(0, 59)
        
        job_id = f"email_processing_{i+1}"
        scheduler.add_job(
            func=process_monitored_emails,
            trigger="cron",
            hour=random_hour,
            minute=random_minute,
            id=job_id,
            name=f"Email processing {i+1}",
            replace_existing=True
        )
        logger.info(f"Scheduled email processing {i+1} at {random_hour}:{random_minute}")




job1= scheduler.add_job(
    func=schedule_followups,
    trigger='cron',
    hour=9,
    minute=0,
    id='daily_followups',
    name='Send daily followup emails',
    replace_existing=True
)


job2= scheduler.add_job(
    func=schedule_email_processing,
    trigger="cron",
    hour=0,
    minute=0,
    id="daily_reschedule",
    name="Reschedule email processing",
    replace_existing=True
)

if __name__ == '__main__':
    scheduler.start()
    print("scheduler started")
    app.run(
        host='0.0.0.0', 
        port=int(os.getenv('PORT', 5000)), 
        debug=os.getenv('FLASK_DEBUG', False)
    )

