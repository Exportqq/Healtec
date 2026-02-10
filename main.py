from fastapi import FastAPI, HTTPException, Header, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from uuid import uuid4


DATABASE_URL = "postgresql+psycopg2://postgres:yvtBoBbueGkabrUvJhufVqhVRDVbkptW@switchyard.proxy.rlwy.net:28129/railway"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

tokens_map = {}

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)

class ClothingItemDB(Base):
    __tablename__ = "clothes"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    rating = Column(String, nullable=False)
    photo = Column(Text, nullable=False)

class DoctorDB(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True)
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
    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"))

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

class ClothingItem(BaseModel):
    id: int
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

app = FastAPI(title="Medical & Clothing API", version="1.0.0")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

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
        tokens_map[token] = user.username
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
        tokens_map[token] = user.username
        return {"token": token, "username": user.username}
    finally:
        db.close()

@app.get("/me", response_model=UserInfo)
def me(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Неверный заголовок Authorization")
    token = authorization.split(" ")[1]
    username = tokens_map.get(token)
    if not username:
        raise HTTPException(status_code=401, detail="Неверный токен")
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Не авторизован")
        return user
    finally:
        db.close()

@app.get("/clothes", response_model=list[ClothingItem])
def get_clothes():
    db = SessionLocal()
    try:
        return db.query(ClothingItemDB).all()
    finally:
        db.close()

@app.post("/clothes", response_model=ClothingItem)
def create_clothing_item(item: ClothingItem):
    db = SessionLocal()
    try:
        db_item = ClothingItemDB(**item.dict())
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    finally:
        db.close()

@app.post("/doctors", response_model=Doctor)
def create_doctor(
    name: str = Form(...),
    specialty: str = Form(...),
    rating: float = Form(...),
    photo: UploadFile = File(...),  # <--- теперь файл
    experience: str = Form(...),
    patients_count: str = Form(...),
    reviews_count: str = Form(...),
    description: str = Form(...),
    diseases: str = Form(...)
):
    # Сохраняем файл на диск (например)
    file_location = f"photos/{photo.filename}"
    with open(file_location, "wb") as f:
        f.write(photo.file.read())

    db = SessionLocal()
    try:
        db_doctor = DoctorDB(
            name=name,
            specialty=specialty,
            rating=rating,
            photo=file_location,  # путь к файлу в БД
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
            name=name,
            specialty=specialty,
            rating=rating,
            photo=file_location,  # путь к файлу
            experience=experience,
            patients_count=patients_count,
            reviews_count=reviews_count,
            description=description,
            diseases=diseases.split(",")
        )
    finally:
        db.close()




@app.get("/doctors", response_model=list[Doctor])
def get_doctors():
    db = SessionLocal()
    try:
        doctors = db.query(DoctorDB).all()
        return [{**d.__dict__, "diseases": d.diseases.split(",")} for d in doctors]
    finally:
        db.close()
