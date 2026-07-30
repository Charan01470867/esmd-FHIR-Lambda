import logging

def setup_logger(name: str):
    """Sets up a logger with a standard format and console handler."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Check if logger already has handlers to avoid adding multiple handlers
    if not logger.handlers:
        # Create a console handler with a DEBUG level
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        
        # Create a formatter and set it for the handler
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        
        # Add the console handler to the logger
        logger.addHandler(ch)
    
    return logger
