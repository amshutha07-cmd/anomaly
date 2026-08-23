import os
from typing import Any

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient


def validate_access_token(token: str) -> dict[str, Any]:
    """Validate a Supabase access token using the server-only JWT secret or JWKS."""
    supabase_url = (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "").rstrip("/")
    if not supabase_url:
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured")

    issuer = f"{supabase_url}/auth/v1"
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

    try:
        if jwt_secret:
            claims = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                issuer=issuer,
            )
        else:
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
            signing_key = PyJWKClient(jwks_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "ES256"],
                audience="authenticated",
                issuer=issuer,
            )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Auth verification service unavailable") from exc

    return claims
