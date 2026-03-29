class AppError(Exception):
    """Base application error for digital twin service."""


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class PersistenceError(AppError):
    pass
