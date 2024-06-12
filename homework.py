"""Бот для Telegram, проверяющий статус домашних заданий."""

import logging
import os
import requests  # type: ignore
import sys
import time

from dotenv import load_dotenv
from telebot import TeleBot  # type: ignore

from exceptions import WrongStatusError, NoHomeworkNameError, WrongAnswerError

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
    message = ''
    if not PRACTICUM_TOKEN:
        message = 'PRACTICUM_TOKEN'
    elif not TELEGRAM_TOKEN:
        message = 'TELEGRAM_TOKEN'
    elif not TELEGRAM_CHAT_ID:
        message = 'TELEGRAM_CHAT_ID'
    if message:
        logger.critical(
            f'Отсутствует обязательная переменная окружения: '
            f'{message}\nПрограмма принудительно остановлена.'
        )
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(
            f'Не удалось отправить сообщение. Ошибка: {error}', exc_info=True
        )
    else:
        logger.debug(f'Бот отправил сообщение "{message}"')


def get_api_answer(timestamp):
    """Получить ответ от API."""
    params = {'from_date': timestamp}
    message = ''
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        message = (f'Сбой в работе программы: Ошибка {error}')
        logger.error(message, exc_info=True)
    else:
        status = response.status_code
        if status == 400:
            message = ('Сбой в работе программы: Код ответа API: 400\n'
                       'Неверный формат даты')
            logger.error(message)
        elif status == 401:
            message = ('Сбой в работе программы: Код ответа API: 401\n'
                       'Учетные данные не были предоставлены')
            logger.error(message)
        elif status == 404:
            message = (f'Сбой в работе программы:\nЭндпоинт {ENDPOINT} '
                       'недоступен. Код ответа API: 404')
            logger.error(message)
        elif status != 200:
            message = (f'Сбой в работе программы: Код ответа API: {status}')
            logger.error(message)
    if message:
        raise WrongAnswerError(message)
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
    elif not isinstance(response['homeworks'], list):
        message = ('Неверный тип данных homeworks: '
                   f'{type(response["homeworks"])}')
        logger.error(message)
        send_message(message)
        raise TypeError(message)
    else:
        return True


def parse_status(homework):
    """Парсит статус одной домашней работы."""
    message = ''
    if 'status' not in homework:
        message = 'Нет статуса у домашней работы.'
        raise WrongStatusError(message)
    if 'homework_name' not in homework:
        message = 'Нет имени у домашней работы.'
        raise NoHomeworkNameError(message)
    homework_name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        message = f'Неизвестный статус работы: {status}'
        raise WrongStatusError(message)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()

    try:
        bot = TeleBot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logger.critical(
            f'Не удалось подключить бота {TELEGRAM_TOKEN}\n'
            f'Ошибка {error}\n'
            'Программа принудительно остановлена.', exc_info=True
        )
        exit()

    # Флаг, что сообщение об ошибке уже отсылалось.
    already_sent = False

    timestamp = 0

    while True:
        message = ''
        try:
            response = get_api_answer(timestamp)
            if check_response(response):
                timestamp = response['current_date']
                homeworks = response['homeworks']
                if not homeworks:
                    logger.debug('Нет новых статусов')
                else:
                    for homework in homeworks:
                        status = parse_status(homework)
                        if status:
                            logger.debug(status)
                            send_message(bot,
                                         HOMEWORK_VERDICTS[homework['status']])
        except (WrongAnswerError, NoHomeworkNameError,
                WrongStatusError) as error:
            message = error.message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
        if message:
            logger.error(message)
            if not already_sent:
                send_message(bot, message)
                already_sent = True
        else:
            already_sent = False
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
