from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
import hashlib
import jwt

from app.database import get_db, SECRET_KEY
from app import models, schemas, security

app = FastAPI(title="Payment API Test Task")

# --- ЗАВИСИМОСТИ АВТОРИЗАЦИИ ---

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security_scheme = HTTPBearer()

async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security_scheme), db: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[security.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    result = await db.execute(select(models.User).where(models.User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_admin(current_user: models.User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return current_user


# --- РОУТЫ: АВТОРИЗАЦИЯ ---

@app.post("/auth/login", response_model=schemas.Token)
async def login(user_data: schemas.UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).where(models.User.email == user_data.email))
    user = result.scalar_one_or_none()
    if not user or not security.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = security.create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


# --- РОУТЫ: ПОЛЬЗОВАТЕЛЬ ---

@app.get("/users/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@app.get("/users/me/accounts", response_model=List[schemas.AccountResponse])
async def read_own_accounts(current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Account).where(models.Account.user_id == current_user.id))
    return result.scalars().all()

@app.get("/users/me/payments", response_model=List[schemas.PaymentResponse])
async def read_own_payments(current_user: models.User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Получаем счета пользователя, чтобы потом найти платежи
    result = await db.execute(select(models.Account.id).where(models.Account.user_id == current_user.id))
    account_ids = result.scalars().all()
    
    if not account_ids:
        return []
        
    payments_result = await db.execute(select(models.Payment).where(models.Payment.account_id.in_(account_ids)))
    return payments_result.scalars().all()


# --- РОУТЫ: АДМИНИСТРАТОР ---

@app.get("/admin/me", response_model=schemas.UserResponse)
async def read_admin_me(current_user: models.User = Depends(get_current_admin)):
    return current_user

@app.post("/admin/users", response_model=schemas.UserResponse)
async def create_user(user: schemas.UserCreate, db: AsyncSession = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    db_user = models.User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=security.get_password_hash(user.password),
        is_admin=user.is_admin
    )
    db.add(db_user)
    try:
        await db.commit()
        await db.refresh(db_user)
        return db_user
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")

@app.get("/admin/users", response_model=List[dict])
async def list_users_with_accounts(db: AsyncSession = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    result = await db.execute(select(models.User).options(selectinload(models.User.accounts)))
    users = result.scalars().all()

    response = []
    for user in users:
        response.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "accounts": [{"id": acc.id, "balance": acc.balance} for acc in user.accounts]
        })
    return response

@app.delete("/admin/users/{user_id}", status_code=204)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()

@app.put("/admin/users/{user_id}", response_model=schemas.UserResponse)
async def update_user(user_id: int, user_update: schemas.UserUpdate, db: AsyncSession = Depends(get_db), admin: models.User = Depends(get_current_admin)):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_update.email: user.email = user_update.email
    if user_update.full_name: user.full_name = user_update.full_name
    if user_update.password: user.hashed_password = security.get_password_hash(user_update.password)
    
    await db.commit()
    await db.refresh(user)
    return user



@app.post("/webhook/payment")
async def process_payment_webhook(payload: schemas.WebhookPayload, db: AsyncSession = Depends(get_db)):

    amount_str = str(int(payload.amount)) if payload.amount % 1 == 0 else str(payload.amount)
    
    raw_string = f"{payload.account_id}{amount_str}{payload.transaction_id}{payload.user_id}{SECRET_KEY}"
    expected_signature = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()
    
    if payload.signature != expected_signature:
        raise HTTPException(status_code=400, detail="Invalid signature")

    existing_payment = await db.execute(select(models.Payment).where(models.Payment.transaction_id == payload.transaction_id))
    if existing_payment.scalar_one_or_none():
        return {"status": "already_processed"} 

    result = await db.execute(
        select(models.Account).where(models.Account.id == payload.account_id).with_for_update()
    )
    account = result.scalar_one_or_none()

    if not account:
        user_res = await db.execute(select(models.User).where(models.User.id == payload.user_id))
        if not user_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="User does not exist")
            
        account = models.Account(id=payload.account_id, user_id=payload.user_id, balance=0)
        db.add(account)
        await db.flush() 
    elif account.user_id != payload.user_id:
        raise HTTPException(status_code=400, detail="Account belongs to a different user")

    account.balance += payload.amount
    payment = models.Payment(
        transaction_id=payload.transaction_id,
        account_id=payload.account_id,
        amount=payload.amount
    )
    db.add(payment)
    await db.commit()

    return {"status": "success", "transaction_id": payload.transaction_id}