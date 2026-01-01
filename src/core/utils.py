import time
import functools
from .logger import logger

def retry(max_retries: int = 3, delay: int = 5, backoff: int = 2, exceptions: tuple = (Exception,)):
    """
    Decorator to retry a function with exponential backoff.
    
    Args:
        max_retries (int): Maximum number of retries.
        delay (int): Initial delay between retries in seconds.
        backoff (int): Multiplier for the delay after each retry.
        exceptions (tuple): Exceptions that trigger a retry.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries. Error: {e}")
                        raise
                    logger.warning(f"Function {func.__name__} failed. Retrying in {current_delay}s... (Attempt {retries}/{max_retries})")
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
