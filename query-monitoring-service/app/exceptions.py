class AppError(Exception):
    """Base application error for query monitoring service."""


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class PersistenceError(AppError):
    pass
