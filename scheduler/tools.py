import importlib

import croniter
from django.apps import apps
from django.conf import settings
from django.utils import timezone
from django_rq import job

from scheduler import logger
from scheduler.scheduler import DjangoRQScheduler

MODEL_NAMES = ['ScheduledJob', 'RepeatableJob', 'CronJob']


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
    logger.debug("Rescheduling all jobs")
    for model_name in MODEL_NAMES:
        model = apps.get_model(app_label='scheduler', model_name=model_name)
        enabled_jobs = model.objects.filter(enabled=True)
        unscheduled_jobs = filter(lambda j: not j.is_scheduled(), enabled_jobs)
        for item in unscheduled_jobs:
            logger.debug(f"Rescheduling {str(item)}")
            item.save()


def start_scheduler_thread():
    start_scheduler_as_thread = getattr(settings, 'SCHEDULER_THREAD', True)
    if not start_scheduler_as_thread:
        logger.info("Scheduler thread is turned off in the project settings")
        logger.info("Make sure a scheduler is running")
        return
    if start_scheduler_as_thread:
        interval = getattr(settings, 'SCHEDULER_INTERVAL', 60)
        interval = max(1, interval)
        if interval < 10:
            logger.warn(
                f"SCHEDULER_INTERVAL is set to {interval} - "
                f"it is not recommended to have the interval less than 10 seconds")
        scheduler = DjangoRQScheduler(interval=interval)
        scheduler.start()


def run_job(job_model: str, job_id: int):
    """Run a job
    """
    if job_model not in MODEL_NAMES:
        raise ValueError(f'Job Model {job_model} does not exist, choices are {MODEL_NAMES}')
    model = apps.get_model(app_label='scheduler', model_name=job_model)
    job = model.objects.filter(id=job_id).first()
    if job is None:
        raise ValueError(f'Job {job_model}:{job_id} does not exit')
    logger.debug(f'Running job {str(job)}')
    args = job.parse_args()
    kwargs = job.parse_kwargs()
    res = job.callable_func()(*args, **kwargs)
    return res
