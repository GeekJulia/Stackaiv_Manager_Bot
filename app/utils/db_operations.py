import time
import threading
from functools import wraps

class DatabaseTimeoutError(Exception):
    """Custom exception for database timeouts"""
    pass

def with_db_timeout(timeout_seconds=10):
    """Decorator to add timeout to database operations"""
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
    Safely execute a database operation with one silent retry.
    
    The first attempt after a period of inactivity may hit a stale/cold
    connection. We catch that specific case, wait briefly, then retry once
    before surfacing any error to the user.
    """
    RETRYABLE_PHRASES = (
        "connection",
        "timeout",
        "closed",
        "broken pipe",
        "eof detected",
        "ssl",
        "could not connect",
        "server closed",
    )
# heat production
    def attempt(): 
        try:
            return func(*args, **kwargs)
        except DatabaseTimeoutError:
            raise  # Never swallow explicit timeouts — let caller handle
        except Exception as e:
            raise e

    try:
        return attempt()

    except DatabaseTimeoutError:
        raise  # Propagate immediately, no retry

    except Exception as first_error:
        error_msg = str(first_error).lower()
        is_connection_error = any(phrase in error_msg for phrase in RETRYABLE_PHRASES)

        if is_connection_error:
            print(f"[DB] Connection error on first attempt ({func.__name__}): {first_error}. Retrying in 2s...")
            time.sleep(2)  # Brief pause to let pool establish a fresh connection
            try:
                return attempt()
            except DatabaseTimeoutError:
                raise
            except Exception as second_error:
                print(f"[DB] Retry also failed ({func.__name__}): {second_error}")
                raise second_error  # Raise so start.py shows error to user
        else:
            # Non-connection error (e.g. bad query, constraint violation) — don't retry
            print(f"Database error in {func.__name__}: {first_error}")
            raise