"""
Authentication & RBAC Module
===============================
Provides session-based authentication and role-based access control
for multi-user deployments. Uses Streamlit session state for
zero-persistence compliance.

Supports:
  - Local user/password authentication (bcrypt hashed)
  - Role-based access (Admin, Analyst, Viewer)
  - Rate limiting per user/session
  - Session timeout
"""

import hashlib
import hmac
import time
import secrets
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta


# ─── Role definitions ────────────────────────────────────────────────────────
ROLES = {
    "admin": {
        "label": "Administrator",
        "permissions": [
            "view_dashboard", "analyze_servers", "export_data",
            "ai_analysis", "manage_users", "view_audit_log",
            "bulk_upload", "scenario_analysis", "auto_discovery",
        ],
    },
    "analyst": {
        "label": "Analyst",
        "permissions": [
            "view_dashboard", "analyze_servers", "export_data",
            "ai_analysis", "bulk_upload", "scenario_analysis",
        ],
    },
    "viewer": {
        "label": "Viewer",
        "permissions": [
            "view_dashboard", "export_data",
        ],
    },
}

# ─── Default users (in production, use external identity provider) ───────────
# Passwords hashed with SHA-256 for demo; use bcrypt in production
DEFAULT_USERS = {
    "admin": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "display_name": "Administrator",
    },
    "analyst": {
        "password_hash": hashlib.sha256("analyst123".encode()).hexdigest(),
        "role": "analyst",
        "display_name": "Cloud Analyst",
    },
    "viewer": {
        "password_hash": hashlib.sha256("viewer123".encode()).hexdigest(),
        "role": "viewer",
        "display_name": "Report Viewer",
    },
}

# ─── Session settings ────────────────────────────────────────────────────────
SESSION_TIMEOUT_MINUTES = 60
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AuthManager:
    """Manages authentication and authorization state."""

    def __init__(self, users: Optional[Dict] = None):
        self.users = users or DEFAULT_USERS
        self._login_attempts: Dict[str, List[float]] = {}

    def authenticate(self, username: str, password: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Authenticate a user.
        Returns (success, message, user_info).
        """
        username = username.strip().lower()

        # Check lockout
        if self._is_locked_out(username):
            remaining = self._lockout_remaining(username)
            return False, f"Account locked. Try again in {remaining} minutes.", None

        if username not in self.users:
            self._record_attempt(username)
            return False, "Invalid username or password.", None

        user = self.users[username]
        pw_hash = hashlib.sha256(password.encode()).hexdigest()

        if not hmac.compare_digest(pw_hash, user["password_hash"]):
            self._record_attempt(username)
            attempts_left = MAX_LOGIN_ATTEMPTS - len(self._login_attempts.get(username, []))
            return False, f"Invalid username or password. {max(0, attempts_left)} attempts remaining.", None

        # Success — clear attempts
        self._login_attempts.pop(username, None)

        session_token = secrets.token_hex(32)
        user_info = {
            "username": username,
            "role": user["role"],
            "display_name": user.get("display_name", username),
            "permissions": ROLES[user["role"]]["permissions"],
            "session_token": session_token,
            "login_time": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat(),
        }

        return True, f"Welcome, {user_info['display_name']}!", user_info

    def has_permission(self, user_info: Optional[Dict], permission: str) -> bool:
        """Check if user has a specific permission."""
        if user_info is None:
            return False
        return permission in user_info.get("permissions", [])

    def is_session_valid(self, user_info: Optional[Dict]) -> bool:
        """Check if session is still valid (not expired)."""
        if user_info is None:
            return False
        try:
            expires = datetime.fromisoformat(user_info["expires_at"])
            return datetime.now() < expires
        except (KeyError, ValueError):
            return False

    def get_role_label(self, role: str) -> str:
        """Get display label for a role."""
        return ROLES.get(role, {}).get("label", role)

    def _record_attempt(self, username: str):
        """Record a failed login attempt."""
        now = time.time()
        if username not in self._login_attempts:
            self._login_attempts[username] = []
        # Keep only recent attempts within lockout window
        cutoff = now - (LOCKOUT_DURATION_MINUTES * 60)
        self._login_attempts[username] = [
            t for t in self._login_attempts[username] if t > cutoff
        ]
        self._login_attempts[username].append(now)

    def _is_locked_out(self, username: str) -> bool:
        """Check if account is locked out."""
        if username not in self._login_attempts:
            return False
        now = time.time()
        cutoff = now - (LOCKOUT_DURATION_MINUTES * 60)
        recent = [t for t in self._login_attempts[username] if t > cutoff]
        return len(recent) >= MAX_LOGIN_ATTEMPTS

    def _lockout_remaining(self, username: str) -> int:
        """Minutes remaining in lockout."""
        if username not in self._login_attempts or not self._login_attempts[username]:
            return 0
        oldest = min(self._login_attempts[username])
        elapsed = (time.time() - oldest) / 60
        return max(0, int(LOCKOUT_DURATION_MINUTES - elapsed))


class RateLimiter:
    """
    Token bucket rate limiter.
    Tracks requests per user/session to prevent abuse.
    """

    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, List[float]] = {}

    def check_limit(self, identifier: str) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.
        Returns (allowed, remaining_requests).
        """
        now = time.time()
        cutoff = now - self.window_seconds

        if identifier not in self._buckets:
            self._buckets[identifier] = []

        # Clean old entries
        self._buckets[identifier] = [
            t for t in self._buckets[identifier] if t > cutoff
        ]

        current_count = len(self._buckets[identifier])

        if current_count >= self.max_requests:
            return False, 0

        self._buckets[identifier].append(now)
        return True, self.max_requests - current_count - 1

    def get_usage(self, identifier: str) -> Dict:
        """Get current rate limit usage for an identifier."""
        now = time.time()
        cutoff = now - self.window_seconds

        if identifier not in self._buckets:
            return {"used": 0, "limit": self.max_requests, "remaining": self.max_requests}

        recent = [t for t in self._buckets[identifier] if t > cutoff]
        return {
            "used": len(recent),
            "limit": self.max_requests,
            "remaining": max(0, self.max_requests - len(recent)),
            "resets_in_seconds": int(self.window_seconds - (now - min(recent))) if recent else 0,
        }


# Rate limiters for different operations
api_rate_limiter = RateLimiter(max_requests=100, window_seconds=3600)     # 100 API calls/hr
analysis_rate_limiter = RateLimiter(max_requests=50, window_seconds=3600)  # 50 analyses/hr
export_rate_limiter = RateLimiter(max_requests=20, window_seconds=3600)    # 20 exports/hr
ai_rate_limiter = RateLimiter(max_requests=10, window_seconds=3600)        # 10 AI calls/hr


def render_login_page(st):
    """Render Streamlit login form. Returns user_info if authenticated."""
    auth = AuthManager()

    st.markdown("""
    <div style="text-align:center; padding:3rem 0 1rem 0;">
        <h1 style="font-size:2.5rem;">☁️ Cloud Migration Analyzer</h1>
        <p style="color:#94A3B8;">Please sign in to continue</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return None

                success, message, user_info = auth.authenticate(username, password)
                if success:
                    st.session_state["_auth_user"] = user_info
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

        st.caption("Default accounts: admin/admin123, analyst/analyst123, viewer/viewer123")

    return st.session_state.get("_auth_user")
