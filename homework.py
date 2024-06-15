"""Бот для Telegram, проверяющий статус домашних заданий."""

import logging
import os
import requests  # type: ignore
import sys
import time
from http import HTTPStatus  # https://docs.python.org/3/library/http.html

from dotenv import load_dotenv
from telebot import TeleBot  # type: ignore
from telebot.apihelper import ApiException  # type: ignore

# Настройки времени опросов.
DURATION_IN_HOURS = 0
DURATION_IN_MINUTES = 10
DURATION_IN_SECONDS = (DURATION_IN_HOURS * 60 + DURATION_IN_MINUTES) * 60
RETRY_PERIOD = DURATION_IN_SECONDS

# Загрузка переменных окружения.
load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Настройки API.
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

# Настройки логов.
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
strfmt = '%(asctime)s [%(levelname)s] %(message)s'
datefmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter(fmt=strfmt, datefmt=datefmt)
handler.setFormatter(formatter)
logger.addHandler(handler)


class CanSendMessageError(Exception):
    """Ошибка, о которой можно отправить сообщение."""


class NoSendMessageError(Exception):
    """Ошибка, о которой не удаётся отправить сообщение."""


def check_tokens() -> None:
    """Проверка наличия необходимых переменных окружения."""
    tokens: dict = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT-ID': TELEGRAM_CHAT_ID,
    }
    flag_no_token: bool = False
    for token in tokens:
        if not tokens[token]:
            logger.critical(
                f'Отсутствует обязательная переменная окружения: '
                f'{token}\nПрограмма принудительно остановлена.'
            )
            flag_no_token = True
    if flag_no_token:
        sys.exit()


def send_message(bot, message) -> None:
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except ApiException as error:
        # Тесты не проходят, если перехватывать в другом месте.
        logger.exception(
            f'Не удалось отправить сообщение. Ошибка API: {error}')
        raise NoSendMessageError(
            f'Не удалось отправить сообщение. Ошибка: {error}') from error
    except Exception as error:
        raise NoSendMessageError(
            f'Не удалось отправить сообщение. Ошибка: {error}') from error
    else:
        logger.debug(f'Бот отправил сообщение "{message}"')


def get_api_answer(timestamp) -> dict:
    """Получить ответ от API."""
    params = {'from_date': timestamp}
    message = ''
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        message = (f'Сбой в работе программы: Ошибка {error}')
    else:
        status = response.status_code
        if status == HTTPStatus.BAD_REQUEST:
            message = ('Сбой в работе программы: Код ответа API: 400\n'
                       'Неверный формат даты')
        elif status == HTTPStatus.UNAUTHORIZED:
            message = ('Сбой в работе программы: Код ответа API: 401\n'
                       'Учетные данные не были предоставлены')
        elif status == HTTPStatus.NOT_FOUND:
            message = (f'Сбой в работе программы:\nЭндпоинт {ENDPOINT} '
                       'недоступен. Код ответа API: 404')
        elif status != HTTPStatus.OK:
            message = (f'Сбой в работе программы: Код ответа API: {status}')
    if message:
        raise CanSendMessageError(message)
    return response.json()


def check_response(response) -> None:
    """Проверка полученного ответа от API."""
    message = ''
    if not isinstance(response, dict):
        response_type = type(response)
        message = (f'Неожиданный формат ответа: {response_type}\n'
                   f'Сообщение: {response}')
        raise TypeError(message)  # Требование тестов.
    if 'homeworks' not in response:
        message = 'Ответ не содержит сведения о домашних заданиях'
    elif 'current_date' not in response:
        message = 'Ответ не содержит сведения о текущей дате'
    if message:
        raise CanSendMessageError(message)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        homeworks_type = type(homeworks)
        message = ('Неверный тип данных homeworks: '
                   f'{homeworks_type}\n Сообщение: {homeworks}')
        raise TypeError(message)


def parse_status(homework) -> str:
    """Парсит статус одной домашней работы."""
    if 'status' not in homework:
        raise CanSendMessageError('Нет статуса у домашней работы.')
    if 'homework_name' not in homework:
        raise CanSendMessageError('Нет имени у домашней работы.')
    homework_name = homework['homework_name']
    status = homework['status']
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise CanSendMessageError(f'Неизвестный статус работы: {status}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> None:
    """Основная логика работы бота."""
    check_tokens()
    try:
        bot = TeleBot(token=TELEGRAM_TOKEN)
    except Exception as error:
        logger.critical(
            f'Не удалось подключить бота {TELEGRAM_TOKEN}\n'
            f'Ошибка {error}\n'
            'Программа принудительно остановлена.', exc_info=True
        )
        return
    # Какие сообщения уже отсылались.
    already_sent: set = set()
    # Флаг, что сообщение нельзя отослать.
    cant_send = False
    timestamp = int(time.time())
    while True:
        message = ''
        try:
            response_content = get_api_answer(timestamp)
            check_response(response_content)
            timestamp = response_content['current_date']
            homeworks = response_content['homeworks']
            if not homeworks:
                logger.debug('Нет новых статусов')
            for homework in homeworks:
                status = parse_status(homework)
                logger.debug(status)
                send_message(bot, status)
        except NoSendMessageError as error:
            message = repr(error)
            cant_send = True
        except (CanSendMessageError, TypeError) as error:
            message = repr(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
        finally:
            if not message:
                already_sent = set()
                cant_send = False
            elif message not in already_sent and not cant_send:
                logger.error(message)
                send_message(bot, message)
                already_sent.add(message)
            else:
                logger.error(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
