from django.conf import settings
from rq.decorators import job as _rq_job

from .queues import get_queue


def job(func_or_queue, connection=None, *args, **kwargs):
    """
    The same as rq package's job decorator, but it automatically works out
    the ``connection`` argument from RQ_QUEUES.

    And also, it allows simplified ``@job`` syntax to put job into
    default queue.

    """
    if callable(func_or_queue):
        func = func_or_queue
        queue = 'default'
    else:
        func = None
        queue = func_or_queue

    if isinstance(queue, str):
        try:
            queue = get_queue(queue)
            if connection is None:
                connection = queue.connection
        except KeyError:
            pass

    config = getattr(settings, 'SCHEDULER', {})
    default_result_ttl = config.get('DEFAULT_RESULT_TTL')
    kwargs.setdefault('result_ttl', default_result_ttl)

    default_timeout = config.get('DEFAULT_TIMEOUT')
    kwargs.setdefault('timeout', default_timeout)

    decorator = _rq_job(queue, connection=connection, *args, **kwargs)
    if func:
        return decorator(func)
    return decorator
