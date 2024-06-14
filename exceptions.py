"""Пользовательские исключения."""


class CanSendMessageError(Exception):
    """Ошибка, о которой можно отправить сообщение."""


class NoSendMessageError(Exception):
    """Не удается отправить сообщение."""
