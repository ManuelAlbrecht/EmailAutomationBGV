import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ssl
import time
import logging
from typing import List, Dict
from email.header import decode_header

class IMAPMonitor:
    def __init__(self, 
                 imap_server: str, 
                 username: str, 
                 password: str, 
                 imap_port: int = 993,
                 check_interval: int = 60):
        
        """
        Initialize IMAP email monitor
        
        :param imap_server: IMAP server address
        :param username: Email username
        :param password: Email password
        :param imap_port: IMAP server port (default 993)
        :param check_interval: Interval between email checks in seconds
        """
        self.imap_server = imap_server
        self.username = username
        self.password = password
        self.imap_port = imap_port
        self.check_interval = check_interval
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def _create_secure_imap_connection(self) -> imaplib.IMAP4_SSL:
        """
        Create a secure IMAP connection with robust error handling
        
        :return: Secure IMAP connection
        """
        try:
            # Create a secure SSL context
            context = ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED

            # Attempt to connect with default SSL
            mail = imaplib.IMAP4_SSL(
                self.imap_server, 
                self.imap_port, 
                ssl_context=context
            )
            mail.login(self.username, self.password)
            return mail
        
        except ssl.SSLError as ssl_err:
            self.logger.warning(f"SSL Error: {ssl_err}. Attempting fallback.")
            try:
                # Fallback to explicit TLS version
                mail = imaplib.IMAP4_SSL(
                    self.imap_server, 
                    self.imap_port, 
                    ssl_version=ssl.PROTOCOL_TLSv1_2
                )
                mail.login(self.username, self.password)
                return mail
            except Exception as e:
                self.logger.error(f"IMAP Connection Error: {e}")
                raise
    
    def _decode_email_header(self, header: str) -> str:
        """
        Decode email headers to handle non-ASCII characters
        
        :param header: Encoded email header
        :return: Decoded header
        """
        decoded_parts = []
        for part, encoding in decode_header(header):
            if isinstance(part, bytes):
                decoded_part = part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_part = part
            decoded_parts.append(decoded_part)
        return ' '.join(decoded_parts)
    
    def _parse_email(self, raw_email: bytes) -> Dict[str, str]:
        """
        Parse raw email into a structured dictionary
        
        :param raw_email: Raw email bytes
        :return: Parsed email dictionary
        """
        email_message = email.message_from_bytes(raw_email)
        
        # Decode headers safely
        subject = self._decode_email_header(email_message.get('Subject', ''))
        sender = self._decode_email_header(email_message.get('From', ''))
        
        # Extract email body
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break
        else:
            body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        return {
            'subject': subject,
            'sender': sender,
            'body': body.strip(),
            'timestamp': email_message.get('Date')
        }
    
    def monitor_emails(self, mailbox: str = 'INBOX') -> List[Dict[str, str]]:
        """
        Monitor emails in specified mailbox
        
        :param mailbox: Mailbox to monitor (default INBOX)
        :return: List of new email dictionaries
        """
        mail = self._create_secure_imap_connection()
        
        try:
            # Select the mailbox
            mail.select('"INBOX/Hide/einkauf1@erdbaron.com"')
            # Search for unseen emails
            _, search_data = mail.search(None, 'UNSEEN')
            
            new_emails = []
            for num in search_data[0].split():
                try:
                    # Fetch the entire email
                    _, data = mail.fetch(num, '(RFC822)')
                    raw_email = data[0][1]
                    
                    # Parse and process email
                    parsed_email = self._parse_email(raw_email)
                    new_emails.append(parsed_email)
                    
                    # Mark email as seen
                    mail.store(num, '+FLAGS', '\\Seen')
                    
                    self.logger.info(f"New email from {parsed_email['sender']}")
                except Exception as email_error:
                    self.logger.error(f"Error processing email: {email_error}")
            
            return new_emails
        
        except Exception as e:
            self.logger.error(f"Email monitoring error: {e}")
            return []
        finally:
            mail.close()
            mail.logout()

class EmailHandler:
    def __init__(self, imap_server, imap_port, smtp_server, smtp_port, username, password,sender):
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender=sender
       
    
    def _connect_imap(self):
        """
        Establish IMAP connection with improved SSL context
        """
        # Create a secure SSL context
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        try:
            # Try connecting with the default SSL/TLS protocol
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, ssl_context=context)
            mail.login(self.username, self.password)
            return mail
        except ssl.SSLError:
            # Fallback to explicit SSL/TLS version if default fails
            try:
                mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port, ssl_version=ssl.PROTOCOL_TLSv1_2)
                mail.login(self.username, self.password)
                return mail
            except Exception as e:
                print(f"IMAP Connection Error: {e}")
                raise
    
    def _connect_smtp(self):
        """
        Establish SMTP connection with improved SSL context
        """
        # Create a secure SSL context
        context = ssl.create_default_context()
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        try:
            # Try connecting with the default SSL/TLS protocol
            server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context)
            server.login(self.username, self.password)
            return server
        except ssl.SSLError:
            # Fallback to explicit SSL/TLS version if default fails
            try:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls(context=context)
                server.login(self.username, self.password)
                return server
            except Exception as e:
                print(f"SMTP Connection Error: {e}")
                raise
    
    def fetch_unread_emails(self):
        """
        Fetch unread emails from inbox
        """
        mail = self._connect_imap()
        mail.select('inbox')
        
        _, search_data = mail.search(None, 'UNSEEN')
        
        emails = []
        for num in search_data[0].split():
            _, data = mail.fetch(num, '(RFC822)')
            raw_email = data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            emails.append({
                'subject': email_message['Subject'],
                'from': email_message['From'],
                'body': self._get_email_body(email_message),
                'message_id': email_message['Message-ID']
            })
        
        mail.close()
        mail.logout()
        return emails
    
    def _get_email_body(self, email_message):
        """
        Extract email body text
        """
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = email_message.get_payload(decode=True).decode()
        
        return body
    
    def send_non_personalizedtemplate_email(self, entry):
        """
        Send initial email template to entry
        """
        msg = MIMEMultipart()
        msg['From'] = f"Einkauf Erdbaron <{self.sender}>"
        msg['To'] = entry
        msg['Subject'] = f"Anfrage: Probenehmer LAGA PN 98"
        
        # Customize email template based on entry
        body = f"""
        Sehr geehrte Damen und Herren,

        wir sind auf der Suche nach zuverlässigen Probenehmer für Boden und Bauschutt.

        Hätten Sie generell Interesse für uns als Probenehmer tätig zu werden?

        Über die Erdbaron Akademie könnten Sie bei Bedarf Ihre Schulung für die LAGA PN 98 stark vergünstigt machen bzw. auffrischen.

        Über eine kurze Rückmeldung würden wir uns freuen und verbleiben mit

        Mit freundlichen Grüßen

        Einkaufs-Team

        Telefon: +49 (0)7041 806-9900

        Web: www.erdbaron.com

        Erdbaron HQ S.R.L.

        Strada Preot Bacca 13

        550145 Hermannstadt
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        with self._connect_smtp() as server:
            server.send_message(msg)
    
    def send_personalizedtemplate_email(self, email, anrede, nachname, vorname):
        """
        Send initial email template to entry
        """
        msg = MIMEMultipart()
        msg['From'] = f"Einkauf Erdbaron <{self.sender}>"
        msg['To'] = email
        msg['Subject'] = f"Anfrage: Probenehmer LAGA PN 98"
        
        # Customize email template based on entry
        body = f"""
        Dear {anrede} {nachname},

        We are looking for a reliable sampler for soil and construction debris in the vicinity of.

        Would you generally be interested and have the capacity to take samples for us in the area around ?

        A prerequisite would be technical and specialized knowledge in accordance with LAGA PN 98.

        I would appreciate a brief response and remain

        With kind regards,

        Purchasing Team

        Phone: +49 (0)7041 806-9900

        Web: www.erdbaron.com

        Erdbaron HQ S.R.L.

        Strada Preot Bacca 13

        550145 Hermannstadt

        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        with self._connect_smtp() as server:
            server.send_message(msg)
    
    def send_followup_email(self, entry):
        """
        Send follow-up email for an entry
        """
        
        msg = MIMEMultipart()
        msg['From'] = f"Einkauf Erdbaron <{self.sender}>"
        msg['To'] = entry['email']
        msg['Subject'] = f"Follow-up:Mail"
        
        body = f"""
        Dear {entry['email']},

        We haven't heard back from you regarding our previous email.
        Could you please provide the requested information?

        Best regards,
        Your Company
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        with self._connect_smtp() as server:
            server.send_message(msg)
            
    def send_status_email(self,  recipient_email, body):
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"Einkauf Erdbaron <{self.sender}>"
        msg['To'] = recipient_email
        msg['Subject'] = "Re: Anfrage: Probenehmer LAGA PN 98"
        msg.attach(MIMEText(body, 'plain'))
        # Send the email
        try:
            with self._connect_smtp() as server:
                server.send_message(msg)
                return True
        except Exception as e:
            print(f"Error sending status email: {e}")
            return False
            