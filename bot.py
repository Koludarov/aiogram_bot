import os
import logging

import requests
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import exceptions

from dotenv import load_dotenv

# Подключаем логгирование
logger = logging.getLogger(__name__)
logging.basicConfig(
    filename='aiogram_bot.log',
    format='[%(asctime)s | %(levelname)s]: %(message)s',
    datefmt='%m.%d.%Y %H:%M:%S',
    level=logging.INFO
)

# Забираем значения из .env файла
load_dotenv()

# API ключи
WEATHER_API_KEY = os.environ.get('WEATHER_API_KEY')
EXCHANGE_API_KEY = os.environ.get('EXCHANGE_API_KEY')
ANIMALS_API_KEY = os.environ.get('ANIMALS_API_KEY')
BOT_TOKEN = os.environ.get('BOT_TOKEN')


class WeatherState(StatesGroup):
    """Состояние для запроса погоды"""
    city = State()


class ExchangeState(StatesGroup):
    """Состояние для запроса конвертации валюты"""
    currency = State()


class CreatePoll(StatesGroup):
    """Состояние для создания опроса"""
    poll_name = State()
    poll_options = State()
    chat_id = State()


# Хранилище для состояний
storage = MemoryStorage()
# Создаем бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)


# Функция приветствия
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    """
    Отправляет сообщение со списком функций бота.
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = [
        types.KeyboardButton(text='Погода 🌦', callback_data='weather'),
        types.KeyboardButton(text='Конвертер валют 💰', callback_data='/currency_converter'),
        types.KeyboardButton(text='Милые животные 🐶', callback_data='/cute_animals'),
        types.KeyboardButton(text='Опросы 📊', callback_data='/surveys')
    ]
    keyboard.add(*buttons)
    await message.answer('Привет! Что я могу для тебя сделать?', reply_markup=keyboard)


@dp.message_handler(commands=['help'])
async def help_handler(message: types.Message):
    """
    Отправляет сообщение со списком доступных команд бота.
    """
    help_text = "Список доступных команд:\n"
    help_text += "/start - начать использование бота\n"
    help_text += "/help - получить список доступных команд\n"
    help_text += "/weather <город> - узнать погоду в указанном городе\n"
    help_text += "/currency_converter <количество> <из валюты> to <в валюту> - конвертировать валюту\n"
    help_text += "/cute_animals - Получить милую картинку животного\n"
    help_text += "/survey Создать опрос\n"
    await message.answer(help_text)


@dp.message_handler(commands=['weather'])
@dp.message_handler(lambda message: message.text == 'Погода 🌦')
async def weather(message: types.Message):
    """
    Обрабатывает команду /weather и запускает состояние.
    """
    await message.answer('Какой город вам интересен?')
    await WeatherState.city.set()


# Функция для получения погоды
@dp.message_handler(state=WeatherState.city)
async def get_weather(message: types.Message, state: FSMContext):
    """
    Получает погоду в указанном городе и отправляет ее пользователю.
    """
    # Получаем город от пользователя
    city = message.text
    # Формируем URL для запроса
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric'
    # Отправляем запрос и получаем данные
    response = requests.get(url).json()
    # Получаем данные о погоде
    if response['cod'] == 200:
        description = response['weather'][0]['description']
        temperature = response['main']['temp']
        feels_like = response['main']['feels_like']
        humidity = response['main']['humidity']
        wind_speed = response['wind']['speed']
        # Отправляем сообщение с погодой
        await message.answer(
            f'Сейчас в {city} {description}, температура {temperature}°C, ощущается как {feels_like}°C.\n'
            f'Влажность {humidity}%, скорость ветра {wind_speed} м/с.')
    else:
        await message.answer(f'Не удалось получить погоду для {city}.')
        logging.exception(f'Ошибка при подключении к api.openweathermap. Код {response["cod"]}')
    # Сбрасываем состояние
    await state.finish()


# Функция для конвертации валют
@dp.message_handler(commands=['currency_converter'])
@dp.message_handler(lambda message: message.text == 'Конвертер валют 💰')
async def handle_convert(message: types.Message):
    """
    Обрабатывает команду /currency_converter и запускает состояние.
    """
    await message.answer('Укажите сумму и валюты в формате: \n <сумма> <Валюта1> <Валюта2> ')
    await ExchangeState.currency.set()


@dp.message_handler(state=ExchangeState.currency)
async def convert_currency(message: types.Message, state: FSMContext):
    """
    Получает курс валют, конвертирует и отправляет результат пользователю.
    """
    # Обработка выхода из состояния
    if message.text == 'Меню':
        await state.finish()
        await message.reply('Успешно вернулись в меню\nПомощь - /help')
        return

    try:
        amount, from_currency, to_currency = message.text.split()
    except ValueError:
        # Если пользователь ввел неверный формат сообщения, отправляем ему подсказку
        await message.reply(
            """
            Неверный формат сообщения. Введите сообщение в формате '<сумма> <Валюта1> <Валюта2>'.
            \nДля выхода - напишите: \nМеню
            """)
        return

    # Проверяем, что количество является числом
    try:
        amount = float(amount)
    except ValueError:
        # Если количество не является числом, отправляем пользователю сообщение об ошибке
        await message.reply("Количество должно быть числом.")
        return

    # Запрос курса валют по API
    headers = {"apikey": EXCHANGE_API_KEY}
    url = f"https://api.apilayer.com/exchangerates_data/convert?to={to_currency}&from={from_currency}&amount={amount}"
    response = requests.request("GET", url, headers=headers)

    # Обработка ответа от API
    if response.status_code != 200:
        await message.reply("Ошибка при получении курса валют.")
        logging.exception(f'Ошибка при подключении к api.apilayer. {response.status_code}')
        await state.finish()
        return
    data = response.json()
    try:
        rate = data["info"]["rate"]
    except KeyError:
        await message.reply(f"Валюта {to_currency.upper()} не найдена.")
        return

    # Выполнение конвертации
    converted_amount = round(amount * rate, 2)

    # Формирование и отправка сообщения с результатом конвертации
    result = f"{amount} {from_currency.upper()} = {converted_amount} {to_currency.upper()}"
    await message.reply(result)

    # Сбрасываем состояние
    await state.finish()


@dp.message_handler(commands=['cute_animals'])
@dp.message_handler(lambda message: message.text == 'Милые животные 🐶')
async def send_random_animal_image(message: types.Message):
    """
    Обрабатывает команду /cute_animals и отправляет картинку с животным.
    """
    try:
        # Получаем случайную картинку животного
        response = requests.get(f"https://api.unsplash.com/photos/random",
                                params={"query": "animal", "orientation": "portrait"},
                                headers={"Authorization": f"Client-ID {ANIMALS_API_KEY}"})
        response.raise_for_status()
        data = response.json()

        # Получаем URL и отправляем картинку пользователю
        image_url = data["urls"]["regular"]
        await bot.send_photo(message.chat.id, photo=image_url)

    except Exception as error:
        # Обрабатываем ошибки и сообщаем пользователю
        logging.exception(f'Ошибка при подключении к api.unsplash. {error}')
        await message.reply("Не удалось отправить картинку :(")


@dp.message_handler(commands=['survey'])
@dp.message_handler(lambda message: message.text == 'Опросы 📊')
async def create_poll(message: types.Message, state: FSMContext):
    """
    Обрабатывает команду /survey и запускает состояние.
    """
    # Проверяем находимся ли мы в группе
    if message.chat.type != types.ChatType.GROUP:
        await message.answer("Введите id чата, в который хотите отправить опрос:")
        await CreatePoll.chat_id.set()
    else:
        async with state.proxy() as data:
            data['chat_id'] = message.chat.id
        await message.answer("Введите название опроса:")
        await CreatePoll.poll_name.set()


@dp.message_handler(state=CreatePoll.chat_id)
async def process_chat_id(message: types.Message, state: FSMContext):
    """
    Записывает chat_id диалога для опроса.
    """
    async with state.proxy() as data:
        data['chat_id'] = message.text
    await message.answer("Введите название опроса:")
    await CreatePoll.poll_name.set()


@dp.message_handler(state=CreatePoll.poll_name)
async def process_poll_name(message: types.Message, state: FSMContext):
    """
    Записывает poll_name - Название для опроса.
    """
    async with state.proxy() as data:
        data['poll_name'] = message.text
    await message.answer("Введите варианты ответов, разделяя их знаком ';'\n(Минимальное количество вариантов 2):")
    await CreatePoll.next()


@dp.message_handler(state=CreatePoll.poll_options)
async def process_poll_options(message: types.Message, state: FSMContext):
    """
    Записывает poll_options варианты ответа на опрос.
    Если всё корректно, то отправляет опрос в диалог.
    """
    async with state.proxy() as data:
        data['poll_options'] = message.text.split(';')
        poll_name = data['poll_name']
        poll_options = data['poll_options']
    try:
        # отправляем опрос в группу
        await bot.send_poll(chat_id=data['chat_id'],
                            question=poll_name,
                            options=poll_options)
        await message.answer("Опрос успешно создан!")
    except exceptions.ChatNotFound:
        logging.exception(f'Опрос не создан: {exceptions.ChatNotFound.text}')
        await message.answer("Чат с таким номером не найден\nНе удалось отправить опрос 😢")
    except exceptions.PollMustHaveMoreOptions:
        logging.exception(f'Опрос не создан: {exceptions.PollMustHaveMoreOptions.text}')
        await message.answer("Должно быть как минимум 2 варианта ответа\nНе удалось создать опрос 😢")
    except exceptions.PollCantHaveMoreOptions:
        logging.exception(f'Опрос не создан: {exceptions.PollCantHaveMoreOptions.text}')
        await message.answer("В опросе может быть не больше 10 вариантов ответа\nНе удалось создать опрос 😢")
    except exceptions.PollOptionsMustBeNonEmpty:
        logging.exception(f'Опрос не создан: {exceptions.PollOptionsMustBeNonEmpty.text}')
        await message.answer("Вариант ответа не может быть пустым\nНе удалось создать опрос 😢")

    await state.finish()


if __name__ == '__main__':
    # Запускаем бота
    executor.start_polling(dp, skip_updates=True)
