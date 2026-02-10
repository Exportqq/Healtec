from fastapi import FastAPI, HTTPException, Header, Form, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from uuid import uuid4
import traceback
import base64


DATABASE_URL = "postgresql+psycopg2://postgres:yvtBoBbueGkabrUvJhufVqhVRDVbkptW@switchyard.proxy.rlwy.net:28129/railway"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Medical & Clothing API", version="1.0.0")

# Глобальный CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Мидлвара для логирования всех ошибок
@app.middleware("http")
async def log_all_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        print("❌ ОШИБКА СЕРВЕРА:")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# --- МОДЕЛИ БАЗЫ ДАННЫХ ---
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

class TokenDB(Base):
    __tablename__ = "tokens"
    token = Column(String, primary_key=True)
    username = Column(String, nullable=False)

class ClothingItemDB(Base):
    __tablename__ = "clothes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    rating = Column(String, nullable=False)
    photo = Column(Text, nullable=False)

class DoctorDB(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    specialty = Column(String, nullable=False)
    rating = Column(Float, nullable=False)
    photo = Column(Text, nullable=False)
    experience = Column(String, nullable=False)
    patients_count = Column(String, nullable=False)
    reviews_count = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    diseases = Column(Text, nullable=False)

class AppointmentDB(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"))

# --- PYDANTIC МОДЕЛИ ---
class RegisterRequest(BaseModel):
    username: str
    password: str
    repeat_password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    token: str
    username: str

class UserInfo(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

class ClothingItem(BaseModel):
    id: int | None = None
    name: str
    price: int
    type: str
    rating: str
    photo: str

    class Config:
        from_attributes = True

class Doctor(BaseModel):
    id: int | None = None
    name: str
    specialty: str
    rating: float
    photo: str
    experience: str
    patients_count: str
    reviews_count: str
    description: str
    diseases: list[str]

    class Config:
        from_attributes = True

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def get_current_user(authorization: str = Header(...)) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Неверный заголовок Authorization")
    token = authorization.split(" ")[1]
    db = SessionLocal()
    try:
        token_db = db.query(TokenDB).filter(TokenDB.token == token).first()
        if not token_db:
            raise HTTPException(status_code=401, detail="Неверный токен")
        return token_db.username
    finally:
        db.close()

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

# --- ЭНДПОИНТЫ АВТОРИЗАЦИИ ---
@app.post("/auth/register", response_model=AuthResponse)
def register(data: RegisterRequest):
    if data.password != data.repeat_password:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")
    db = SessionLocal()
    try:
        user = UserDB(username=data.username, password_hash=hash_password(data.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        
        token = str(uuid4())
        db.add(TokenDB(token=token, username=user.username))
        db.commit()
        
        return {"token": token, "username": user.username}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username уже существует")
    finally:
        db.close()

@app.post("/auth/login", response_model=AuthResponse)
def login(data: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == data.username).first()
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверные данные")
        
        token = str(uuid4())
        db.add(TokenDB(token=token, username=user.username))
        db.commit()
        
        return {"token": token, "username": user.username}
    finally:
        db.close()

@app.get("/me", response_model=UserInfo)
def me(username: str = Depends(get_current_user)):
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == username).first()
        return user
    finally:
        db.close()

# --- ЭНДПОИНТЫ ОДЕЖДЫ ---
@app.get("/clothes", response_model=list[ClothingItem])
def get_clothes():
    db = SessionLocal()
    try:
        return db.query(ClothingItemDB).all()
    finally:
        db.close()

@app.post("/clothes", response_model=ClothingItem)
def create_clothing_item(item: ClothingItem, username: str = Depends(get_current_user)):
    db = SessionLocal()
    try:
        db_item = ClothingItemDB(**item.model_dump(exclude={"id"}))
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    finally:
        db.close()

# --- ЭНДПОИНТЫ ДОКТОРОВ ---
@app.get("/doctors", response_model=list[Doctor])
def get_doctors():
    db = SessionLocal()
    try:
        doctors = db.query(DoctorDB).all()
        result = []
        for d in doctors:
            result.append(Doctor(
                id = d.id,
                name = d.name,
                specialty = d.specialty,
                rating = d.rating,
                photo = d.photo,
                experience = d.experience,
                patients_count = d.patients_count,
                reviews_count = d.reviews_count,
                description = d.description,
                diseases = d.diseases.split(",")
            ))
        return result
    finally:
        db.close()

@app.post("/doctors", response_model=Doctor)
def create_doctor(
    name: str = Form(...),
    specialty: str = Form(...),
    rating: float = Form(...),
    photo: UploadFile = File(...),
    experience: str = Form(...),
    patients_count: str = Form(...),
    reviews_count: str = Form(...),
    description: str = Form(...),
    diseases: str = Form(...),
    username: str = Depends(get_current_user)
):
    db = SessionLocal()
    try:
        # Конвертируем фото в base64
        photo_content = photo.file.read()
        photo_base64 = f"data:{photo.content_type};base64,{base64.b64encode(photo_content).decode()}"

        db_doctor = DoctorDB(
            name=name,
            specialty=specialty,
            rating=rating,
            photo=photo_base64,
            experience=experience,
            patients_count=patients_count,
            reviews_count=reviews_count,
            description=description,
            diseases=diseases
        )
        db.add(db_doctor)
        db.commit()
        db.refresh(db_doctor)

        return Doctor(
            id = db_doctor.id,
            name=db_doctor.name,
            specialty=db_doctor.specialty,
            rating=db_doctor.rating,
            photo=db_doctor.photo,
            experience=db_doctor.experience,
            patients_count=db_doctor.patients_count,
            reviews_count=db_doctor.reviews_count,
            description=db_doctor.description,
            diseases=diseases.split(",")
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# --- ЭНДПОИНТ ЗАПИСИ К ВРАЧУ ---
@app.post("/appointments/{doctor_id}")
def create_appointment(doctor_id: int, username: str = Depends(get_current_user)):
    db = SessionLocal()
    try:
        appointment = AppointmentDB(username=username, doctor_id=doctor_id)
        db.add(appointment)
        db.commit()
        return {"status": "ok", "message": "Запись создана"}
    finally:
        db.close()

@app.get("/appointments")
def get_my_appointments(username: str = Depends(get_current_user)):
    db = SessionLocal()
    try:
        return db.query(AppointmentDB).filter(AppointmentDB.username == username).all()
    finally:
        db.close()
