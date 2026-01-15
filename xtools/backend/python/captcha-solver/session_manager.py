import json
import os
import time

class SessionManager:
    def __init__(self, session_file: str = "admin_sessions.json"):
        self.session_file = session_file
        self.sessions = self._load_sessions()

    def _load_sessions(self) -> dict:
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    current_time = time.time()
                    valid_sessions = {
                        session_id: expires
                        for session_id, expires in data.items()
                        if expires > current_time
                    }
                    if len(valid_sessions) != len(data):
                        self._save_sessions(valid_sessions)
                    return valid_sessions
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_sessions(self, sessions: dict = None):
        if sessions is None:
            sessions = self.sessions
        try:
            with open(self.session_file, 'w') as f:
                json.dump(sessions, f)
        except IOError:
            pass

    def add_session(self, session_id: str, expires_in: int = 86400):
        expires_at = time.time() + expires_in
        self.sessions[session_id] = expires_at
        self._save_sessions()

    def is_valid_session(self, session_id: str) -> bool:
        if session_id not in self.sessions:
            return False
        if self.sessions[session_id] <= time.time():
            del self.sessions[session_id]
            self._save_sessions()
            return False
        return True

    def remove_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_sessions()
    def get_all_sessions(self) -> dict:
        """Get all valid sessions."""
        current_time = time.time()
        valid_sessions = {
            session_id: expires
            for session_id, expires in self.sessions.items()
            if expires > current_time
        }
        if len(valid_sessions) != len(self.sessions):
            self.sessions = valid_sessions
            self._save_sessions()
        return valid_sessions

    def create_session(self, username: str, expires_in: int = 86400) -> str:
        """Create a new session and return session ID."""
        import secrets
        session_id = secrets.token_urlsafe(32)
        self.add_session(session_id, expires_in)
        return session_id

session_manager = SessionManager()

