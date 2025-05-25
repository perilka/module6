import os
import random
import time

import telebot
from telebot import types

from tgbot_func import get_date, get_time, load_user_data, save_user_data

info = {}
TEXT_ERROR = 'Произошла ошибка. Попробуй другую команду или перезапусти бота.'


# Подключение к боту
MY_TOKEN = os.getenv('TOKEN')
if not MY_TOKEN:
    raise ValueError ("Токен бота не найден. Задайте переменную 'TOKEN'")
bot = telebot.TeleBot(MY_TOKEN)


@bot.message_handler(commands=['start'])
def start(message: telebot.types.Message):
    """
    Обработчик команды /start

    :param message: telebot.types.Message
    :return:
    """
    info[message.chat.id] = load_user_data(message.chat.id)
    current_user = info[message.chat.id]

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('О командах'))
    bot.send_message(message.chat.id,
                     f'Привет, {current_user["name"]}! Я буду помогать тебе отслеживать сон. '
                     'Используй команды /sleep, /wake, /quality, /notes '
                     'и кнопки ниже, чтобы управлять ботом.',
                     reply_markup=markup)


@bot.message_handler(commands=['sleep'])
def sleep(message: telebot.types.Message):
    """
    Обработчик команды /sleep; дополнительно проверяет, может ли пользователь начать цикл

    :param message: telebot.types.Message
    :return:
    """
    current_user = info[message.chat.id]
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


def create_new_cycle(user: dict, date: str, message: telebot.types.Message):
    """
    Создает новый цикл, отмечает время старта

    :param user: dict
    :param date: str
    :param message: telebot.types.Message
    :return:
    """
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

    bot.send_message(message.chat.id, f'Отмечено время отхода ко сну: {relative_time}')
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('О командах'))
    options = ['Доброй ночи!', 'Уютных снов!', 'Мягких подушек!', 'Спокойной ночи!', 'Комфортного сна!']
    bot.send_message(message.chat.id, f'{random.choice(options)} Не забудь сообщить о пробуждении: /wake',
                     reply_markup=markup)
    save_user_data(message.chat.id, user)


@bot.message_handler(commands=['wake'])
def wake(message: telebot.types.Message):
    """
    Обработчик команды /wake; дополнительно проверяет, начинал ли пользователь цикл

    :param message: telebot.types.Message
    :return:
    """
    current_user = info[message.chat.id]
    if not current_user['is_sleeping']:
        bot.send_message(message.chat.id, 'Я не вижу, чтобы ты сообщил о начале сна. '
                                          'Используй команду /sleep.')
        return

    current_date = list(current_user['cycles'].keys())[-1]
    finish_cycle(current_user, current_date, message)


def finish_cycle(user: dict, date: str, message: telebot.types.Message):
    """
    Завершает цикл и рассчитывает продолжительность сна

    :param user: dict
    :param date: str
    :param message: telebot.types.Message
    :return:
    """
    absolute_time = time.time()
    relative_time = get_time()
    cycle = user['cycles'][date]
    cycle['wake_relative_time'] = relative_time
    cycle['wake_absolute_time'] = absolute_time
    cycle['duration'] = round((absolute_time - cycle['sleep_absolute_time']) / 3600, 2)
    user['is_sleeping'] = 0

    bot.send_message(message.chat.id, f'Отмечено время пробуждения: {relative_time}')
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('О командах'))
    options = ['Доброе утро!', 'Надеюсь, ты хорошо поспал!', 'Вперед, в новый день!']
    bot.send_message(message.chat.id,
                     f'{random.choice(options)} '
                     f'Продолжительность твоего сна составила примерно {cycle["duration"]} часов. '
                     'Оцени качество сна: /quality, добавь заметки: /notes',
                     reply_markup=markup)
    save_user_data(message.chat.id, user)


@bot.message_handler(commands=['quality'])
def quality(message: telebot.types.Message):
    """
    Обработчик команды /quality

    :param message: telebot.types.Message
    :return:
    """
    if check_possibility_quality(message):
        add_quality(message)
    else:
        bot.send_message(message.chat.id, 'Сначала заверши цикл сна: /sleep и /wake.')


def check_possibility_quality(message: telebot.types.Message) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к команде /quality

    :param message: telebot.types.Message
    :return: bool
    """
    current_user = info[message.chat.id]
    if not current_user['cycles'] or current_user['is_sleeping']:
        return False
    return True


def add_quality(message: telebot.types.Message):
    """
    Обрабатывает сообщение с оценкой пользователя и сохраняет её

    :param message: telebot.types.Message
    :return:
    """
    quality_list = message.text.split()
    try:
        quality_value = int(quality_list[1])
    except (IndexError, ValueError):
        bot.send_message(message.chat.id, 'Введи число от 1 до 10 после команды (пример: /quality 8).')
        return

    if quality_value not in range(1, 11):
        bot.send_message(message.chat.id, 'Оценка должна быть от 1 до 10.')
        return

    current_date = list(info[message.chat.id]['cycles'].keys())[-1]
    cycle = info[message.chat.id]['cycles'][current_date]
    cycle['quality'] = quality_value

    if quality_value <= 5:
        bot.reply_to(message, 'Что-то беспокоило? Напиши об этом в /notes.')
    elif quality_value == 10:
        bot.reply_to(message, 'Супер! Надеюсь, таких ночей будет больше!')
    else:
        bot.reply_to(message, 'Здорово, что ты хорошо отдохнул!')
    bot.send_message(message.chat.id, 'Добавь заметки: /notes '
                                '(пример: /notes спалось хорошо, снился странный сон про кабачки).')
    save_user_data(message.chat.id, info[message.chat.id])


@bot.message_handler(commands=['notes'])
def notes(message: telebot.types.Message):
    """
    Обработчик команды /notes

    :param message: telebot.types.Message
    :return:
    """
    if check_possibility_notes(message):
        add_notes(message)
    else:
        bot.send_message(message.chat.id, 'Оцени качество сна перед добавлением заметок: /quality.')


def check_possibility_notes(message: telebot.types.Message) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к команде /notes

    :param message: telebot.types.Message
    :return: bool
    """
    current_user = info[message.chat.id]
    if not current_user['cycles'] or current_user['is_sleeping']:
        return False
    current_date = list(current_user['cycles'].keys())[-1]
    cycle = current_user['cycles'].get(current_date)
    if cycle and cycle.get('quality') != 0:
        return True
    return True


def add_notes(message: telebot.types.Message):
    """
    Обрабатывает сообщение пользователя с заметкой и сохраняет её

    :param message: telebot.types.Message
    :return:
    """
    notes_list = message.text.split()
    if len(notes_list) <= 1:
        bot.send_message(message.chat.id, 'Напиши заметку после команды '
                                    '(пример: /notes спала нормально, снился странный сон про яблоки).')
        return

    notes_list.pop(0)
    notes_str = ' '.join(notes_list)
    current_date = list(info[message.chat.id]['cycles'].keys())[-1]
    info[message.chat.id]['cycles'][current_date]['notes'] = notes_str

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('Моя статистика'))
    bot.send_message(message.chat.id, 'Заметки сохранены! Посмотри статистику.', reply_markup=markup)
    save_user_data(message.chat.id, info[message.chat.id])


@bot.message_handler(func=lambda message: message.text == 'О командах')
def about_commands(message: telebot.types.Message):
    """
    Обработчик "О командах"

    :param message: telebot.types.Message
    :return:
    """
    bot.send_message(message.chat.id,
                     'Сообщи о сне: /sleep, о пробуждении: /wake\n'
                     'Оцени качество по 10-балльной шкале: /quality (пример: /quality 8)\n'
                     'Добавь заметки: /notes '
                     '(пример: /notes спала отлично, снился странный сон про арбузы)')


@bot.message_handler(func=lambda message: message.text == 'Да, начать новый цикл')
def new_cycle(message: telebot.types.Message):
    """
    Обработчик "Да, начать новый цикл": перезаписывает цикл для текущей даты

    :param message: telebot.types.Message
    :return:
    """
    current_date = get_date()
    current_user = info[message.chat.id]
    create_new_cycle(current_user, current_date, message)


@bot.message_handler(func=lambda message: message.text == 'Оставить предыдущую запись')
def cycle_cancellation(message: telebot.types.Message):
    """
    Обработчик "Оставить предыдущую запись"

    :param message: telebot.types.Message
    :return:
    """
    bot.send_message(message.chat.id, f'Статистика за {get_date()} не изменена.')


@bot.message_handler(func=lambda message: message.text == 'Моя статистика')
def print_stat(message: telebot.types.Message):
    """
    Обработчик "Моя статистика"; дополнительно проверяет, есть ли у пользователя доступ к статистике

    :param message: telebot.types.Message
    :return:
    """
    current_user = info[message.chat.id]
    if not current_user['cycles']:
        bot.send_message(message.chat.id, 'Внеси запись о сне для статистики.')
        return
    select_date(message)


def select_date(message: telebot.types.Message):
    """
    Выводит кнопки с доступными для статистики датами

    :param message: telebot.types.Message
    :return:
    """
    current_user = info[message.chat.id]
    markup = types.InlineKeyboardMarkup()
    for date in current_user['cycles'].keys():
        markup.add(types.InlineKeyboardButton(date, callback_data=f'stat_{date}'))
    bot.send_message(message.chat.id, 'Выбери дату для статистики:', reply_markup=markup)


# Обработчик статистики
@bot.callback_query_handler(func=lambda call: call.data.startswith('stat_'))
def callback_stat(call: telebot.types.CallbackQuery):
    """
    Проверяет доступность выбранной даты для отображения статистики, отправляет статистику пользователю

    :param call: telebot.types.CallbackQuery
    :return:
    """
    current_user = info.get(call.message.chat.id)
    if not current_user or not current_user['cycles']:
        bot.send_message(call.message.chat.id, 'Нет данных для статистики.')
        return
    date = call.data.split('_')[1]
    cycle = current_user['cycles'].get(date)
    if not cycle:
        bot.send_message(call.message.chat.id, f'Нет данных за {date}.')
        return
    bot.send_message(call.message.chat.id,
                     f'Статистика за {date}:\n'
                     f'Отход ко сну: {cycle.get("sleep_relative_time", "Не указано")}\n'
                     f'Пробуждение: {cycle.get("wake_relative_time", "Не указано")}\n'
                     f'Длительность: {cycle.get("duration", 0)} ч\n'
                     f'Качество: {cycle.get("quality", 0)}\n'
                     f'Заметки: {cycle.get("notes", "Нет")}')
    bot.send_message(call.message.chat.id, 'Собираешься спать? Используй /sleep!')


@bot.message_handler(content_types=['text'])
def other_text(message: telebot.types.Message):
    """
    Обработчик остальных сообщений

    :param message: telebot.types.Message
    :return:
    """
    bot.reply_to(message, 'Я не смог распознать команду. Попробуй еще раз.')


# Запуск бота
bot.polling(none_stop=True)