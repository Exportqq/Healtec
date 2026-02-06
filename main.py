from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext
import jwt
import datetime

DATABASE_URL = "postgresql+psycopg2://postgres:password@localhost:5432/dbname"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "YOUR_SECRET_KEY"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

class RegisterRequest(BaseModel):
    username: str
    password: str
    repeat_password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    access_token: str

app = FastAPI(title="Auth API", version="1.0.0")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.post("/auth/register", response_model=AuthResponse)
def register(data: RegisterRequest):
    if data.password != data.repeat_password:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")
    db = SessionLocal()
    try:
        if db.query(UserDB).filter(UserDB.username == data.username).first():
            raise HTTPException(status_code=400, detail="Пользователь уже существует")
        user = UserDB(username=data.username, password_hash=hash_password(data.password))
        db.add(user)
        db.commit()
        token = create_token(data.username)
        return {"access_token": token}
    finally:
        db.close()

@app.post("/auth/login", response_model=AuthResponse)
def login(data: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == data.username).first()
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверные данные")
        token = create_token(data.username)
        return {"access_token": token}
    finally:
        db.close()
