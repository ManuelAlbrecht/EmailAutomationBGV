import requests
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2):
    """
    Decorator to retry a function call upon exception with exponential backoff.
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
                        logger.error(f"Max retries reached: {str(e)}")
                        raise
                    logger.warning(f"Request failed: {str(e)}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            return func(*args, **kwargs)
        return wrapper
    return decorator

class ZohoCRMService:
    """
    A service class for interacting with the 'Bodengutachter' module in Zoho CRM.
    """
    def __init__(self, client_id, client_secret, refresh_token):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.access_token = self._get_access_token()

    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    def _get_access_token(self):
        """
        Obtain a new access token using the refresh token.
        """
        token_url = "https://accounts.zoho.eu/oauth/v2/token"
        params = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }
        
        response = requests.post(token_url, data=params)
        response.raise_for_status()
        data = response.json()
        
        if "access_token" not in data:
            raise requests.exceptions.RequestException(f"Failed to get access token: {data}")
        
        return data["access_token"]

    def _refresh_token_if_needed(self, response):
        """
        If we get 401 (Unauthorized), try to refresh the token.
        """
        if response.status_code == 401:
            logger.info("Access token expired. Refreshing token...")
            self.access_token = self._get_access_token()
            return True
        return False

    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    def fetch_zoho_record_by_email(self, email):
        """
        Search the Bodengutachter module by Email.
        Returns the record ID if found, else None.
        """
        url = "https://www.zohoapis.eu/crm/v2/Bodengutachter/search"
        params = {
            "criteria": f"(Email:equals:{email})"
        }
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers, params=params)
        if self._refresh_token_if_needed(response):
            # Retry with the new token
            headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
            response = requests.get(url, headers=headers, params=params)
        
        response.raise_for_status()
        data = response.json()
        records = data.get("data", [])
        
        if records:
            record_id = records[0]["id"]
            return record_id
        else:
            return None

    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    def update_record_status(self, record_id, status_value):
        """
        Update the Mail_Status field for a given record in Bodengutachter.
        """
        url = f"https://www.zohoapis.eu/crm/v2/Bodengutachter/{record_id}"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "data": [{
                "id": record_id,
                "Mail_Status": status_value
            }]
        }
        
        response = requests.patch(url, headers=headers, json=payload)
        if self._refresh_token_if_needed(response):
            # Retry with the refreshed token
            headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
            response = requests.patch(url, headers=headers, json=payload)
        
        response.raise_for_status()
        return response.json()

    @retry_on_failure(max_retries=3, retry_delay=2, backoff_factor=2)
    def get_entries_for_email_processing(self):
        """
        Example method: fetch records in Bodengutachter that need emailing.
        Adjust the criteria as needed. For instance, 
        here we fetch records where Mail_Status is empty or null.
        """
        url = "https://www.zohoapis.eu/crm/v2/Bodengutachter/search"
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        # For example: fetch records where Mail_Status is blank
        params = {
            "criteria": "(Mail_Status:equals:)"
        }
        
        response = requests.get(url, headers=headers, params=params)
        if self._refresh_token_if_needed(response):
            headers["Authorization"] = f"Zoho-oauthtoken {self.access_token}"
            response = requests.get(url, headers=headers, params=params)
        
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
