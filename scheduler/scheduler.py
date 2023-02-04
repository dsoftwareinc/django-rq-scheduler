import os
import threading
import traceback

import django_rq
from django.conf import settings
from rq.scheduler import RQScheduler


class DjangoRQScheduler(RQScheduler):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DjangoRQScheduler, cls).__new__(cls)
        return cls._instance

    def __init__(self, *args, **kwargs):
        self.thread = None
        queues = settings.RQ_QUEUES.keys()
        redis_conn = django_rq.get_connection()
        super(DjangoRQScheduler, self).__init__(queues, redis_conn, *args, **kwargs)

    def _install_signal_handlers(self):
        return None

    def start(self):
        self.thread = threading.Thread(target=run, args=(self,), name='Scheduler')
        self.thread.start()
        return self.thread


def run(scheduler):
    scheduler.log.info("Scheduler for %s started with PID %s",
                       ','.join(scheduler._queue_names), os.getpid())
    try:
        scheduler.work()
    except Exception as e:  # noqa
        scheduler.log.error(
            'Scheduler [PID %s] raised an exception.\n%s',
            os.getpid(), traceback.format_exc()
        )
        raise
    scheduler.log.info("Scheduler with PID %s has stopped", os.getpid())
