import importlib

import croniter
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from django_rq import job

from scheduler.scheduler import DjangoRQScheduler


def callable_func(callable_str: str):
    path = callable_str.split('.')
    module = importlib.import_module('.'.join(path[:-1]))
    func = getattr(module, path[-1])
    if callable(func) is False:
        raise TypeError("'{}' is not callable".format(callable_str))
    return func


def get_next_cron_time(cron_string):
    """Calculate the next scheduled time by creating a crontab object
    with a cron string"""
    now = timezone.now()
    itr = croniter.croniter(cron_string, now)
    return itr.get_next(timezone.datetime)


@job
def reschedule_all_jobs():
    MODEL_NAMES = ['ScheduledJob', 'RepeatableJob', 'CronJob']
    for model_name in MODEL_NAMES:
        model = apps.get_model(app_label='scheduler', model_name=model_name)
        enabled_jobs = model.objects.filter(enabled=True)
        unscheduled_jobs = filter(lambda j: not j.is_scheduled(), enabled_jobs)
        for item in unscheduled_jobs:
            item.save()


def start_scheduler_thread():
    start_scheduler_as_thread = getattr(settings, 'SCHEDULER_THREAD', True)
    if start_scheduler_as_thread:
        interval = getattr(settings, 'SCHEDULER_INTERVAL', 60)
        scheduler = DjangoRQScheduler(interval=interval)
        scheduler.start()
