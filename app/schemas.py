from pydantic import BaseModel, EmailStr
from typing import List, Optional
from decimal import Decimal

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserCreate(UserLogin):
    full_name: str
    is_admin: bool = False

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_admin: bool

    class Config:
        from_attributes = True

class AccountResponse(BaseModel):
    id: int
    user_id: int
    balance: Decimal

    class Config:
        from_attributes = True

class PaymentResponse(BaseModel):
    transaction_id: str
    account_id: int
    amount: Decimal

    class Config:
        from_attributes = True

class WebhookPayload(BaseModel):
    transaction_id: str
    user_id: int
    account_id: int
    amount: Decimal
    signature: str

class Token(BaseModel):
    access_token: str
    token_type: str