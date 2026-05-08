"""使用者認證模組：註冊、登入驗證、Session 助手、login_required 裝飾器。"""

import re
from functools import wraps
from typing import Dict, Optional, Tuple

from flask import g, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import database


USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
MIN_PASSWORD_LEN = 6


def register_user(username: str, password: str, display_name: Optional[str] = None) -> Tuple[bool, str]:
    """註冊新使用者，回傳 (是否成功, 訊息或 user_id 字串)。"""
    username = (username or "").strip()
    display_name = (display_name or "").strip() or None

    if not USERNAME_RE.match(username):
        return False, "帳號需為 3–30 字元，限英數字或底線"
    if not password or len(password) < MIN_PASSWORD_LEN:
        return False, f"密碼長度至少 {MIN_PASSWORD_LEN} 個字元"

    if database.get_user_by_username(username):
        return False, "此帳號已被使用"

    password_hash = generate_password_hash(password)
    user_id = database.create_user(username, password_hash, display_name)
    return True, str(user_id)


def authenticate(username: str, password: str) -> Optional[Dict]:
    """驗證帳密，成功回傳 user dict，失敗回傳 None。"""
    user = database.get_user_by_username((username or "").strip())
    if not user:
        return None
    if not check_password_hash(user["password_hash"], password or ""):
        return None
    database.update_last_login(user["id"])
    return user


def login_session(user: Dict) -> None:
    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["display_name"] = user.get("display_name") or user["username"]


def logout_session() -> None:
    session.clear()


def current_user() -> Optional[Dict]:
    """從 session 還原使用者；同一 request 內快取在 g。"""
    if "user" in g.__dict__:
        return g.user
    user_id = session.get("user_id")
    if not user_id:
        g.user = None
        return None
    g.user = database.get_user_by_id(user_id)
    if g.user is None:
        # session 殘留已被刪除的帳號 → 清乾淨
        session.clear()
    return g.user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login", next=_safe_next()))
        return view(*args, **kwargs)
    return wrapper


def _safe_next() -> str:
    from flask import request
    return request.path
