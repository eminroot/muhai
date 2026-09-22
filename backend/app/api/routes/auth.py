"""Accounts and sessions.

This is the only authentication in Muhai. It replaced Firebase Auth: a
bcrypt-hashed password in Postgres, a signed JWT back to the browser, and the
same secret verifying it on every later request. Nothing leaves the VPS.

Registration creates the account and its company in one transaction. A
half-registered account — one that can sign in but has nothing to sign in to —
was a real failure mode under the old two-system setup and is now impossible.

``/google`` is the one exception, and not a return to Firebase Auth: it takes
an ID token, verifies it against Google's published certificates, and issues
Muhai's own JWT. Firebase authenticates a person and is then out of the path.
"""
import secrets

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.company import Company
from app.db.models.user import User
from app.schemas.user import (
    CompanyInput,
    GoogleAuth,
    PasswordChange,
    Session,
    Token,
    UserLogin,
    UserOut,
    UserRegister,
)
from app.services.google_identity import GoogleIdentityError, verify_id_token_async
from app.services.workspace import company_document

router = APIRouter(prefix="/auth", tags=["auth"])


async def _session(db: DbSession, user: User) -> tuple[UserOut, dict | None]:
    company = await db.get(Company, user.company_id) if user.company_id else None
    return UserOut.model_validate(user), (
        company_document(company) if company is not None else None
    )


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: DbSession) -> Token:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta adresi zaten kayıtlı.",
        )

    profile = payload.company
    company = Company(
        name=profile.name if profile else payload.business_name,
        tax_id=profile.taxId if profile else "",
        tax_office=profile.taxOffice if profile else "",
        sector=profile.sector if profile else "general",
        city=profile.city if profile else "",
        legal_form=profile.legalForm if profile else "ltd",
        email=payload.email,
    )
    db.add(company)
    await db.flush()

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        business_name=payload.business_name,
        display_name=payload.display_name,
        role="owner",
        company_id=company.id,
    )
    db.add(user)
    await db.flush()

    company.owner_user_id = user.id
    db.add(company)
    await db.flush()
    await db.refresh(user)

    user_out, company_out = await _session(db, user)
    return Token(
        access_token=create_access_token(user.id),
        user=user_out,
        company=company_out,
    )


@router.post("/login", response_model=Token)
async def login(payload: UserLogin, db: DbSession) -> Token:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-posta veya şifre hatalı.",
        )

    user_out, company_out = await _session(db, user)
    return Token(
        access_token=create_access_token(user.id),
        user=user_out,
        company=company_out,
    )


@router.post("/google", response_model=Token)
async def google(payload: GoogleAuth, db: DbSession) -> Token:
    """Exchange a Firebase ID token for a Muhai session.

    Google proves who the person is; Muhai still decides what they may see.
    The token it hands back is the same one a password login issues, so every
    later request is authenticated identically and Firebase never becomes the
    session.

    Accounts match on lowercased email, so signing in with Google and signing
    in with a password land in the same account rather than forking it. A
    Google profile carries no tax id or legal form, so an account created here
    arrives with **no company** — ``ProtectedRoute`` routes it to the setup
    screen, the path a company-less session already had.
    """
    if not settings.FIREBASE_PROJECT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google ile giriş bu sunucuda yapılandırılmamış.",
        )

    try:
        claims = await verify_id_token_async(
            payload.id_token, settings.FIREBASE_PROJECT_ID
        )
    except GoogleIdentityError as exc:
        # The message is already the one to show: google_identity raises in
        # Turkish and says which check the token failed.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc

    email = claims["email"]
    user = await db.scalar(select(User).where(User.email == email))

    if user is None:
        display_name = (claims.get("name") or "").strip()
        user = User(
            email=email,
            # No password was set and none can be guessed into: bcrypt over a
            # value nothing will ever submit. The account reaches a password
            # by way of the reset flow, not by having a blank one.
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            business_name=display_name or email,
            display_name=display_name,
            role="owner",
            # Deliberately no company — see the docstring.
            company_id=None,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
    elif not user.display_name and claims.get("name"):
        user.display_name = str(claims["name"]).strip()
        db.add(user)
        await db.flush()

    user_out, company_out = await _session(db, user)
    return Token(
        access_token=create_access_token(user.id),
        user=user_out,
        company=company_out,
    )


@router.get("/me", response_model=Session)
async def me(current_user: CurrentUser, db: DbSession) -> Session:
    """Restore a session from a stored token — the app's first call on load."""
    user_out, company_out = await _session(db, current_user)
    return Session(user=user_out, company=company_out)


@router.post("/company", response_model=Session, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyInput,
    current_user: CurrentUser,
    db: DbSession,
) -> Session:
    """Attach a company to an account that has none.

    Reachable only from the frontend's recovery screen. Registration normally
    does this, so an account arriving here means an earlier attempt was
    interrupted between the two writes.
    """
    if current_user.company_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu hesabın zaten bir işletmesi var.",
        )

    company = Company(
        name=payload.name,
        tax_id=payload.taxId,
        tax_office=payload.taxOffice,
        sector=payload.sector,
        city=payload.city,
        legal_form=payload.legalForm,
        email=current_user.email,
        owner_user_id=current_user.id,
    )
    db.add(company)
    await db.flush()

    current_user.company_id = company.id
    db.add(current_user)
    await db.flush()

    user_out, company_out = await _session(db, current_user)
    return Session(user=user_out, company=company_out)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    current_user: CurrentUser,
    db: DbSession,
) -> Response:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mevcut şifre hatalı.",
        )
    if verify_password(payload.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yeni şifre mevcut şifreden farklı olmalıdır.",
        )

    current_user.hashed_password = hash_password(payload.new_password)
    db.add(current_user)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(current_user: CurrentUser, db: DbSession) -> Response:
    """Permanently delete the account and everything its company owns."""
    company = (
        await db.get(Company, current_user.company_id)
        if current_user.company_id
        else None
    )
    await db.delete(current_user)
    if company is not None:
        # Cascades through the five workspace collections.
        await db.delete(company)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
