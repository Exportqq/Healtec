from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext
import base64
import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:yvtBoBbueGkabrUvJhufVqhVRDVbkptW.proxy.rlwy.net:46067/postgres"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
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


Base.metadata.create_all(bind=engine)


class ClothingItem(BaseModel):
    id: int
    name: str
    price: int
    type: str
    rating: str
    photo: str

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    username: str
    password: str
    repeat_password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class Doctor(BaseModel):
    id: int
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


@app.get("/")
def root():
    return {"message": "API работает"}


# ---------- AUTH ----------

@app.post("/auth/register")
def register(data: RegisterRequest):
    if data.password != data.repeat_password:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")

    db = SessionLocal()
    if db.query(UserDB).filter(UserDB.username == data.username).first():
        db.close()
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    user = UserDB(
        username=data.username,
        password_hash=hash_password(data.password)
    )

    db.add(user)
    db.commit()
    db.close()

    return {"message": "Регистрация успешна"}


@app.post("/auth/login")
def login(data: LoginRequest):
    db = SessionLocal()
    user = db.query(UserDB).filter(UserDB.username == data.username).first()
    db.close()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверные данные")

    return {"message": "Авторизация успешна", "username": user.username}


# ---------- CLOTHES ----------

@app.get("/clothes", response_model=list[ClothingItem])
def get_clothes():
    db = SessionLocal()
    items = db.query(ClothingItemDB).all()
    db.close()
    return items


@app.post("/clothes", response_model=ClothingItem)
async def create_clothing_item(
    id: int = Form(...),
    name: str = Form(...),
    price: int = Form(...),
    type: str = Form(...),
    rating: str = Form(...),
    photo_file: UploadFile = File(...)
):
    if photo_file.content_type != "image/png":
        raise HTTPException(status_code=400, detail="Только PNG")

    photo = base64.b64encode(await photo_file.read()).decode()

    db = SessionLocal()
    if db.query(ClothingItemDB).filter(ClothingItemDB.id == id).first():
        db.close()
        raise HTTPException(status_code=400, detail="ID уже существует")

    item = ClothingItemDB(
        id=id,
        name=name,
        price=price,
        type=type,
        rating=rating,
        photo=photo
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    db.close()
    return item


# ---------- DOCTORS ----------

@app.post("/doctors", response_model=Doctor)
async def create_doctor(
    name: str = Form(...),
    specialty: str = Form(...),
    rating: float = Form(...),
    experience: str = Form(...),
    patients_count: str = Form(...),
    reviews_count: str = Form(...),
    description: str = Form(...),
    diseases: str = Form(...),
    photo_file: UploadFile = File(...)
):
    if photo_file.content_type != "image/png":
        raise HTTPException(status_code=400, detail="Только PNG")

    photo = base64.b64encode(await photo_file.read()).decode()

    db = SessionLocal()
    doctor = DoctorDB(
        name=name,
        specialty=specialty,
        rating=rating,
        photo=photo,
        experience=experience,
        patients_count=patients_count,
        reviews_count=reviews_count,
        description=description,
        diseases=diseases
    )

    db.add(doctor)
    db.commit()
    db.refresh(doctor)
    db.close()

    return {
        **doctor.__dict__,
        "diseases": doctor.diseases.split(",")
    }


@app.get("/doctors", response_model=list[Doctor])
def get_doctors():
    db = SessionLocal()
    doctors = db.query(DoctorDB).all()
    db.close()

    return [
        {**d.__dict__, "diseases": d.diseases.split(",")}
        for d in doctors
    ]


# ---------- APPOINTMENTS ----------

@app.post("/appointments")
def book_appointment(
    username: str = Form(...),
    doctor_id: int = Form(...)
):
    db = SessionLocal()

    if not db.query(UserDB).filter(UserDB.username == username).first():
        db.close()
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if not db.query(DoctorDB).filter(DoctorDB.id == doctor_id).first():
        db.close()
        raise HTTPException(status_code=404, detail="Доктор не найден")

    appointment = AppointmentDB(
        username=username,
        doctor_id=doctor_id
    )

    db.add(appointment)
    db.commit()
    db.close()

    return {"message": "Вы записались к врачу"}
