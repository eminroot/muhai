from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyInput(BaseModel):
    """The company profile collected on the second step of sign-up."""

    name: str = Field(min_length=1, max_length=200)
    taxId: str = ""
    taxOffice: str = ""
    sector: str = "general"
    city: str = ""
    legalForm: str = "ltd"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    # The company's trading name. Kept for the legacy column of the same name;
    # `company.name` is the one the workspace actually uses.
    business_name: str = Field(min_length=1, max_length=200)
    display_name: str = ""
    company: CompanyInput | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuth(BaseModel):
    """The Firebase ID token the browser got from "sign in with Google"."""

    id_token: str = Field(min_length=1)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    business_name: str
    display_name: str = ""
    role: str = "owner"
    company_id: str | None = None
    created_at: datetime


class Session(BaseModel):
    """Everything the client needs to render a signed-in shell.

    The company travels with the user because the app is useless without it —
    fetching them separately only invents a state where one has arrived and the
    other has not.
    """

    user: UserOut
    company: dict[str, Any] | None = None


class Token(Session):
    access_token: str
    token_type: str = "bearer"
