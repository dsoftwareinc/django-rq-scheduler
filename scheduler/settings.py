from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from scheduler.queues import logger

QUEUES = None
SCHEDULER = None


def conf_settings():
    global QUEUES
    global SCHEDULER

    QUEUES = getattr(settings, 'SCHEDULER_QUEUES', None)
    if QUEUES is None:
        logger.warning('Configuration using RQ_QUEUES is deprecated. Use SCHEDULER_QUEUES instead')
        QUEUES = getattr(settings, 'RQ_QUEUES', None)
    if QUEUES is None:
        raise ImproperlyConfigured("You have to define RQ_QUEUES in settings.py")

    SCHEDULER = {
        'EXECUTIONS_IN_PAGE': 20,
        'DEFAULT_RESULT_TTL': 600,  # 10 minutes
        'DEFAULT_TIMEOUT': 300,  # 5 minutes
    }
    user_settings = getattr(settings, 'SCHEDULER', {})
    SCHEDULER.update(user_settings)


conf_settings()
