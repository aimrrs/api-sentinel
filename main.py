from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Depends, FastAPI, HTTPException, status, Header
from apscheduler.schedulers.background import BackgroundScheduler
from passlib.context import CryptContext
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .database import SessionLocal
from sqlalchemy.sql import func
from dotenv import load_dotenv
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional
from . import models
import requests
import secrets
import os

from fastapi.middleware.cors import CORSMiddleware

scheduler = BackgroundScheduler()

exchange_rate_cache = {
    "rate": 83.50,
    "last_fetched": None
}

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

app = FastAPI(
    title="API Sentinel Backend",
    description="The core API for the API Sentinel service.",
    version="0.3.0",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://192.168.0.130:3000", "http://127.0.0.1:3000"], # Allows your frontend to connect
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
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

class ProjectCreate(BaseModel):
    name: str

class ProjectResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    sentinel_key: str

    class Config:
        from_attributes = True

class ProjectStats(BaseModel):
    project_id: int
    project_name: str
    monthly_budget: int
    current_usage: float
    usage_start_date: datetime
    usage_end_date: datetime

class SentinelKeyDetails(BaseModel):
    project_id: int
    monthly_budget: int
    current_usage: float
    usd_to_inr_rate: float

class PricingOut(BaseModel):
    model_name: str
    input_cost_per_million_usd: float
    output_cost_per_million_usd: float

def fetch_and_cache_exchange_rate():
    global exchange_rate_cache
    print("[API - SENTINEl] Fetching latest USD->INR exchange rate...")
    
    api_key = os.getenv("EXCHANGERATE_API_KEY")
    if not api_key:
        print("[API - SENTINEl] Warning: EXCHANGERATE_API_KEY not found. Using default rate.")
        return

    try:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        inr_rate = data.get("conversion_rates", {}).get("INR")
        
        if inr_rate:
            exchange_rate_cache["rate"] = inr_rate
            exchange_rate_cache["last_fetched"] = datetime.utcnow()
            print(f"BACKEND: Exchange rate cache updated to {inr_rate}")
    except requests.RequestException as e:
        print(f"[API - SENTINEl] Warning: Could not fetch exchange rate. Using default. Error: {e}")

@app.on_event("startup")
def startup_event():
    fetch_and_cache_exchange_rate()
    scheduler.add_job(fetch_and_cache_exchange_rate, 'interval', hours=24)
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

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
    if not sentinel_key or not sentinel_key.is_active:
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

@app.get("/keys/verify", response_model=SentinelKeyDetails, tags=["SDK"])
def get_key_details(x_sentinel_key: str = Header(...), db: Session = Depends(get_db)):
    sentinel_key = db.query(models.SentinelKey).filter(models.SentinelKey.key_string == x_sentinel_key).first()
    if not sentinel_key or not sentinel_key.is_active:
        raise HTTPException(
            status_code = 401,
            detail = "Invalid or missing API key."
        )
    now = datetime.utcnow()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    usage_sum = db.query(func.sum(models.UsageLog.cost_rupees)).filter(
        models.UsageLog.sentinel_key_id == sentinel_key.id,
        models.UsageLog.timestamp >= start_of_month,
    ).scalar()
    return {
        "project_id": sentinel_key.project_id,
        "monthly_budget": sentinel_key.monthly_budget_rupees,
        "current_usage": usage_sum or 0.0,
        "usd_to_inr_rate": exchange_rate_cache["rate"]
    }

@app.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, tags=["Projects"])
def create_project(project: ProjectCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_project = models.Project(name=project.name, owner_id=current_user.id)
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    key_string = f"api-sentinel_pk_{secrets.token_urlsafe(16)}"
    new_key = models.SentinelKey(key_string=key_string, project_id=new_project.id)
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return {
        "id": new_project.id,
        "name": new_project.name,
        "owner_id": new_project.owner_id,
        "sentinel_key": new_key.key_string
    }

@app.delete("/projects/{project_id}", status_code=status.HTTP_200_OK, tags=["Projects"])
def delete_project(project_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    project_to_delete = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == current_user.id
    ).first()

    if not project_to_delete:
        raise HTTPException(
            status_code = 404,
            detail = "Project not found."
        )
    
    db.delete(project_to_delete)
    db.commit()
    return {"message": f"Project '{project_to_delete.name}' and all its data have been successfully deleted."}

@app.get("/projects", response_model=list[ProjectResponse], tags=["Projects"])
def read_user_projects(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(models.Project).filter(models.Project.owner_id == current_user.id).all()
    response_list = []
    for project in projects:
        response_list.append({
            "id": project.id,
            "name": project.name,
            "owner_id": project.owner_id,
            "sentinel_key": project.sentinel_key.key_string if project.sentinel_key else "N/A"
        })
    return response_list

@app.delete("/users/me", status_code=status.HTTP_200_OK, tags=["Users"])
def delete_current_user(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.delete(current_user)
    db.commit()
    return {"message": "Your account and all associated data have been successfully deleted."}

@app.get("/v1/projects/{project_id}/stats", response_model=ProjectStats, tags=["Dashboard"])
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

@app.get("/v1/public/pricing/{api_name}", response_model=list[PricingOut], tags=["Public"])
def get_api_pricing(api_name: str, db: Session = Depends(get_db)):
    pricing_data = db.query(models.ApiPricing).filter(models.ApiPricing.api_name == api_name).all()
    if not pricing_data:
        raise HTTPException(status_code=404, detail="Pricing information not found for this API.")
    return pricing_data
