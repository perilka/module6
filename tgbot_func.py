from datetime import date
from sqlite3 import connect
import time
import telebot
import atexit
import os

# Подключение к боту
MY_TOKEN = os.getenv('TOKEN')
if not MY_TOKEN:
    raise ValueError ("Токен бота не найден. Задайте переменную 'TOKEN'")
bot = telebot.TeleBot(MY_TOKEN)

# Подготовка базы данных
conn = connect('tgbot_users')
cursor = conn.cursor()
cursor.execute('PRAGMA foreign_keys = ON')
atexit.register(conn.close)

## Таблица users хранит информацию о пользователях, включая их уникальные Telegram ID и имена.
cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        name TEXT,
        sleep_status INTEGER
    );
    '''
)

## Таблица sleep_record хранит информацию о ежедневных записях о сне пользователей,
## включая время начала и окончания сна, заметки, а также оценку качества сна.
cursor.execute(
    '''
    CREATE TABLE IF NOT EXISTS sleep_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        sleep_date TEXT NOT NULL,
        sleep_time TEXT,
        wake_time TEXT,
        duration REAL,
        sleep_quality INTEGER,
        note TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
    '''
)
conn.commit()

def get_date() -> str:
    """
    Возвращает текущую дату в текстовом формате

    :return: str
    """
    return date.today().strftime('%Y-%m-%d')


def get_time() -> str:
    """
    Возвращает текущее время в текстовом формате

    :return: str
    """
    return time.strftime('%X')


def load_new_user(chat_id: int):
    """
    Загружает нового пользователя в базу данных

    :param chat_id: int
    :return:
    """
    cursor.execute(
        """
        INSERT INTO users (id, name, sleep_status) 
        VALUES (?, ?, ?);
        """,
        (chat_id, bot.get_chat(chat_id).first_name, 0)
    )
    conn.commit()


def check_existing(chat_id: int):
    """
    Проверяет наличие пользователя в базе данных

    :param chat_id: int
    :return: int
    """
    cursor.execute(
        '''
        SELECT EXISTS (SELECT 1 FROM users WHERE id = ?)
        ''',
        (chat_id,)
    )
    result = cursor.fetchone()
    return result[0] if result else 0


def is_sleeping(chat_id: int):
    """
    Проверяет, начинал ли пользователь цикл сна кнопкой sleep

    :param chat_id: int
    :return: int
    """
    cursor.execute(
        '''
        SELECT sleep_status 
        FROM users
        WHERE id = ?
        ''',
        (chat_id,)
    )
    result = cursor.fetchone()
    return result[0] if result else 0


def load_user_data(chat_id: int) -> dict:
    """
    Возвращает данные о пользователе. Если пользователь новый, создает и возвращает новую запись

    :param chat_id: int
    :return: dict
    """
    if check_existing(chat_id):
        cursor.execute(
            '''
            SELECT sleep_date, sleep_time, wake_time, duration, sleep_quality, note
            FROM sleep_records
            WHERE user_id = ?
            ORDER BY sleep_date DESC
            ''',
            (chat_id,)
        )
        rows = cursor.fetchall()
        user = {
            'name': bot.get_chat(chat_id).first_name,
            'cycles': {},
            'is_sleeping': is_sleeping(chat_id)
        }
        if rows:
            for row in rows:
                user['cycles'][row[0]] = {
                    'sleep_relative_time': row[1],
                    'wake_relative_time': row[2],
                    'duration': row[3],
                    'quality': row[4],
                    'notes': row[5]
                }
        return user
    else:
        new_user = {
            'name': bot.get_chat(chat_id).first_name,
            'cycles': {},
            'is_sleeping': 0
        }
        load_new_user(chat_id)
        return new_user


def save_user_data(chat_id: int, data: dict):
    """
    Обновляет данные о пользователе в базе данных

    :param chat_id: int
    :param data: dict
    :return:
    """
    for cycle_date, cycle in data['cycles'].items():
        cursor.execute(
            '''
            INSERT OR REPLACE INTO sleep_records
            (user_id, sleep_date, sleep_time, wake_time, duration, sleep_quality, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (chat_id, cycle_date,
             cycle.get('sleep_relative_time'),
             cycle.get('wake_relative_time'),
             cycle.get('duration'),
             cycle.get('quality'),
             cycle.get('notes'))
        )

    cursor.execute(
        '''
        UPDATE users
        SET sleep_status = ?
        WHERE id = ?
        ''',
        (data['is_sleeping'], chat_id)
    )

    conn.commit()