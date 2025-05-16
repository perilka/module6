import telebot
from telebot import types
import os
import random
import time
from datetime import date
from sqlite3 import connect
import atexit


info = {}
TEXT_ERROR = 'Произошла ошибка. Попробуй другую команду или перезапусти бота.'


# Подключение к боту
MY_TOKEN = os.getenv('token')
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
    cursor.execute(
        '''
        SELECT EXISTS (SELECT 1 FROM users WHERE id = ?)
        ''',
        (chat_id,)
    )
    result = cursor.fetchone()
    return result[0] if result else 0


def is_sleeping(chat_id: int):
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


def save_user_data(chat_id, data):
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



# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message: telebot.types.Message):
    info[message.chat.id] = load_user_data(message.chat.id)
    current_user = info[message.chat.id]

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('О командах'))
    bot.send_message(message.chat.id,
                     f'Привет, {current_user["name"]}! Я буду помогать тебе отслеживать сон. '
                     'Используй команды /sleep, /wake, /quality, /notes '
                     'и кнопки ниже, чтобы управлять ботом.',
                     reply_markup=markup)


# Обработчик команды /sleep
@bot.message_handler(commands=['sleep'])
def sleep(message: telebot.types.Message):
    current_user = info.get(message.chat.id)
    current_date = get_date()

    if current_user['is_sleeping']:
        bot.send_message(message.chat.id, 'Похоже, ты пытаешься начать новый цикл сна, не закончив предыдущий. '
                                              'Воспользуйся командой /wake, чтобы завершить текущий цикл.')
        return

    if current_date in current_user['cycles']:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton('Да, начать новый цикл'), types.KeyboardButton('Оставить предыдущую запись'))
        bot.send_message(message.chat.id,
                         'Сегодня ты уже начинал цикл сна. Начать новый? (Предыдущий будет перезаписан.)',
                         reply_markup=markup)
    else:
        create_new_cycle(current_user, current_date, message)


def create_new_cycle(user, date, m: telebot.types.Message):
    absolute_time = time.time()
    relative_time = get_time()
    user['cycles'][date] = {
        'quality': 0,
        'notes': None,
        'sleep_relative_time': relative_time,
        'sleep_absolute_time': absolute_time,
        'wake_relative_time': None,
        'wake_absolute_time': None,
        'duration': None
    }
    user['is_sleeping'] = 1

    bot.send_message(m.chat.id, f'Отмечено время отхода ко сну: {relative_time}')
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('О командах'))
    options = ['Доброй ночи!', 'Уютных снов!', 'Мягких подушек!', 'Спокойной ночи!', 'Комфортного сна!']
    bot.send_message(m.chat.id, f'{random.choice(options)} Не забудь сообщить о пробуждении: /wake',
                     reply_markup=markup)
    save_user_data(m.chat.id, user)


# Обработчик команды /wake
@bot.message_handler(commands=['wake'])
def wake(message: telebot.types.Message):
    current_user = info.get(message.chat.id)
    if not current_user['is_sleeping']:
        bot.send_message(message.chat.id, 'Я не вижу, чтобы ты сообщил о начале сна. '
                                          'Используй команду /sleep.')
        return

    current_date = list(current_user['cycles'].keys())[-1]
    finish_cycle(current_user, current_date, message)


def finish_cycle(user, date, m: telebot.types.Message):
    absolute_time = time.time()
    relative_time = get_time()
    cycle = user['cycles'][date]
    cycle['wake_relative_time'] = relative_time
    cycle['wake_absolute_time'] = absolute_time
    cycle['duration'] = round((absolute_time - cycle['sleep_absolute_time']) / 3600, 2)
    user['is_sleeping'] = 0

    bot.send_message(m.chat.id, f'Отмечено время пробуждения: {relative_time}')
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('О командах'))
    options = ['Доброе утро!', 'Надеюсь, ты хорошо поспал!', 'Вперед, в новый день!']
    bot.send_message(m.chat.id,
                     f'{random.choice(options)} '
                     f'Продолжительность твоего сна составила примерно {cycle["duration"]} часов. '
                     'Оцени качество сна: /quality, добавь заметки: /notes',
                     reply_markup=markup)
    save_user_data(m.chat.id, user)


# Обработчик команды /quality
@bot.message_handler(commands=['quality'])
def quality(message: telebot.types.Message):
    current_user = info.get(message.chat.id)
    if not current_user['cycles'] or current_user['is_sleeping']:
        bot.send_message(message.chat.id, 'Сначала заверши цикл сна: /sleep и /wake.')
        return
    add_quality(message)


def add_quality(m: telebot.types.Message):
    quality_list = m.text.split()
    try:
        quality_value = int(quality_list[1])
    except (IndexError, ValueError):
        bot.send_message(m.chat.id, 'Введи число от 1 до 10 после команды (пример: /quality 8).')
        return

    if quality_value not in range(1, 11):
        bot.send_message(m.chat.id, 'Оценка должна быть от 1 до 10.')
        return

    current_date = list(info[m.chat.id]['cycles'].keys())[-1]
    cycle = info[m.chat.id]['cycles'][current_date]
    cycle['quality'] = quality_value

    if quality_value <= 5:
        bot.reply_to(m, 'Что-то беспокоило? Напиши об этом в /notes.')
    elif quality_value == 10:
        bot.reply_to(m, 'Супер! Надеюсь, таких ночей будет больше!')
    else:
        bot.reply_to(m, 'Здорово, что ты хорошо отдохнул!')
    bot.send_message(m.chat.id, 'Добавь заметки: /notes '
                                '(пример: /notes спалось хорошо, снился странный сон про кабачки).')
    save_user_data(m.chat.id, info[m.chat.id])


# Обработчик команды /notes
@bot.message_handler(commands=['notes'])
def notes(message: telebot.types.Message):
    if check_possibility_notes(message):
        add_notes(message)
    else:
        bot.send_message(message.chat.id, 'Оцени качество сна перед добавлением заметок: /quality.')


def check_possibility_notes(m: telebot.types.Message):
    current_user = info.get(m.chat.id)
    if not current_user['cycles']:
        return False
    current_date = list(current_user['cycles'].keys())[-1]
    cycle = current_user['cycles'].get(current_date)
    return cycle and cycle.get('quality') != 0


def add_notes(m: telebot.types.Message):
    notes_list = m.text.split()
    if len(notes_list) <= 1:
        bot.send_message(m.chat.id, 'Напиши заметку после команды '
                                    '(пример: /notes спала нормально, снился странный сон про яблоки).')
        return

    notes_list.pop(0)
    notes_str = ' '.join(notes_list)
    current_date = list(info[m.chat.id]['cycles'].keys())[-1]
    info[m.chat.id]['cycles'][current_date]['notes'] = notes_str

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('Моя статистика'))
    bot.send_message(m.chat.id, 'Заметки сохранены! Посмотри статистику.', reply_markup=markup)
    save_user_data(m.chat.id, info[m.chat.id])


# Обработчик "О командах"
@bot.message_handler(func=lambda message: message.text == 'О командах')
def about_commands(message: telebot.types.Message):
    bot.send_message(message.chat.id,
                     'Сообщи о сне: /sleep, о пробуждении: /wake\n'
                     'Оцени качество по 10-балльной шкале: /quality (пример: /quality 8)\n'
                     'Добавь заметки: /notes '
                     '(пример: /notes спала отлично, снился странный сон про арбузы)')


# Обработчик "Да, начать новый цикл"
@bot.message_handler(func=lambda message: message.text == 'Да, начать новый цикл')
def new_cycle(message: telebot.types.Message):
    current_date = get_date()
    current_user = info.get(message.chat.id)
    create_new_cycle(current_user, current_date, message)


# Обработчик "Оставить предыдущую запись"
@bot.message_handler(func=lambda message: message.text == 'Оставить предыдущую запись')
def cycle_cancellation(message: telebot.types.Message):
    bot.send_message(message.chat.id, f'Статистика за {get_date()} не изменена.')


# Обработчик "Моя статистика"
@bot.message_handler(func=lambda message: message.text == 'Моя статистика')
def print_stat(message: telebot.types.Message):
    current_user = info.get(message.chat.id)
    if not current_user['cycles']:
        bot.send_message(message.chat.id, 'Внеси запись о сне для статистики.')
        return
    select_date(message)


def select_date(message: telebot.types.Message):
    current_user = info.get(message.chat.id)
    markup = types.InlineKeyboardMarkup()
    for date in current_user['cycles'].keys():
        markup.add(types.InlineKeyboardButton(date, callback_data=f'stat_{date}'))
    bot.send_message(message.chat.id, 'Выбери дату для статистики:', reply_markup=markup)


# Обработчик статистики
@bot.callback_query_handler(func=lambda call: call.data.startswith('stat_'))
def callback_stat(call):
    date = call.data.split('_')[1]
    current_user = info.get(call.message.chat.id)
    cycle = current_user['cycles'].get(date)
    bot.send_message(call.message.chat.id,
                     f'Статистика за {date}:\n'
                     f'Отход ко сну: {cycle["sleep_relative_time"]}\n'
                     f'Пробуждение: {cycle["wake_relative_time"]}\n'
                     f'Длительность: {cycle["duration"]} ч\n'
                     f'Качество: {cycle["quality"]}\n'
                     f'Заметки: {cycle["notes"] or "Нет"}')
    bot.send_message(call.message.chat.id, 'Собираешься спать? Используй /sleep!')


# Обработчик всякого разного остального
@bot.message_handler(content_types=['text'])
def other_text(message: telebot.types.Message):
    bot.reply_to(message, 'Я не смог распознать команду. Попробуй еще раз.')


# Запуск бота
bot.polling(none_stop=True)