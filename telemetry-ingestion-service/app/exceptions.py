class AppError(Exception):
    """Base application error for telemetry service domain failures."""


class NotFoundError(AppError):
    pass


class ValidationError(AppError):
    pass


class ConflictError(AppError):
    pass


class DependencyError(AppError):
    pass


class PersistenceError(AppError):
    pass
