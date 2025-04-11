import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    Configure logging with rotating file handler
    """
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Configure logger
    logger = logging.getLogger('email_processor')
    logger.setLevel(logging.INFO)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # File Handler (Rotating)
    file_handler = RotatingFileHandler(
        'logs/email_processor.log', 
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger