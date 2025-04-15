import os
import time
import imaplib
from dotenv import load_dotenv
import logging

from logging_service import setup_logging
from email_handler import EmailHandler
from zoho_crm import ZohoCRMService
from ai_processor import AssistantTester

# ---------------------- Load Environment ----------------------
load_dotenv()

# ---------------------- Setup Logging -------------------------
logger = setup_logging()

# ---------------------- Create Service Instances --------------
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

assistant_tester = AssistantTester()

# A quick dictionary to map AI status tokens to Zoho dropdown values
STATUS_MAPPING = {
    "FOLLOWUP": "Follow Up",
    "INTERESSIERT": "Interessiert",
    "UNINTERESSIERT": "Uninteressiert",
    "KLAERUNG": "Klärung",
    "COMPLETED": "Interessiert",
    "NOT INTERESTED": "Uninteressiert"
}

def main_loop():
    """
    Continuously fetch unread Bodengutachter emails,
    feed them to the AI, parse and remove the STATUS line,
    map the raw status to a valid CRM dropdown value,
    send the AI's textual response back, and update Zoho CRM.
    """
    logger.info("Starting main Bodengutachter loop...")

    while True:
        try:
            # 1. Fetch all matching unread emails
            new_emails = email_handler.fetch_unread_emails()
            if new_emails:
                logger.info(f"Found {len(new_emails)} new email(s) for Bodengutachter.")

            # 2. Process each email
            for email_data in new_emails:
                subject = email_data.get('subject', '')
                sender = email_data.get('from', '')

                logger.info(f"Processing email from {sender} with subject: {subject}")

                # Extract the pure email address (e.g. from "Name <user@example.com>")
                if '<' in sender and '>' in sender:
                    sender_email = sender.split('<')[1].split('>')[0].strip()
                else:
                    sender_email = sender.strip()

                # 2a. Get AI's response
                ai_response = assistant_tester.ai_assistant(email_data)
                logger.info(f"AI Raw Response:\n{ai_response}")

                # 2b. Parse out any STATUS line, remove it from final reply
                status_value = "Mail Received"  # fallback if no known status
                filtered_lines = []

                for line in ai_response.split('\n'):
                    if line.strip().startswith("STATUS:"):
                        # Extract raw token after "STATUS:"
                        raw_status = line.split("STATUS:", 1)[1].strip().upper()  # e.g. "FOLLOWUP"
                        # Map to Zoho-friendly label if recognized
                        status_value = STATUS_MAPPING.get(raw_status, "Mail Received")
                    else:
                        filtered_lines.append(line)

                final_reply = '\n'.join(filtered_lines).strip()

                # 2c. Send the AI-generated reply (minus status line) back
                sent_ok = email_handler.send_status_email(sender, final_reply)
                if sent_ok:
                    logger.info(f"Successfully sent AI reply to {sender}")
                else:
                    logger.error(f"Failed to send AI reply to {sender}")

                # 2d. Update Zoho CRM with mapped status
                record_id = zoho_crm_service.fetch_zoho_record_by_email(sender_email)
                if record_id:
                    zoho_crm_service.update_record_status(record_id, status_value)
                    logger.info(f"Updated Zoho record {record_id} with status: {status_value}")
                else:
                    logger.warning(f"No Zoho record found for {sender_email}")

            # 3. Sleep for a few seconds, then loop again
            time.sleep(10)

        except imaplib.IMAP4.error as imap_err:
            logger.error(f"IMAP error: {imap_err}. Retrying in 30 seconds.", exc_info=True)
            time.sleep(30)
            continue

        except KeyboardInterrupt:
            logger.info("Shutting down gracefully (KeyboardInterrupt).")
            break

        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(30)

if __name__ == "__main__":
    main_loop()
