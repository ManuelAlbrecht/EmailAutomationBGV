import os
import openai
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

class AssistantTester:
    """
    This class uses OpenAI's Assistant API to analyze inbound emails
    and generate responses for Bodengutachter.
    """
    def __init__(self):
        """
        Initialize the AssistantTester by loading API credentials and assistant ID 
        from environment variables.
        """
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.assistant_id = os.getenv("ASSISTANT_ID", "")
        
        # Create an OpenAI client instance
        self.client = OpenAI(api_key=self.api_key)
    
    def ai_assistant(self, email_data):
        """
        Sends the email data to the OpenAI assistant and returns the assistant's response.
        
        Args:
            email_data (dict): A dictionary with keys like 'subject' and 'body'.
        
        Returns:
            str: The assistant's response text or an error message.
        """
        try:
            subject = email_data.get('subject', '')
            body = email_data.get('body', '')

            # Optionally, combine subject + body for context. 
            # (If you only want the body, remove subject from content.)
            full_text = f"Subject: {subject}\n\nBody: {body}"

            # 1. Create a new thread
            thread = self.client.beta.threads.create()
            
            # 2. Add the user's message to the thread
            message = self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=full_text
            )
            
            # 3. Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )
            
            # 4. Poll until the run is complete
            while run.status != "completed":
                run = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            
            # 5. Retrieve the assistant's response
            messages = self.client.beta.threads.messages.list(thread_id=thread.id)
            for msg in messages.data:
                if msg.role == "assistant":
                    # Return the text from the assistant
                    return msg.content[0].text.value
            
            return "No response from assistant"
        
        except Exception as e:
            # Return the error string if something goes wrong
            return f"Error: {str(e)}"
