import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    s = data.encode("ascii")
    s += b"=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def _jwt_secret() -> str:
    # 线上必须显式设置，否则每次重启 token 都会失效。
    return os.getenv("JWT_SECRET") or "dev-insecure-jwt-secret"


def issue_jwt(payload: Dict[str, Any], *, expires_in_seconds: int = 7 * 24 * 3600) -> str:
    header = {"alg": "HS256", "typ": "JWT"}

    now = int(time.time())
    full_payload = dict(payload)
    full_payload.setdefault("iat", now)
    full_payload.setdefault("exp", now + int(expires_in_seconds))

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(full_payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    sig = hmac.new(_jwt_secret().encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_jwt(token: str) -> Optional[Dict[str, Any]]:
    if not token or token.count(".") != 2:
        return None

    try:
        header_b64, payload_b64, sig_b64 = token.split(".", 2)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected_sig = hmac.new(
            _jwt_secret().encode("utf-8"), signing_input, hashlib.sha256
        ).digest()

        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        if not isinstance(payload, dict):
            return None

        exp = payload.get("exp")
        if exp is not None:
            if int(time.time()) > int(exp):
                return None

        return payload
    except Exception:
        return None


def is_admin_jwt(token: str) -> bool:
    payload = decode_jwt(token)
    if not payload:
        return False
    return str(payload.get("role", "")).lower() == "admin"
