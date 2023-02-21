import os
import threading
import traceback

import django_rq
from django.conf import settings
from rq.scheduler import RQScheduler

from scheduler import logger


class StopThreadException(Exception):
    pass


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

    @classmethod
    def instance(cls):
        return cls._instance

    def _install_signal_handlers(self):
        return None

    def stop(self, *args, **kwargs):
        pass

    def start(self):
        if self.thread is not None and self.thread.is_alive():
            return self.thread
        logger.info(f'Starting scheduler thread with interval {self.interval}')
        self.thread = threading.Thread(target=run, args=(self,), name='Scheduler', daemon=True)

        self.thread.start()
        return self.thread

    def work(self):
        super(DjangoRQScheduler, self).work()
        self.thread = None


def run(scheduler):
    logger.info("Scheduler for %s started with PID %s", ','.join(scheduler._queue_names), os.getpid())
    try:
        scheduler.work()
    except Exception as e:  # noqa
        logger.error(f'Scheduler [PID {os.getpid()}] raised an exception.\n{traceback.format_exc()}')
        raise
    logger.info("Scheduler with PID %s has stopped", os.getpid())
