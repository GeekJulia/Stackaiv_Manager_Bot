import threading
import time
from functools import wraps
from ..database.queries import conn as db_conn

class DatabaseTimeoutError(Exception):
    """Custom exception for database timeouts"""
    pass

def with_db_timeout(timeout_seconds=10):
    """
    Decorator to add timeout to database operations
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=timeout_seconds)
            
            if thread.is_alive():
                raise DatabaseTimeoutError(
                    f"Database operation timed out after {timeout_seconds} seconds"
                )
            
            if exception[0]:
                raise exception[0]
            
            return result[0]
        return wrapper
    return decorator

def safe_db_operation(func, fallback_value=None, *args, **kwargs):
    """
    Safely execute a database operation with proper error handling
    """
    try:
        return func(*args, **kwargs)
    except DatabaseTimeoutError:
        raise
    except Exception as e:
        # Log the error (in production, use proper logging)
        print(f"Database error in {func.__name__}: {e}")
        raise