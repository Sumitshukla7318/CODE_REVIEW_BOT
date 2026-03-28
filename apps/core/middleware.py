import logging
import time

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """
    Logs all incoming requests with method, path, status, and duration.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        response = self.get_response(request)

        duration = time.time() - start_time
        duration_ms = round(duration * 1000, 2)

        logger.info(
            f"{request.method} {request.path} "
            f"status={response.status_code} "
            f"duration={duration_ms}ms "
            f"user={getattr(request.user, 'email', 'anonymous')}"
        )

        return response