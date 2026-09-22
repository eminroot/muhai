from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.models.company import Company
from app.db.models.user import User
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya süresi dolmuş oturum.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_error

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_company(db: DbSession, user: CurrentUser) -> Company:
    """The workspace the caller signs in to.

    Every workspace route scopes its query by this company's id, which is the
    whole authorisation model: an account can only ever reach rows beneath the
    one company it belongs to.

    A 409 (rather than 404) marks the recoverable state where an account exists
    but its company row does not — the frontend answers that with its
    company-setup screen instead of signing the user out.
    """
    if user.company_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu hesaba bağlı bir işletme yok.",
        )
    company = await db.get(Company, user.company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu hesaba bağlı bir işletme yok.",
        )
    return company


CurrentCompany = Annotated[Company, Depends(get_current_company)]


async def get_compute_caller(request: Request, db: DbSession) -> User | None:
    """Resolve the caller of a ``/api/compute`` endpoint.

    Compute is stateless — it reads no table and returns a pure function of the
    posted snapshot — so it authenticates without needing a company. It is
    still gated by default: an open maths endpoint is a free CPU for anyone who
    finds it.

    ``COMPUTE_AUTH_REQUIRED=false`` opens it for an offline demo, where the
    caller is None. Never do that on a deployment anyone else can reach.
    """
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    token = token.strip()

    unauthorised = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Oturum tokenı gerekli.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if scheme.lower() != "bearer" or not token:
        if not settings.COMPUTE_AUTH_REQUIRED:
            return None
        raise unauthorised

    user_id = decode_access_token(token)
    user = await db.get(User, user_id) if user_id else None
    if user is None:
        if not settings.COMPUTE_AUTH_REQUIRED:
            return None
        raise unauthorised
    return user


ComputeCaller = Annotated[User | None, Depends(get_compute_caller)]
