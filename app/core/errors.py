"""Application errors that can be mapped to stable HTTP problem responses."""


class ApplicationError(Exception):
    """Known application failure with an API-safe representation."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class BadRequestError(ApplicationError):
    """A request is syntactically valid but violates an application rule."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=400,
            code=code,
            message=message,
            details=details,
        )


class NotFoundError(ApplicationError):
    """A requested domain resource does not exist."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            status_code=404,
            code=code,
            message=message,
            details=details,
        )
