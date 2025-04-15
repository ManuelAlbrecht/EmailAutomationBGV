import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
from typing import List, Dict
from email.header import decode_header
import logging

# You can use your existing logger setup from logging_service or create a local one here:
logger = logging.getLogger(__name__)

class EmailHandler:
    """
    This class handles both fetching inbound emails (filtered by subject)
    and sending out emails (templates, status replies, etc.) for Bodengutachter.
    """
    def __init__(self, imap_server, imap_port, smtp_server, smtp_port, username, password, sender):
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender

    def _connect_imap(self):
        """
        Establish a secure IMAP connection using SSL/TLS.
        """
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED
        
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, ssl_context=context)
            mail.login(self.username, self.password)
            return mail
        except ssl.SSLError:
            # Fallback to explicit TLS if default fails
            try:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, ssl_version=ssl.PROTOCOL_TLSv1_2)
                mail.login(self.username, self.password)
                return mail
            except Exception as e:
                logger.error(f"IMAP Connection Error: {e}")
                raise

    def _connect_smtp(self):
        """
        Establish a secure SMTP connection using SSL/TLS.
        """
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        try:
            server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context)
            server.login(self.username, self.password)
            return server
        except ssl.SSLError:
            # Fallback to explicit TLS if default fails
            try:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls(context=context)
                server.login(self.username, self.password)
                return server
            except Exception as e:
                logger.error(f"SMTP Connection Error: {e}")
                raise

    def _decode_email_header(self, header_value: str) -> str:
        """
        Decode an email header to handle non-ASCII or encoded text.
        """
        decoded_parts = []
        for part, encoding in decode_header(header_value):
            if isinstance(part, bytes):
                decoded_part = part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_part = part
            decoded_parts.append(decoded_part)
        return ' '.join(decoded_parts)

    def _get_email_body(self, email_message) -> str:
        """
        Extract the plain-text email body from a (potentially) multipart email.
        """
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        return body.strip()

    def fetch_unread_emails(self) -> List[Dict[str, str]]:
        """
        Fetch unread emails from the inbox that have the subject: 
        'Anfrage: Baugrundgutachten / Feldarbeiten'.
        
        Returns:
            A list of dictionaries, each with keys: 'subject', 'from', 'body'.
        """
        SUBJECT_FILTER = "Anfrage: Baugrundgutachten"
        
        mail = self._connect_imap()
        try:
            mail.select('"INBOX/Hide/einkauf1@erdbaron.com"')

            # Search for unread + exact subject match.
            # IMAP query requires the subject to be in quotes if it has spaces.
            search_criteria = f'(UNSEEN SUBJECT "{SUBJECT_FILTER}")'
            logger.info(f"Searching for emails with criteria: {search_criteria}")
            
            _, search_data = mail.search(None, search_criteria)
            email_list = []

            for num in search_data[0].split():
                _, data = mail.fetch(num, '(RFC822)')
                raw_email = data[0][1]
                email_message = email.message_from_bytes(raw_email)

                # Decode subject
                raw_subject = email_message.get('Subject', '')
                subject_decoded = self._decode_email_header(raw_subject)

                # Build a dictionary with relevant fields
                email_dict = {
                    'subject': subject_decoded,
                    'from': self._decode_email_header(email_message.get('From', '')),
                    'body': self._get_email_body(email_message)
                }

                email_list.append(email_dict)

                # Mark email as seen so we don't re-fetch it next time
                mail.store(num, '+FLAGS', '\\Seen')

                logger.info(f"Fetched email from {email_dict['from']} with subject: {subject_decoded}")

            return email_list
        
        except Exception as e:
            logger.error(f"Error fetching unread emails: {e}")
            return []
        finally:
            mail.close()
            mail.logout()

    # -------------------------------------------------------------------------
    # -------------------------- EMAIL SENDING METHODS -------------------------
    # -------------------------------------------------------------------------

    def send_non_personalizedtemplate_email(self, recipient):
        """
        Send an initial (non-personalized) Bodengutachter inquiry to the given recipient.
        """
        msg = MIMEMultipart()
        msg['From'] = f"Einkauf Erdbaron <{self.sender}>"
        msg['To'] = recipient
        # For outbound emails you might reuse or keep the subject the same:
        msg['Subject'] = "Anfrage: Baugrundgutachten / Feldarbeiten"
        
        body = """
Sehr geehrte Damen und Herren,

wir sind auf der Suche nach Fachleuten für Baugrundgutachten und Feldarbeiten.

Hätten Sie generell Interesse und Kapazität, solche Gutachten für uns durchzuführen?

Über eine kurze Rückmeldung würden wir uns freuen.

Mit freundlichen Grüßen

Einkaufs-Team Erdbaron
Telefon: +49 (0)7041 806-9900
Web: www.erdbaron.com
        """

        msg.attach(MIMEText(body, 'plain'))

        try:
            with self._connect_smtp() as server:
                server.send_message(msg)
                logger.info(f"Sent non-personalized Bodengutachter email to {recipient}")
        except Exception as e:
            logger.error(f"Error sending non-personalized Bodengutachter email: {e}")

    def send_personalizedtemplate_email(self, recipient, anrede, nachname, vorname):
        """
        Send a personalized Bodengutachter inquiry, using
        e.g. the person's name or salutation.
        """
        msg = MIMEMultipart()
        msg['From'] = f"Einkauf Erdbaron <{self.sender}>"
        msg['To'] = recipient
        msg['Subject'] = "Anfrage: Baugrundgutachten / Feldarbeiten"

        body = f"""
Sehr geehrte/r {anrede} {nachname},

wir sind auf der Suche nach Fachleuten wie Ihnen ({vorname} {nachname}) 
für Baugrundgutachten und Feldarbeiten.

Hätten Sie generell Interesse und Kapazität, solche Gutachten für uns durchzuführen?

Wir freuen uns auf Ihre Rückmeldung.

Mit freundlichen Grüßen

Einkaufs-Team Erdbaron
Telefon: +49 (0)7041 806-9900
Web: www.erdbaron.com
        """

        msg.attach(MIMEText(body, 'plain'))

        try:
            with self._connect_smtp() as server:
                server.send_message(msg)
                logger.info(f"Sent personalized Bodengutachter email to {recipient}")
        except Exception as e:
            logger.error(f"Error sending personalized Bodengutachter email: {e}")

    def send_followup_email(self, recipient):
        """
        Send a follow-up email (if you decide to implement follow-ups 
        for Bodengutachter).
        """
        msg = MIMEMultipart()
        msg['From'] = f"Einkauf Erdbaron <{self.sender}>"
        msg['To'] = recipient
        msg['Subject'] = "Follow-up: Baugrundgutachten / Feldarbeiten"

        body = f"""
Sehr geehrte Damen und Herren,

wir wollten noch einmal nachhaken, ob Sie Interesse am Thema 
Baugrundgutachten und Feldarbeiten haben.

Über eine kurze Rückmeldung würden wir uns sehr freuen!

Mit freundlichen Grüßen

Einkaufs-Team Erdbaron
Telefon: +49 (0)7041 806-9900
Web: www.erdbaron.com
        """

        msg.attach(MIMEText(body, 'plain'))

        try:
            with self._connect_smtp() as server:
                server.send_message(msg)
                logger.info(f"Sent follow-up Bodengutachter email to {recipient}")
        except Exception as e:
            logger.error(f"Error sending follow-up Bodengutachter email: {e}")

    def send_status_email(self, recipient_email, body):
        """
        Send an email containing the AI-composed response (or status update)
        to the sender of an inbound email.
        """
        msg = MIMEMultipart()
        msg['From'] = f"Einkauf Erdbaron <{self.sender}>"
        msg['To'] = recipient_email
        msg['Subject'] = "Re: Anfrage: Baugrundgutachten / Feldarbeiten"
        
        msg.attach(MIMEText(body, 'plain'))

        try:
            with self._connect_smtp() as server:
                server.send_message(msg)
            logger.info(f"Sent status reply email to {recipient_email}")
            return True
        except Exception as e:
            logger.error(f"Error sending status email: {e}")
            return False
