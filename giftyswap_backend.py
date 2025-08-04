# backend/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List
from uuid import uuid4
from datetime import datetime, timedelta
import asyncio

app = FastAPI()

# Данные в памяти
DEALS: Dict[str, Dict] = {}
ADMIN_ID = "@drainss"
ADMIN_TELEGRAM_ID = 123456789  # Заменить на реальный Telegram ID администратора
COMMISSION_PERCENT = 2
TIMEOUT_MINUTES = 10

# Модель сделки
class Deal(BaseModel):
    id: str
    buyer_id: int
    seller_id: int
    gift_id: str
    price_ton: float
    buyer_confirmed: bool = False
    seller_confirmed: bool = False
    status: str = "pending"
    created_at: datetime = datetime.utcnow()
    timer_started: bool = False
    timer_started_at: datetime = None

@app.post("/create")
def create_deal(data: Deal):
    if data.id in DEALS:
        raise HTTPException(400, detail="Сделка уже существует")
    DEALS[data.id] = data.dict()
    return {"message": "Сделка создана"}

@app.post("/confirm")
def confirm_deal(deal_id: str, by_user: int):
    deal = DEALS.get(deal_id)
    if not deal:
        raise HTTPException(404, detail="Сделка не найдена")

    if deal["buyer_id"] == by_user:
        deal["buyer_confirmed"] = True
    elif deal["seller_id"] == by_user:
        deal["seller_confirmed"] = True
    else:
        raise HTTPException(403, detail="Вы не участвуете в сделке")

    if deal["buyer_confirmed"] and deal["seller_confirmed"]:
        deal["status"] = "completed"
        deal["confirmed_at"] = datetime.utcnow()
        ton_total = deal["price_ton"]
        commission = round(ton_total * COMMISSION_PERCENT / 100, 2)
        seller_amount = ton_total - commission
        return {
            "message": "Сделка завершена",
            "transfer": {
                "to_seller": seller_amount,
                "to_admin": commission
            }
        }

    return {"message": "Один из участников подтвердил сделку"}

@app.post("/cancel")
def cancel_deal(deal_id: str, by_user: int):
    deal = DEALS.get(deal_id)
    if not deal:
        raise HTTPException(404, detail="Сделка не найдена")
    if by_user not in [deal["buyer_id"], deal["seller_id"]] and by_user != ADMIN_TELEGRAM_ID:
        raise HTTPException(403, detail="Вы не участник сделки и не администратор")
    deal["status"] = "cancelled"
    return {"message": "Сделка отменена, средства возвращены"}

@app.get("/deals/{user_id}")
def get_user_deals(user_id: int):
    return [d for d in DEALS.values() if d["buyer_id"] == user_id or d["seller_id"] == user_id]

@app.get("/admin/deals")
def get_all_deals(admin_id: int):
    if admin_id != ADMIN_TELEGRAM_ID:
        raise HTTPException(403, detail="Доступ запрещён")
    return list(DEALS.values())

@app.post("/trigger_timer")
def trigger_timer(deal_id: str, by_user: int):
    deal = DEALS.get(deal_id)
    if not deal or deal["status"] != "pending":
        raise HTTPException(400, detail="Неверная сделка")
    if by_user not in [deal["buyer_id"], deal["seller_id"]]:
        raise HTTPException(403, detail="Вы не участник сделки")

    deal["timer_started"] = True
    deal["timer_started_at"] = datetime.utcnow()
    asyncio.create_task(check_timeout(deal_id))
    return {"message": "Таймер запущен"}

@app.post("/call_admin")
def call_admin(deal_id: str, by_user: int):
    deal = DEALS.get(deal_id)
    if not deal:
        raise HTTPException(404, detail="Сделка не найдена")
    return {"message": f"Администратор {ADMIN_ID} будет уведомлён."}

async def check_timeout(deal_id: str):
    await asyncio.sleep(TIMEOUT_MINUTES * 60)
    deal = DEALS.get(deal_id)
    if deal and deal["status"] == "pending" and deal["timer_started"]:
        deal["status"] = "cancelled"
        return {"message": "Сделка отменена по таймеру, средства возвращены"}
