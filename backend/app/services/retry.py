from collections.abc import Awaitable, Callable

from app.observability.metrics import ERROR_COUNT, RETRY_COUNT


class RetryableOperationError(Exception):
    def __init__(self, message: str, *, error_category: str = "transient") -> None:
        super().__init__(message)
        self.error_category = error_category


async def retry_async(
    *,
    operation: str,
    max_attempts: int,
    call: Callable[[], Awaitable],
) -> object:
    attempt = 0
    while True:
        attempt += 1
        try:
            return await call()
        except Exception as exc:
            error_category = getattr(exc, "error_category", "unknown")
            if attempt >= max_attempts:
                ERROR_COUNT.labels(stage=operation, error_category=error_category).inc()
                raise
            RETRY_COUNT.labels(operation=operation, error_category=error_category).inc()

