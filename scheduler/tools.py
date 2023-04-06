import importlib
import os

import croniter
import redis
from django.apps import apps
from django.utils import timezone

from scheduler.decorators import job
from scheduler.queues import get_queues, logger, get_queue
from scheduler.rq_classes import DjangoWorker

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


def get_scheduled_job(task_model: str, task_id: int):
    if task_model not in MODEL_NAMES:
        raise ValueError(f'Job Model {task_model} does not exist, choices are {MODEL_NAMES}')
    model = apps.get_model(app_label='scheduler', model_name=task_model)
    task = model.objects.filter(id=task_id).first()
    if task is None:
        raise ValueError(f'Job {task_model}:{task_id} does not exit')
    return task


def run_job(task_model: str, task_id: int):
    """Run a scheduled job
    """
    scheduled_job = get_scheduled_job(task_model, task_id)
    logger.debug(f'Running task {str(scheduled_job)}')
    args = scheduled_job.parse_args()
    kwargs = scheduled_job.parse_kwargs()
    res = scheduled_job.callable_func()(*args, **kwargs)
    return res


def create_worker(*queue_names, **kwargs):
    """
    Returns a Django worker for all queues or specified ones.
    """
    queues = get_queues(*queue_names)
    existing_workers = DjangoWorker.all(connection=queues[0].connection)
    existing_worker_names = set(map(lambda w: w.name, existing_workers))
    hostname = os.uname()[1]
    c = 1
    worker_name = f'{hostname}-worker:{c}'
    while worker_name in existing_worker_names:
        c += 1
        worker_name = f'{hostname}-worker:{c}'
    kwargs['name'] = worker_name
    worker = DjangoWorker(queues, connection=queues[0].connection, **kwargs)
    return worker


def get_job_executions(queue_name, scheduled_job):
    queue = get_queue(queue_name)
    res = list()
    try:
        job_list = queue.get_jobs()
    except redis.ConnectionError:
        return res
    res.extend(list(filter(lambda j: j.is_execution_of(scheduled_job), job_list)))
    scheduled_job_id_list = queue.scheduled_job_registry.get_job_ids()

    res.extend(list(
        map(lambda j: j.to_json(),
            filter(lambda j: j.is_execution_of(scheduled_job),
                   map(queue.fetch_job, scheduled_job_id_list)
                   ))))
    return res
