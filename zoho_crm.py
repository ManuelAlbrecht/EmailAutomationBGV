import os
import requests
import time
from datetime import datetime, timedelta
from functools import wraps

def retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2):
    """
    Decorator to retry a function call upon exception with exponential backoff.
    
    Args:
        max_retries (int): Maximum number of retries before giving up
        retry_delay (int): Initial delay in seconds between retries
        backoff_factor (int): Factor by which the delay increases with each retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retry_count = 0
            current_delay = retry_delay
            
            while retry_count < max_retries:
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        print(f"Maximum retries ({max_retries}) reached. Failing with error: {str(e)}")
                        raise
                    
                    print(f"Request failed: {str(e)}. Retrying in {current_delay} seconds... (Attempt {retry_count} of {max_retries})")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor  # Exponential backoff
            
            return func(*args, **kwargs)  # One final attempt
        return wrapper
    return decorator

class ZohoCRMService:
    def __init__(self, client_id, client_secret, refresh_token, max_retries=3):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.max_retries = max_retries
        self.access_token = self._get_access_token()
    
    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    def _get_access_token(self):
        """
        Obtain a new access token using refresh token with retry mechanism
        """
        token_url = 'https://accounts.zoho.eu/oauth/v2/token'
        params = {
            'refresh_token': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token'
        }
        
        response = requests.post(token_url, data=params)
        response.raise_for_status()  # Will raise exception for HTTP errors
        token_data = response.json()
        
        if 'access_token' not in token_data:
            raise requests.exceptions.RequestException(f"Failed to get access token: {token_data}")
            
        return token_data.get('access_token')
    
    def _refresh_token_if_needed(self, response):
        """
        Check if the token has expired and refresh if needed
        """
        if response.status_code == 401:
            print("Access token expired. Refreshing token...")
            self.access_token = self._get_access_token()
            return True
        return False
    
    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    
    def get_entries_for_email_processing(self):
        """
        Fetch CRM entries that need initial email processing with retry mechanism
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            'https://www.zohoapis.eu/crm/v2/Probenehmer/search',
            headers=headers,
            params={'criteria': 'Email:equals:Developmentexpert121@gmail.com'}
        )
        
        response.raise_for_status()
        
        return response.json().get('data', [])
    
    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    
    def update_entry_status(self, entry_id, status):
        """
        Update CRM entry status, follow-up count with retry mechanism
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'data': [{
                'id': entry_id,
                'make_com_Status': status,
            }]
        }
        
        response = requests.patch(
            f'https://www.zohoapis.eu/crm/v2/Probenehmer/{entry_id}',
            headers=headers,
            json=payload
        )
        
        response.raise_for_status()
     
        return response.json()
    
    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    
    def update_status(self, entry_id, status):
        """
        Update CRM entry status with retry mechanism
        """
       
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'data': [{
                'id': entry_id,
                'make_com_Status': status,
            }]
        }
        
        response = requests.patch(
            f'https://www.zohoapis.eu/crm/v2/Probenehmer/{entry_id}',
            headers=headers,
            json=payload
        )
        
        response.raise_for_status()
        
        return response.json()
    
    
    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    def get_entries_for_followup(self):
        """
        Get entries that need follow-up with retry mechanism
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            'https://www.zohoapis.eu/crm/v2/Probenehmer/search',
            headers=headers,
            params={
                'criteria': f'make_com_Status:starts_with:i',
            }
        )
        
        response.raise_for_status()
        return response.json().get('data', [])
    
    
    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    def fetch_zoho_record_by_email(self, email):
        """
        Fetch Zoho CRM record by email with retry mechanism
        Returns tuple (record_id, followup_count) if found, None otherwise
        """
        url = "https://www.zohoapis.eu/crm/v2/Probenehmer/search"
        
        params = {
            "criteria": f"(Email:equals:{email})"
        }
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if data.get("data"):
                record_id = data["data"][0]["id"]
                followup_count = data["data"][0].get('Followup_Count', 0)
             
                return record_id, followup_count
            else:
                return None
        except requests.exceptions.RequestException:
            return None
        
        
        
    def update_mailsent_status(self, entry_id, mail_sent):
        """
        Update CRM entry status, follow-up count with retry mechanism
        """
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'data': [{
                'id': entry_id,
                'mailSent': mail_sent,
                
            }]
        }
        
        response = requests.patch(
            f'https://www.zohoapis.eu/crm/v2/Probenehmer/{entry_id}',
            headers=headers,
            json=payload
        )
        
        response.raise_for_status()
     
        return response.json()
    
    
    def update_followup(self, entry_id, follow_up_count):
        """
        Update CRM entry status with retry mechanism
        """
      
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'data': [{
                'id': entry_id,
                'Followup_Count': follow_up_count
            }]
        }
        
        response = requests.patch(
            f'https://www.zohoapis.eu/crm/v2/Probenehmer/{entry_id}',
            headers=headers,
            json=payload
        )
        
        response.raise_for_status()
        return response.json()
    