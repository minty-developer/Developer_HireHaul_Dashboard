"""비밀번호 해시.

기존 Flask(werkzeug) 버전에서 저장한 해시(`scrypt:n:r:p$salt$hex`,
`pbkdf2:sha256:iter$salt$hex`)를 그대로 검증할 수 있도록 같은 형식을 사용한다.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import string

SALT_CHARS = string.ascii_letters + string.digits
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1


def _scrypt(password: str, salt: str, n: int, r: int, p: int) -> str:
    return hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=n, r=r, p=p, maxmem=132 * n * r * p
    ).hex()


def hash_password(password: str) -> str:
    salt = "".join(secrets.choice(SALT_CHARS) for _ in range(16))
    digest = _scrypt(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return f"scrypt:{SCRYPT_N}:{SCRYPT_R}:{SCRYPT_P}${salt}${digest}"


def verify_password(stored: str, password: str) -> bool:
    try:
        method, salt, expected = stored.split("$", 2)
        name, *args = method.split(":")
        if name == "scrypt":
            n, r, p = (map(int, args) if args else (SCRYPT_N, SCRYPT_R, SCRYPT_P))
            actual = _scrypt(password, salt, n, r, p)
        elif name == "pbkdf2":
            hash_name = args[0] if args else "sha256"
            iterations = int(args[1]) if len(args) > 1 else 1_000_000
            actual = hashlib.pbkdf2_hmac(
                hash_name, password.encode(), salt.encode(), iterations
            ).hex()
        else:
            return False
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)
