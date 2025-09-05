import os
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from . import models
from .database import SessionLocal, engine

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Security contexts and schemes
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

app = FastAPI(
    title="API Sentinel Backend",
    description="The core API for the API Sentinel service.",
    version="0.3.0",
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class UserCreate(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UsageCreate(BaseModel):
    cost: float
    usage_metadata: dict

class ProjectStats(BaseModel):
    project_id: int
    project_name: str
    monthly_budget: int
    current_usage: float
    usage_start_date: datetime
    usage_end_date: datetime

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encode_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encode_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code = status.HTTP_401_UNAUTHORIZED,
        detail = "Could not validate credentials.",
        headers = {"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

@app.post("/auth/signup", status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code = 409,
            detail = "An account with this email already exists.",
        )
    hashed_password = get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

@app.post("/auth/token", response_model=Token, tags=["Authentication"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Incorrect email or passowrd",
        )
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/v1/usage", status_code=status.HTTP_202_ACCEPTED, tags=["SDK"])
def report_usage(usage: UsageCreate, x_sentinel_key: str = Header(...), db: Session = Depends(get_db)):
    sentinel_key = db.query(models.SentinelKey).filter(models.SentinelKey.key_string == x_sentinel_key).first()
    if not sentinel_key or not sentinel_key.is_active():
        raise HTTPException(
            status_code = 401,
            details = "Invalid or missing API key.",
        )
    new_log = models.UsageLog(
        sentinel_key_id = sentinel_key.id, 
        cost_rupees = usage.cost, 
        usage_metadata = usage.usage_metadata
    )
    db.add(new_log)
    db.commit()
    return

@app.get("/v1/projects/{projects_id}/stats", response_model=ProjectStats, tags=["Dashboard"])
def get_project_stats(project_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id, models.Project.owner_id == current_user.id).first()
    if not project:
        raise HTTPException(
            status_code = 404,
            detail = "Project not found."
        )
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    usage_sum = db.query(func.sum(models.UsageLog.cost_rupees)).filter(
        models.UsageLog.sentinel_key_id == project.sentinel_key.id,
        models.UsageLog.timestamp >= start_of_month).scalar()
    
    return {
        "project_id": project.id,
        "project_name": project.name,
        "monthly_budget": project.sentinel_key.monthly_budget_rupees,
        "current_usage": usage_sum or 0.0,
        "usage_start_date": start_of_month,
        "usage_end_date": (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(seconds=1),
    }
