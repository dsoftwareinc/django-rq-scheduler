from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.utils import timezone

from scheduler.models import CronJob, JobKwarg, RepeatableJob, ScheduledJob
from scheduler.queues import get_queue


def sequence_gen():
    n = 1
    while True:
        yield n
        n += 1


seq = sequence_gen()


def job_factory(cls, instance_only=False, **kwargs):
    values = dict(
        name='Scheduled Job %d' % next(seq),
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
    if instance_only:
        instance = cls(**values)
    else:
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
        values['key'] = 'key%d' % next(seq),
    values.update(kwargs)
    instance = cls.objects.create(**values)
    return instance


def _get_job_from_queue(django_job):
    queue = django_job._get_rqueue()
    jobs_to_schedule = queue.scheduled_job_registry.get_job_ids()
    entry = next(i for i in jobs_to_schedule if i == django_job.job_id)
    return queue.fetch_job(entry)


def _get_executions(django_job):
    queue = get_queue(django_job.queue)
    job_ids = (queue.get_job_ids()
               + queue.finished_job_registry.get_job_ids()
               + queue.scheduled_job_registry.get_job_ids()
               + queue.failed_job_registry.get_job_ids())
    return list(filter(
        lambda j: j.is_execution_of(django_job),
        map(lambda jid: queue.fetch_job(jid), job_ids)))


class SchedulerBaseCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        try:
            User.objects.create_superuser('admin', 'admin@a.com', 'admin')
        except Exception:
            pass
        cls.client = Client()

    def setUp(self) -> None:
        super(SchedulerBaseCase, self).setUp()
        queue = get_queue('default')
        queue.empty()

    def tearDown(self) -> None:
        super(SchedulerBaseCase, self).setUp()
        queue = get_queue('default')
        queue.empty()

    @classmethod
    def setUpClass(cls):
        super(SchedulerBaseCase, cls).setUpClass()
        queue = get_queue('default')
        queue.connection.flushall()
