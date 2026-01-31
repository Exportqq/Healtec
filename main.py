from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from typing import List
import base64

# MARK: - Модель данных
class SportCard(BaseModel):
    id: int
    sportName: str
    sportResult: str
    photo: str  # base64-кодированное изображение PNG

# MARK: - Инициализация приложения
app = FastAPI(title="Sport Card API", description="API для спортивных карточек", version="1.0.0")

# MARK: - База данных (в памяти)
cards_db: List[SportCard] = []

# MARK: - Эндпоинт GET /cards
@app.get("/cards", response_model=List[SportCard], summary="Получить все спортивные карточки")
async def get_cards():
    """
    Возвращает список всех спортивных карточек.
    """
    return cards_db

# MARK: - Эндпоинт POST /cards
@app.post("/cards", response_model=SportCard, summary="Добавить новую спортивную карточку")
async def create_card(
    id: int = Form(...),
    sportName: str = Form(...),
    sportResult: str = Form(...),
    photo_file: UploadFile = File(...)
):
    """
    Добавляет новую спортивную карточку с PNG фотографией.
    """
    # Проверяем формат файла
    if photo_file.content_type != "image/png":
        return {"error": "Только PNG изображения разрешены"}

    # Читаем файл и конвертируем в base64
    photo_bytes = await photo_file.read()
    photo_base64 = base64.b64encode(photo_bytes).decode("utf-8")

    card = SportCard(
        id=id,
        sportName=sportName,
        sportResult=sportResult,
        photo=photo_base64
    )
    cards_db.append(card)
    return card
