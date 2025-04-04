import sqlite3
import asyncio
from aiogram import Router, F, html
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramAPIError

from config import STARS_AMOUNT, MESSAGES, ADMINS
from loader import bot

router = Router()

# 📦 Состояния
class GiftState(StatesGroup):
    waiting_for_username = State()

# 🗄️ Инициализация базы данных и создание таблицы
def create_db():
    try:
        conn = sqlite3.connect('user_payments.db')  # Создаём/открываем базу данных
        cursor = conn.cursor()
        cursor.execute(''' 
            CREATE TABLE IF NOT EXISTS payments (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        print("База данных и таблица успешно созданы.")
    except sqlite3.Error as e:
        print(f"Ошибка при создании базы данных или таблицы: {e}")

# 🗄️ Сохранение данных в базе данных
def save_payment(user_id, username):
    conn = sqlite3.connect('user_payments.db')
    cursor = conn.cursor()
    cursor.execute(''' 
        INSERT OR REPLACE INTO payments (user_id, username)
        VALUES (?, ?)
    ''', (user_id, username))
    conn.commit()
    conn.close()

# 🗄️ Получение данных о платеже пользователя
def get_user_payment(user_id):
    conn = sqlite3.connect('user_payments.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM payments WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# 🗄️ Хранение последних сообщений пользователей
user_messages = {}

# 🔹 Получение ID последнего сообщения пользователя
def get_message(user_id):
    return user_messages.get(user_id)

# 🔹 Удаление старого сообщения перед отправкой нового
async def delete_old_message(user_id, chat_id):
    old_message_id = get_message(user_id)
    if old_message_id:
        try:
            await bot.delete_message(chat_id, old_message_id)
        except TelegramAPIError as e:
            print(f"Ошибка при удалении сообщения: {e}")

# 🔹 Функция для демонстрации "бот печатает" с задержкой
async def send_typing_action(chat_id, delay=0):  # Убираем задержку
    await bot.send_chat_action(chat_id, action="typing")  # Сообщаем, что бот печатает
    await asyncio.sleep(delay)  # Убираем задержку, ставим 0 для мгновенного ответа

# 🔹 /start – Удаляет старое сообщение и отправляет новое
@router.message(F.text == "/start")
async def cmd_start(message: Message):
    # Показать, что бот "печатает" мгновенно
    await send_typing_action(message.chat.id, 0)
    
    user_payment = get_user_payment(message.from_user.id)
    
    if user_payment:  # Если пользователь уже оплатил
        # Удаляем старое сообщение перед отправкой нового
        await delete_old_message(message.from_user.id, message.chat.id)

        # Пользователь уже оплатил, выводим сообщение о том, что оплата прошла
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Канал ⭐", url="https://t.me/GiftModChannel")]
])
        msg = await message.answer(
            f"🎉 <b>Вы уже оплатили звезды!</b>\n\n"
            "Благодарим вас за оплату! Ожидайте в течение 72 часов, в зависимости от обстоятельств.\n\n"
            "👇 <b>Выбери действие:</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        # Удаляем старое сообщение перед отправкой нового
        await delete_old_message(message.from_user.id, message.chat.id)

        # Если пользователь еще не оплатил, предлагается кнопка для оплаты
        keyboard = InlineKeyboardMarkup(inline_keyboard=[ 
            [InlineKeyboardButton(text="💳 Оплатить 100 ⭐", callback_data="pay_100")] 
        ]) 

        msg = await message.answer(
            "🌟 <b>Добро пожаловать!</b>\n\n"
            "Отправьте 100 звезд, чтобы получить тортик и кота.! 🎂🐱\n\n"
            "👇 <b>Выбери действие:</b>",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    
    user_messages[message.from_user.id] = msg.message_id  # Сохраняем новое сообщение

# 🔹 Кнопка "Оплатить 100 ⭐"
@router.callback_query(F.data == "pay_100")
async def pay_handler(callback: CallbackQuery):
    try:
        # Показать, что бот "печатает" мгновенно
        await send_typing_action(callback.message.chat.id, 0)

        # Удаляем старое сообщение перед отправкой нового
        await delete_old_message(callback.from_user.id, callback.message.chat.id)

        prices = [LabeledPrice(label='Тортик и котик', amount=STARS_AMOUNT)]

        msg = await bot.send_invoice(
            chat_id=callback.from_user.id,
            title='Тортик🎂 & котик🐱',
            description='Оплати 100 ⭐ и получи подарок!',
            provider_token="381764678:TEST:5e4f61fd-b3f1-4d19-9e89-9f81e23893f5",  # Тестовый токен
            currency="XTR",
            prices=prices,
            start_parameter='stars-payment',
            payload='stars-payment-payload'
        )

        user_messages[callback.from_user.id] = msg.message_id  # Обновляем последнее сообщение
        await callback.answer()

    except Exception as e:
        print(f"Ошибка при отправке инвойса: {e}")
        await callback.answer("Произошла ошибка при обработке оплаты. Пожалуйста, попробуйте позже.")

# 🔹 Валидация транзакции перед оплатой
@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: PreCheckoutQuery):
    try:
        # Валидация суммы и других данных
        if pre_checkout_query.invoice_payload != 'stars-payment-payload':
            raise ValueError("Неверная нагрузка запроса.")
        
        # Проверка на сумму
        if pre_checkout_query.total_amount != STARS_AMOUNT:
            raise ValueError("Неверная сумма платежа.")
        
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

    except Exception as e:
        print(f"Ошибка валидации транзакции: {e}")
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=False, error_message="Ошибка проверки.")

# 🔹 Успешная оплата – удаляет старое сообщение и отправляет новое
@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, state: FSMContext):
    try:
        # Показать, что бот "печатает" мгновенно
        await send_typing_action(message.chat.id, 0)
        
        # Проверка на валидность суммы (передаем, например, 100 звёзд)
        if message.successful_payment.total_amount != STARS_AMOUNT:
            raise ValueError("Неверная сумма оплаты.")
        
        # Сохраняем данные о пользователе в базе данных
        username = message.from_user.username if message.from_user.username else "Без username"
        save_payment(message.from_user.id, username)

        # Удаление старого сообщения
        await delete_old_message(message.from_user.id, message.chat.id)

        # Отправка сообщения после успешной оплаты
        msg = await message.answer(
            "✅ <b>Оплата прошла успешно!</b>\n\n"
            "✏️ Напиши свой Telegram username, чтобы получить подарок 🎁",
            parse_mode="HTML"
        )

        user_messages[message.from_user.id] = msg.message_id  # Сохраняем новое сообщение
        await state.set_state(GiftState.waiting_for_username)

    except Exception as e:
        print(f"Ошибка при обработке успешной оплаты: {e}")
        await message.answer("Произошла ошибка при обработке платежа. Пожалуйста, свяжитесь с поддержкой.")

# 🔹 Ввод username – удаляет старое сообщение и отправляет новое
@router.message(GiftState.waiting_for_username)
async def receive_username(message: Message, state: FSMContext):
    username = message.text.strip()
    await state.clear()

    # Показать, что бот "печатает" мгновенно
    await send_typing_action(message.chat.id, 0)

    # Удаляем старое сообщение перед отправкой нового
    await delete_old_message(message.from_user.id, message.chat.id)

    msg = await message.answer(
        f"🎉 <b>Спасибо, @{username}!</b>\n"
        "🎁 Твой подарок уже почти в пути...\n"
        "⏳ <b>Ожидайте до 72 часов!</b>",
        parse_mode="HTML"
    )

    user_messages[message.from_user.id] = msg.message_id  # Сохраняем новое сообщение

# Инициализация базы данных при старте
create_db()
