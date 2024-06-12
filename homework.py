"""Бот для Telegram, проверяющий статус домашних заданий."""

import logging
import os
import requests  # type: ignore
import sys
import time

from dotenv import load_dotenv
from telebot import TeleBot  # type: ignore

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Флаг, что сообщение об ошибке уже отсылалось.
ALREADY_SENT = False

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
strfmt = '%(asctime)s [%(levelname)s] %(message)s'
datefmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter(fmt=strfmt, datefmt=datefmt)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия необходимых переменных окружения."""
    for data in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        if not data:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: '
                f'{str(data.__name__)}\nПрограмма принудительно остановлена.'
                )
            return False
    return True


def send_message(message):
    """Отправка сообщения."""
    try:
        bot = create_bot()
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(
            f'Не удалось отправить сообщение. Ошибка: {error}', exc_info=True
            )
    else:
        logger.debug(f'Бот отправил сообщение "{message}"')
        return True


def get_api_answer(timestamp):
    """Получить ответ от API."""
    global ALREADY_SENT
    params = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        message = (f'Сбой в работе программы: Ошибка {error}')
        logger.error(message, exc_info=True)
        if not ALREADY_SENT:
            if send_message(message):
                ALREADY_SENT = True
    status = response.status_code
    if status == 400:
        message = ('Сбой в работе программы: Код ответа API: 400\n'
                   'Неверный формат даты')
        logger.error(message)
        if not ALREADY_SENT:
            if send_message(message):
                ALREADY_SENT = True
    elif status == 401:
        message = ('Сбой в работе программы: Код ответа API: 401\n'
                   'Учетные данные не были предоставлены')
        logger.error(message)
        if not ALREADY_SENT:
            if send_message(message):
                ALREADY_SENT = True
    elif status == 404:
        message = (f'Сбой в работе программы:\nЭндпоинт {ENDPOINT} '
                   'недоступен. Код ответа API: 404')
        logger.error(message)
        if not ALREADY_SENT:
            if send_message(message):
                ALREADY_SENT = True
    elif status != 200:
        message = (f'Сбой в работе программы: Код ответа API: {status}')
        logger.error(message)
        if not ALREADY_SENT:
            if send_message(message):
                ALREADY_SENT = True
    else:
        ALREADY_SENT = False
        return response.json()


def check_response(response):
    """Проверка полученного ответа от API."""
    message = ''
    if not response:
        return False
    if not isinstance(response, dict):
        message = (f'Неожиданный формат ответа: {type(message)}\n'
                   f'Сообщение: {message}')
    elif 'homeworks' not in response:
        message = 'Ответ не содержит сведения о домашних заданиях'
    elif 'current_date' not in response:
        message = 'Ответ не содержит сведения о текущей дате'   
    if message:
        logger.error(message)
        send_message(message)
    else:
        return True       


def parse_status(homework):
    """Парсит статус одной домашней работы."""
    message = ''
    if 'status' not in homework:
        message = 'Нет статуса у домашней работы.'
    elif homework['status'] not in HOMEWORK_VERDICTS:
        message = f'Неизвестный статус работы: {homework["status"]}'
    elif 'homework_name' not in homework:
        message = 'Нет имени у домашней работы.'
    if message:
        logger.error(message)
        send_message(message) 
    else:
        homework_name = homework['homework_name']
        verdict = HOMEWORK_VERDICTS[homework['status']] 
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    

def create_bot():
    """Создаёт бота."""
    try:
        bot = TeleBot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logger.critical(
                f'Не удалось подключить бота {TELEGRAM_TOKEN}\n'
                f'Ошибка {error}\n'
                'Программа принудительно остановлена.', exc_info=True
                )
        exit()
    return bot


def main():
    """Основная логика работы бота."""

    if not check_tokens():
        exit()

    timestamp = 0

    while True:
        try:
            response = get_api_answer(
                timestamp)
            if check_response(response):
                timestamp = response['current_date']
                homeworks = response['homeworks']
                if not homeworks:
                    logger.debug('Нет новых статусов')
                else:
                    for homework in homeworks:
                        status = parse_status(homework)
                        if status:
                            send_message(status)
            time.sleep(RETRY_PERIOD)        

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(message)


if __name__ == '__main__':
    main()
