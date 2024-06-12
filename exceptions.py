"""Пользовательские исключения."""


class WrongStatusError(Exception):
    """Недокументированный статус"""


class NoHomeworkNameError(Exception):
    """Нет ключа homework_name в статусе."""


class WrongAnswerError(Exception):
    """Неверный ответ сервера."""
