from operator import itemgetter

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

QUEUES = None
QUEUES_LIST = []
DEFAULT_RESULT_TTL = None


def conf_settings():
    global QUEUES
    global QUEUES_LIST
    global DEFAULT_RESULT_TTL
    QUEUES = getattr(settings, 'RQ_QUEUES', None)
    if QUEUES is None:
        raise ImproperlyConfigured("You have to define RQ_QUEUES in settings.py")

    # All queues in list format, so we can get them by index, includes failed queues

    for key, value in sorted(QUEUES.items(), key=itemgetter(0)):
        QUEUES_LIST.append({'name': key, 'connection_config': value})

    DEFAULT_RESULT_TTL = getattr(settings, 'SCHEDULER_DEFAULT_RESULT_TTL', None)  # noqa: F841


conf_settings()
