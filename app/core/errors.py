"""Application errors that can be mapped to stable HTTP problem responses."""


class ApplicationError(Exception):
    """Known application failure with an API-safe representation."""

    status_code: int

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class BadRequestError(ApplicationError):
    """A request is syntactically valid but violates an application rule."""

    status_code = 400


class NotFoundError(ApplicationError):
    """A requested domain resource does not exist."""

    status_code = 404


class ConflictError(ApplicationError):
    """A valid request conflicts with current persisted state."""

    status_code = 409
