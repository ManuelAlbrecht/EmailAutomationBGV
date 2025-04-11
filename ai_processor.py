import openai
from openai import OpenAI

class AssistantTester:
    
    def __init__(self, api_key, assistant_id):
        """
        Initialize the AssistantTester with API key and assistant ID.
        
        Args:
            api_key (str): Your OpenAI API key
            assistant_id (str): Your assistant's ID
        """
        self.client = OpenAI(api_key=api_key)
        self.assistant_id = assistant_id
    
    def ai_assistant(self, email_data):
        """
        Test your GPT assistant with a user message.
        
        Args:
            user_message (str): Message to send to the assistant
            
        Returns:
            str: Assistant's response or error message
        """
        
        try:
            # Create a thread
            subject = email_data.get('subject', '')
            body = email_data.get('body', '')
            
            # Combine subject and body
            full_text = f"Subject: {subject}\n\nBody: {body}"

            thread = self.client.beta.threads.create()
            
            # Add a message to the thread
            message = self.client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=body
            )
            
            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread.id,
                assistant_id=self.assistant_id
            )
            
            # Wait for completion
            while run.status != "completed":
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
            
            # Retrieve the assistant's response
            messages = self.client.beta.threads.messages.list(
                thread_id=thread.id
            )
            
            # Return the latest assistant message
            for msg in messages.data:
                if msg.role == "assistant":
                    return msg.content[0].text.value
            
            return "No response from assistant"
        
        except Exception as e:
            return f"Error: {str(e)}"
    
    def batch_test(self, test_messages):
        """
        Test the assistant with multiple messages.
        
        Args:
            test_messages (list): List of messages to test
            
        Returns:
            dict: Dictionary of messages and responses
        """
        results = {}
        for msg in test_messages:
            response = self.ai_assistant(msg)
            results[msg] = response
        return results