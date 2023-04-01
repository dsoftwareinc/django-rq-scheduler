from . import settings
from rq.decorators import job as _rq_job

from .queues import get_queue


def job(func_or_queue, connection=None, *args, **kwargs):
    """
    The same as RQ's job decorator, but it automatically works out
    the ``connection`` argument from RQ_QUEUES.

    And also, it allows simplified ``@job`` syntax to put job into
    default queue.

    If RQ.DEFAULT_RESULT_TTL setting is set, it is used as default
    for ``result_ttl`` kwarg.
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

    if settings.DEFAULT_RESULT_TTL is not None:
        kwargs.setdefault('result_ttl', settings.DEFAULT_RESULT_TTL)

    decorator = _rq_job(queue, connection=connection, *args, **kwargs)
    if func:
        return decorator(func)
    return decorator
