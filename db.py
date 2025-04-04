# db.py

import sqlite3

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
