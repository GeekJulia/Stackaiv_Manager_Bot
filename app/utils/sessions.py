import time
import threading

class TTLDict(dict):
    """
    A dictionary with a Time-To-Live (TTL) for its items to prevent memory leaks.
    A background thread periodically cleans up expired items.
    """
    def __init__(self, ttl_seconds=86400, cleanup_interval_seconds=3600): # Default 24h TTL, 1h cleanup
        super().__init__()
        self.ttl = ttl_seconds
        self.cleanup_interval = cleanup_interval_seconds
        self.timestamps = {}
        self.lock = threading.Lock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()

    def __setitem__(self, key, value):
        with self.lock:
            super().__setitem__(key, value)
            self.timestamps[key] = time.time()

    def __getitem__(self, key):
        with self.lock:
            # Optionally update timestamp on access to extend TTL, 
            # here we only set TTL on modification to clear abandoned flows
            return super().__getitem__(key)
            
    def get(self, key, default=None):
        with self.lock:
            return super().get(key, default)
            
    def pop(self, key, default=None):
        with self.lock:
            self.timestamps.pop(key, None)
            return super().pop(key, default)
            
    def __delitem__(self, key):
        with self.lock:
            self.timestamps.pop(key, None)
            super().__delitem__(key)

    def _cleanup_loop(self):
        while True:
            time.sleep(self.cleanup_interval)
            self._cleanup()

    def _cleanup(self):
        now = time.time()
        expired_keys = []
        with self.lock:
            for key, timestamp in self.timestamps.items():
                if now - timestamp > self.ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self.timestamps.pop(key, None)
                super().pop(key, None)

def get_active_program_id(user_id):
    """
    Get program ID for a user - checks session first, then fallback to created program.
    This allows users to access programs via Program ID (not just programs they created).
    """
    from ..handlers.start import user_sessions
    from ..database.queries import get_user_program_id
    from ..utils.db_operations import safe_db_operation
    
    # First check session for program_id
    session = user_sessions.get(user_id, {})
    if "program_id" in session:
        return session["program_id"]
    
    # Fallback to user's created program
    return safe_db_operation(get_user_program_id, None, user_id)
