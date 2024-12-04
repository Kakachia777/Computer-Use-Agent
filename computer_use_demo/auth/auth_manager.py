from typing import Dict, Optional
import hashlib
import time
import secrets

class AuthManager:
    def __init__(self):
        self.secret_key = secrets.token_hex(16)
        # Default test user
        self._users = {
            "test": self._hash_password("test123")
        }
        self._sessions: Dict[str, float] = {}
        
    def login(self, username: str, password: str) -> Optional[str]:
        if username in self._users and self._users[username] == self._hash_password(password):
            token = secrets.token_hex(16)
            self._sessions[token] = time.time() + 3600  # 1 hour
            return token
        return None
        
    def verify_token(self, token: str) -> bool:
        return token in self._sessions and self._sessions[token] > time.time()
        
    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(f"{password}{self.secret_key}".encode()).hexdigest() 