from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext

DATABASE_URL = "postgresql+psycopg2://postgres:yvtBoBbueGkabrUvJhufVqhVRDVbkptW@switchyard.proxy.rlwy.net:28129/railway"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

class RegisterRequest(BaseModel):
    username: str
    password: str
    repeat_password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    message: str

app = FastAPI(title="Auth API", version="1.0.0")

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
        return AuthResponse(message="Регистрация успешна")
    finally:
        db.close()

@app.post("/auth/login", response_model=AuthResponse)
def login(data: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == data.username).first()
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверные данные")
        return AuthResponse(message="Авторизация успешна")
    finally:
        db.close()
