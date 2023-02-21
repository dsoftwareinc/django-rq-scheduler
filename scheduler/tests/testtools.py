from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from scheduler.models import CronJob, JobKwarg, RepeatableJob, ScheduledJob


def sequence():
    n = 1
    while True:
        yield n
        n += 1


def job_factory(cls, **kwargs):
    values = dict(
        name='Scheduled Job %d' % next(sequence()),
        job_id=None,
        queue=list(settings.RQ_QUEUES.keys())[0],
        callable='scheduler.tests.jobs.test_job',
        enabled=True,
        timeout=None)
    if cls == ScheduledJob:
        values.update(dict(
            result_ttl=None,
            scheduled_time=timezone.now() + timedelta(days=1), ))
    elif cls == RepeatableJob:
        values.update(dict(
            result_ttl=None,
            interval=1,
            interval_unit='hours',
            repeat=None,
            scheduled_time=timezone.now() + timedelta(days=1), ))
    elif cls == CronJob:
        values.update(dict(cron_string="0 0 * * *", repeat=None, ))
    values.update(kwargs)
    instance = cls.objects.create(**values)
    return instance


def jobarg_factory(cls, **kwargs):
    content_object = kwargs.pop('content_object', None)
    if content_object is None:
        content_object = job_factory(ScheduledJob)
    values = dict(
        arg_type='str',
        val='',
        object_id=content_object.id,
        content_type=ContentType.objects.get_for_model(content_object),
        content_object=content_object,
    )
    if cls == JobKwarg:
        values['key'] = 'key%d' % next(sequence()),
    values.update(kwargs)
    instance = cls.objects.create(**values)
    return instance


def _get_job_from_queue(django_job):
    queue = django_job._get_rqueue()
    jobs_to_schedule = queue.scheduled_job_registry.get_job_ids()
    entry = next(i for i in jobs_to_schedule if i == django_job.job_id)
    return queue.fetch_job(entry)
