from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

QUEUES = None

DEFAULT_RESULT_TTL = None


def conf_settings():
    global QUEUES

    global DEFAULT_RESULT_TTL
    QUEUES = getattr(settings, 'RQ_QUEUES', None)
    if QUEUES is None:
        raise ImproperlyConfigured("You have to define RQ_QUEUES in settings.py")

    # All queues in list format, so we can get them by index, includes failed queues

    DEFAULT_RESULT_TTL = getattr(settings, 'RQ_DEFAULT_RESULT_TTL', None)  # noqa: F841


conf_settings()
