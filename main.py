from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError
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


@app.post("/auth/register")
def register(data: RegisterRequest):
    if data.password != data.repeat_password:
        raise HTTPException(status_code=400, detail="Пароли не совпадают")

    db = SessionLocal()
    try:
        user = UserDB(
            username=data.username,
            password_hash=hash_password(data.password)
        )
        db.add(user)
        db.commit()
        return {"message": "Регистрация успешна"}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Username уже существует")
    finally:
        db.close()


@app.post("/auth/login")
def login(data: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == data.username).first()
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверные данные")
        return {"message": "Авторизация успешна"}
    finally:
        db.close()


@app.get("/me", response_model=UserInfo)
def me(x_username: str = Header(...)):
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.username == x_username).first()
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
def create_doctor(doctor: Doctor):
    db = SessionLocal()
    try:
        db_doctor = DoctorDB(
            name=doctor.name,
            specialty=doctor.specialty,
            rating=doctor.rating,
            photo=doctor.photo,
            experience=doctor.experience,
            patients_count=doctor.patients_count,
            reviews_count=doctor.reviews_count,
            description=doctor.description,
            diseases=",".join(doctor.diseases)
        )
        db.add(db_doctor)
        db.commit()
        db.refresh(db_doctor)
        return {
            **db_doctor.__dict__,
            "diseases": db_doctor.diseases.split(",")
        }
    finally:
        db.close()


@app.get("/doctors", response_model=list[Doctor])
def get_doctors():
    db = SessionLocal()
    try:
        doctors = db.query(DoctorDB).all()
        return [
            {**d.__dict__, "diseases": d.diseases.split(",")}
            for d in doctors
        ]
    finally:
        db.close()
