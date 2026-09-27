from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Role, User

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)

def hash_password(value: str) -> str: return password_hash.hash(value)
def verify_password(value: str, hashed: str) -> bool: return password_hash.verify(value, hashed)
def create_token(user: User) -> str:
    settings = get_settings(); exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": user.id, "role": user.role.value, "exp": exp}, settings.jwt_secret, algorithm="HS256")
def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try: payload = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, payload.get("sub"))
    if not user or not user.active: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inactive user")
    return user
def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != Role.ADMIN: raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user

