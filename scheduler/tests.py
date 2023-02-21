# -*- coding: utf-8 -*-
import time
import zoneinfo
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_rq import job as jobdecorator
from django_rq.queues import get_queue

from scheduler import tools
from scheduler.models import BaseJob, CronJob, JobArg, JobKwarg, RepeatableJob, ScheduledJob
from scheduler.scheduler import DjangoRQScheduler
from scheduler.tools import run_job


# RQ
# Configuration to pretend there is a Redis service available.
# Set up the connection before RQ Django reads the settings.
# The connection must be the same because in fakeredis connections
# do not share the state. Therefore, we define a singleton object to reuse it.
def sequence():
    n = 1
    while True:
        yield n
        n += 1


def job_instance(cls, **kwargs):
    values = dict(
        name='Scheduled Job %d' % next(sequence()),
        job_id=None,
        queue=list(settings.RQ_QUEUES.keys())[0],
        callable='scheduler.tests.test_job',
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


def jobarg_instance(cls, **kwargs):
    content_object = kwargs.pop('content_object', None)
    if content_object is None:
        content_object = job_instance(ScheduledJob)
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


@jobdecorator
def test_job():
    return 1 + 1


@jobdecorator
def test_args_kwargs(*args, **kwargs):
    func = "test_args_kwargs({})"
    args_list = [repr(arg) for arg in args]
    kwargs_list = [f'{k}={v}' for (k, v) in kwargs.items()]
    return func.format(', '.join(args_list + kwargs_list))


test_non_callable = 'I am a teapot'


def _get_job_from_queue(django_job):
    queue = django_job.get_rqueue()
    jobs_to_schedule = queue.scheduled_job_registry.get_job_ids()
    entry = next(i for i in jobs_to_schedule if i == django_job.job_id)
    return queue.fetch_job(entry)


class BaseTestCases:
    class TestBaseJob(TestCase):
        JobClass = BaseJob

        @classmethod
        def setUpTestData(cls) -> None:
            try:
                User.objects.create_superuser('admin', 'admin@a.com', 'admin')
            except Exception:
                pass
            cls.client = Client()

        def test_callable_func(self):
            job = self.JobClass()
            job.callable = 'scheduler.tests.test_job'
            func = job.callable_func()
            self.assertEqual(test_job, func)

        def test_callable_func_not_callable(self):
            job = self.JobClass()
            job.callable = 'scheduler.tests.test_non_callable'
            with self.assertRaises(TypeError):
                job.callable_func()

        def test_clean_callable(self):
            job = self.JobClass()
            job.callable = 'scheduler.tests.test_job'
            self.assertIsNone(job.clean_callable())

        def test_clean_callable_invalid(self):
            job = self.JobClass()
            job.callable = 'scheduler.tests.test_non_callable'
            with self.assertRaises(ValidationError):
                job.clean_callable()

        def test_clean_queue(self):
            for queue in settings.RQ_QUEUES.keys():
                job = self.JobClass()
                job.queue = queue
                self.assertIsNone(job.clean_queue())

        def test_clean_queue_invalid(self):
            job = self.JobClass()
            job.queue = 'xxxxxx'
            job.callable = 'scheduler.tests.test_job'
            with self.assertRaises(ValidationError):
                job.clean()

        # next 2 check the above are included in job.clean() function
        def test_clean(self):
            job = self.JobClass()
            job.queue = list(settings.RQ_QUEUES)[0]
            job.callable = 'scheduler.tests.test_job'
            self.assertIsNone(job.clean())

        def test_clean_invalid_callable(self):
            job = self.JobClass()
            job.queue = list(settings.RQ_QUEUES)[0]
            job.callable = 'scheduler.tests.test_non_callable'
            with self.assertRaises(ValidationError):
                job.clean()

        def test_clean_invalid_queue(self):
            job = self.JobClass()
            job.queue = 'xxxxxx'
            job.callable = 'scheduler.tests.test_job'
            with self.assertRaises(ValidationError):
                job.clean()

        def test_is_schedulable_already_scheduled(self):
            job = job_instance(self.JobClass, )
            job.schedule()
            self.assertFalse(job.is_schedulable())

        def test_is_schedulable_disabled(self):
            job = self.JobClass()
            job.enabled = False
            self.assertFalse(job.is_schedulable())

        def test_is_schedulable_enabled(self):
            job = self.JobClass()
            job.enabled = True
            self.assertTrue(job.is_schedulable())

        def test_schedule(self):
            job = job_instance(self.JobClass, )
            self.assertTrue(job.is_scheduled())
            self.assertIsNotNone(job.job_id)

        def test_unschedulable(self):
            job = job_instance(self.JobClass, enabled=False)
            self.assertFalse(job.is_scheduled())
            self.assertIsNone(job.job_id)

        def test_unschedule(self):
            job = job_instance(self.JobClass, )
            self.assertTrue(job.unschedule())
            self.assertIsNone(job.job_id)

        def test_unschedule_not_scheduled(self):
            job = job_instance(self.JobClass, enabled=False)
            self.assertTrue(job.unschedule())
            self.assertIsNone(job.job_id)

        def test_save_enabled(self):
            job = job_instance(self.JobClass, )
            job.save()
            self.assertIsNotNone(job.job_id)

        def test_save_disabled(self):
            job = job_instance(self.JobClass, enabled=False)
            job.save()
            self.assertIsNone(job.job_id)

        def test_save_and_schedule(self):
            job = job_instance(self.JobClass, )
            self.assertIsNotNone(job.job_id)
            self.assertTrue(job.is_scheduled())

        def test_schedule2(self):
            job = self.JobClass()
            job.queue = list(settings.RQ_QUEUES)[0]
            job.enabled = False
            job.scheduled_time = timezone.now() + timedelta(minutes=1)
            self.assertFalse(job.schedule())

        def test_delete_and_unschedule(self):
            job = job_instance(self.JobClass, )
            self.assertIsNotNone(job.job_id)
            self.assertTrue(job.is_scheduled())
            job.delete()
            self.assertFalse(job.is_scheduled())

        def test_job_create(self):
            prev_count = self.JobClass.objects.count()
            job_instance(self.JobClass)
            self.assertEqual(self.JobClass.objects.count(), prev_count + 1)

        def test_str(self):
            name = "test"
            job = job_instance(self.JobClass, name=name)
            self.assertEqual(f'{self.JobClass.__name__}[{name}={job.callable}()]', str(job))

        def test_callable_passthrough(self):
            job = job_instance(self.JobClass)
            entry = _get_job_from_queue(job)
            self.assertEqual(entry.func, run_job)
            job_model, job_id = entry.args
            self.assertEqual(job_model, self.JobClass.__name__)
            self.assertEqual(job_id, job.id)

        def test_timeout_passthrough(self):
            job = job_instance(self.JobClass, timeout=500)
            entry = _get_job_from_queue(job)
            self.assertEqual(entry.timeout, 500)

        def test_at_front_passthrough(self):
            job = job_instance(self.JobClass, at_front=True)
            queue = job.get_rqueue()
            jobs_to_schedule = queue.scheduled_job_registry.get_job_ids()
            self.assertIn(job.job_id, jobs_to_schedule)

        def test_callable_result(self):
            job = job_instance(self.JobClass, )
            entry = _get_job_from_queue(job)
            self.assertEqual(entry.perform(), 2)

        def test_callable_empty_args_and_kwargs(self):
            job = job_instance(self.JobClass, callable='scheduler.tests.test_args_kwargs')
            entry = _get_job_from_queue(job)
            self.assertEqual(entry.perform(), 'test_args_kwargs()')

        def test_delete_args(self):
            job = job_instance(self.JobClass, )
            arg = jobarg_instance(JobArg, val='one', content_object=job)
            self.assertEqual(1, job.callable_args.count())
            arg.delete()
            self.assertEqual(0, job.callable_args.count())

        def test_delete_kwargs(self):
            job = job_instance(self.JobClass, )
            kwarg = jobarg_instance(JobKwarg, key='key1', arg_type='str', val='one', content_object=job)
            self.assertEqual(1, job.callable_kwargs.count())
            kwarg.delete()
            self.assertEqual(0, job.callable_kwargs.count())

        def test_parse_args(self):
            job = job_instance(self.JobClass, )
            date = timezone.now()
            jobarg_instance(JobArg, val='one', content_object=job)
            jobarg_instance(JobArg, arg_type='int', val=2, content_object=job)
            jobarg_instance(JobArg, arg_type='bool', val=True, content_object=job)
            jobarg_instance(JobArg, arg_type='bool', val=False, content_object=job)
            jobarg_instance(JobArg, arg_type='datetime', val=date, content_object=job)
            self.assertEqual(job.parse_args(), ['one', 2, True, False, date])

        def test_parse_kwargs(self):
            job = job_instance(self.JobClass, )
            date = timezone.now()
            jobarg_instance(JobKwarg, key='key1', arg_type='str', val='one', content_object=job)
            jobarg_instance(JobKwarg, key='key2', arg_type='int', val=2, content_object=job)
            jobarg_instance(JobKwarg, key='key3', arg_type='bool', val=True, content_object=job)
            jobarg_instance(JobKwarg, key='key4', arg_type='datetime', val=date, content_object=job)
            kwargs = job.parse_kwargs()
            self.assertEqual(kwargs, dict(key1='one', key2=2, key3=True, key4=date))

        def test_callable_args_and_kwargs(self):
            job = job_instance(self.JobClass, callable='scheduler.tests.test_args_kwargs')
            date = timezone.now()
            jobarg_instance(JobArg, arg_type='str', val='one', content_object=job)
            jobarg_instance(JobKwarg, key='key1', arg_type='int', val=2, content_object=job)
            jobarg_instance(JobKwarg, key='key2', arg_type='datetime', val=date, content_object=job)
            jobarg_instance(JobKwarg, key='key3', arg_type='bool', val=False, content_object=job)
            job.save()
            entry = _get_job_from_queue(job)
            self.assertEqual(entry.perform(),
                             "test_args_kwargs('one', key1=2, key2={}, key3=False)".format(date))

        def test_function_string(self):
            job = job_instance(self.JobClass, )
            date = timezone.now()
            jobarg_instance(JobArg, arg_type='str', val='one', content_object=job)
            jobarg_instance(JobArg, arg_type='int', val='1', content_object=job)
            jobarg_instance(JobArg, arg_type='datetime', val=date, content_object=job)
            jobarg_instance(JobArg, arg_type='bool', val=True, content_object=job)
            jobarg_instance(JobKwarg, key='key1', arg_type='str', val='one', content_object=job)
            jobarg_instance(JobKwarg, key='key2', arg_type='int', val=2, content_object=job)
            jobarg_instance(JobKwarg, key='key3', arg_type='datetime', val=date, content_object=job)
            jobarg_instance(JobKwarg, key='key4', arg_type='bool', val=False, content_object=job)
            self.assertEqual(job.function_string(),
                             ("scheduler.tests.test_job(\u200b'one', 1, {date}, True, " +
                              "key1='one', key2=2, key3={date}, key4=False)").format(date=repr(date)))

        def test_admin_list_view(self):
            # arrange
            self.client.login(username='admin', password='admin')
            job = job_instance(self.JobClass, )
            model = job._meta.model.__name__.lower()
            url = reverse(f'admin:scheduler_{model}_changelist')
            # act
            res = self.client.get(url)
            # assert
            self.assertEqual(200, res.status_code)

        def test_admin_list_view_delete_model(self):
            # arrange
            self.client.login(username='admin', password='admin')
            job = job_instance(self.JobClass, )
            job.save()
            model = job._meta.model.__name__.lower()
            url = reverse(f'admin:scheduler_{model}_changelist')
            # act
            res = self.client.post(url, data={
                'action': 'delete_model',
                '_selected_action': [job.pk, ],
            })
            # assert
            self.assertEqual(302, res.status_code)

        def test_admin_single_view(self):
            # arrange
            self.client.login(username='admin', password='admin')
            job = job_instance(self.JobClass, )
            job.save()
            model = job._meta.model.__name__.lower()
            url = reverse(f'admin:scheduler_{model}_change', args=[job.pk, ])
            # act
            res = self.client.get(url)
            # assert
            self.assertEqual(200, res.status_code)

        def test_admin_single_delete(self):
            # arrange
            self.client.login(username='admin', password='admin')
            job = job_instance(self.JobClass, )
            job.save()
            model = job._meta.model.__name__.lower()
            url = reverse(f'admin:scheduler_{model}_delete', args=[job.pk, ])
            # act
            res = self.client.post(url)
            # assert
            self.assertEqual(200, res.status_code)

        def test_admin_run_job_now(self):
            # arrange
            self.client.login(username='admin', password='admin')
            job = job_instance(self.JobClass, )
            job.save()
            data = {
                'action': 'run_job_now',
                '_selected_action': [job.id, ],
            }
            model = job._meta.model.__name__.lower()
            url = reverse(f'admin:scheduler_{model}_changelist')
            # act
            res = self.client.post(url, data=data, follow=True)
            # assert
            entry = _get_job_from_queue(job)
            job_model, job_id = entry.args
            self.assertEqual(job_model, self.JobClass.__name__)
            self.assertEqual(job_id, job.id)
            self.assertEqual(200, res.status_code)

        def test_admin_enable_job(self):
            # arrange
            self.client.login(username='admin', password='admin')
            job = job_instance(self.JobClass, enabled=False)
            job.save()
            data = {
                'action': 'enable_selected',
                '_selected_action': [job.id, ],
            }
            model = job._meta.model.__name__.lower()
            url = reverse(f'admin:scheduler_{model}_changelist')
            # act
            res = self.client.post(url, data=data, follow=True)
            # assert
            self.assertEqual(200, res.status_code)
            job = self.JobClass.objects.filter(id=job.id).first()
            self.assertTrue(job.enabled)

        def test_admin_disable_job(self):
            # arrange
            self.client.login(username='admin', password='admin')
            job = job_instance(self.JobClass, enabled=True)
            job.save()
            data = {
                'action': 'disable_selected',
                '_selected_action': [job.id, ],
            }
            model = job._meta.model.__name__.lower()
            url = reverse(f'admin:scheduler_{model}_changelist')
            # act
            res = self.client.post(url, data=data, follow=True)
            # assert
            self.assertEqual(200, res.status_code)
            job = self.JobClass.objects.filter(id=job.id).first()
            self.assertFalse(job.enabled)

    class TestSchedulableJob(TestBaseJob):
        # Currently ScheduledJob and RepeatableJob
        JobClass = ScheduledJob

        def test_schedule_time_utc(self):
            job = self.JobClass()
            est = zoneinfo.ZoneInfo('US/Eastern')
            scheduled_time = datetime(2016, 12, 25, 8, 0, 0, tzinfo=est)
            job.scheduled_time = scheduled_time
            utc = zoneinfo.ZoneInfo('UTC')
            expected = scheduled_time.astimezone(utc).isoformat()
            self.assertEqual(expected, job.schedule_time_utc().isoformat())

        def test_result_ttl_passthrough(self):
            job = job_instance(self.JobClass, result_ttl=500)
            entry = _get_job_from_queue(job)
            self.assertEqual(entry.result_ttl, 500)


class TestAllJobArg(TestCase):
    JobArgClass = JobArg

    def test_clean_one_value_invalid_str_int(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='int', val='not blank', )
        with self.assertRaises(ValidationError):
            arg.clean()

    def test_clean_invalid(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='int', val='str')
        with self.assertRaises(ValidationError):
            arg.clean()

    def test_clean(self):
        arg = jobarg_instance(self.JobArgClass, val='something')
        self.assertIsNone(arg.clean())


class TestJobArg(TestCase):
    JobArgClass = JobArg

    def test_value(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='str', val='something')
        self.assertEqual(arg.value(), 'something')

    def test__str__str_val(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='str', val='something')
        self.assertEqual('something', str(arg.value()))

    def test__str__int_val(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='int', val='1')
        self.assertEqual('1', str(arg.value()))

    def test__str__datetime_val(self):
        _time = timezone.now()
        arg = jobarg_instance(self.JobArgClass, arg_type='datetime', val=str(_time))
        self.assertEqual(str(_time), str(arg.value()))

    def test__str__bool_val(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='bool', val='True')
        self.assertEqual('True', str(arg.value()))

    def test__repr__str_val(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='str', val='something')
        self.assertEqual("'something'", repr(arg.value()))

    def test__repr__int_val(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='int', val='1')
        self.assertEqual('1', repr(arg.value()))

    def test__repr__datetime_val(self):
        _time = timezone.now()
        arg = jobarg_instance(self.JobArgClass, arg_type='datetime', val=str(_time))
        self.assertEqual(repr(_time), repr(arg.value()))

    def test__repr__bool_val(self):
        arg = jobarg_instance(self.JobArgClass, arg_type='bool', val='False')
        self.assertEqual('False', repr(arg.value()))


class TestJobKwarg(TestAllJobArg):
    JobArgClass = JobKwarg

    def test_value(self):
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='str', val='value')
        self.assertEqual(kwarg.value(), ('key', 'value'))

    def test__str__str_val(self):
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='str', val='something')
        self.assertEqual("key=key value=something", str(kwarg))

    def test__str__int_val(self):
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='int', val=1)
        self.assertEqual("key=key value=1", str(kwarg))

    def test__str__datetime_val(self):
        _time = timezone.now()
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='datetime', val=str(_time))
        self.assertEqual("key=key value={}".format(_time), str(kwarg))

    def test__str__bool_val(self):
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='bool', val='True')
        self.assertEqual("key=key value=True", str(kwarg))

    def test__repr__str_val(self):
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='str', val='something')
        self.assertEqual("('key', 'something')", repr(kwarg.value()))

    def test__repr__int_val(self):
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='int', val='1')
        self.assertEqual("('key', 1)", repr(kwarg.value()))

    def test__repr__datetime_val(self):
        _time = timezone.now()
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='datetime', val=str(_time))
        self.assertEqual("('key', {})".format(repr(_time)), repr(kwarg.value()))

    def test__repr__bool_val(self):
        kwarg = jobarg_instance(self.JobArgClass, key='key', arg_type='bool', val='True')
        self.assertEqual("('key', True)", repr(kwarg.value()))


class TestScheduledJob(BaseTestCases.TestSchedulableJob):
    JobClass = ScheduledJob

    def test_clean(self):
        job = self.JobClass()
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        self.assertIsNone(job.clean())

    def test_unschedulable_old_job(self):
        job = job_instance(self.JobClass, scheduled_time=timezone.now() - timedelta(hours=1))
        self.assertFalse(job.is_scheduled())


class TestRepeatableJob(BaseTestCases.TestSchedulableJob):
    JobClass = RepeatableJob

    def test_unschedulable_old_job(self):
        job = job_instance(self.JobClass, scheduled_time=timezone.now() - timedelta(hours=1), repeat=0)
        self.assertFalse(job.is_scheduled())

    def test_schedulable_old_job_repeat_none(self):
        # If repeat is None, the job should be scheduled
        job = job_instance(self.JobClass, scheduled_time=timezone.now() - timedelta(hours=1), repeat=None)
        self.assertTrue(job.is_scheduled())

    def test_clean(self):
        job = self.JobClass()
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        job.interval = 1
        job.result_ttl = -1
        self.assertIsNone(job.clean())

    def test_clean_seconds(self):
        job = self.JobClass()
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        job.interval = 60
        job.result_ttl = -1
        job.interval_unit = 'seconds'
        self.assertIsNone(job.clean())

    def test_clean_too_frequent(self):
        job = self.JobClass()
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        job.interval = 10
        job.result_ttl = -1
        job.interval_unit = 'seconds'
        with self.assertRaises(ValidationError):
            job.clean_interval_unit()

    def test_clean_not_multiple(self):
        job = self.JobClass()
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        job.interval = 121
        job.interval_unit = 'seconds'
        with self.assertRaises(ValidationError):
            job.clean_interval_unit()

    def test_clean_short_result_ttl(self):
        job = self.JobClass()
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        job.interval = 1
        job.repeat = 1
        job.result_ttl = 3599
        job.interval_unit = 'hours'
        job.repeat = 42
        with self.assertRaises(ValidationError):
            job.clean_result_ttl()

    def test_clean_indefinite_result_ttl(self):
        job = self.JobClass()
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        job.interval = 1
        job.result_ttl = -1
        job.interval_unit = 'hours'
        job.clean_result_ttl()

    def test_clean_undefined_result_ttl(self):
        job = self.JobClass()
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        job.interval = 1
        job.interval_unit = 'hours'
        job.clean_result_ttl()

    def test_interval_seconds_weeks(self):
        job = job_instance(self.JobClass, interval=2, interval_unit='weeks')
        self.assertEqual(1209600.0, job.interval_seconds())

    def test_interval_seconds_days(self):
        job = job_instance(self.JobClass, interval=2, interval_unit='days')
        self.assertEqual(172800.0, job.interval_seconds())

    def test_interval_seconds_hours(self):
        job = job_instance(self.JobClass, interval=2, interval_unit='hours')
        self.assertEqual(7200.0, job.interval_seconds())

    def test_interval_seconds_minutes(self):
        job = job_instance(self.JobClass, interval=15, interval_unit='minutes')
        self.assertEqual(900.0, job.interval_seconds())

    def test_interval_seconds_seconds(self):
        job = RepeatableJob(interval=15, interval_unit='seconds')
        self.assertEqual(15.0, job.interval_seconds())

    def test_interval_display(self):
        job = job_instance(self.JobClass, interval=15, interval_unit='minutes')
        self.assertEqual(job.interval_display(), '15 minutes')

    def test_result_interval(self):
        job = job_instance(self.JobClass, )
        entry = _get_job_from_queue(job)
        self.assertEqual(entry.meta['interval'], 3600)

    def test_repeat(self):
        job = job_instance(self.JobClass, repeat=10)
        entry = _get_job_from_queue(job)
        self.assertEqual(entry.meta['repeat'], 10)

    def test_repeat_old_job_exhausted(self):
        base_time = timezone.now()
        job = job_instance(self.JobClass, scheduled_time=base_time - timedelta(hours=10), repeat=10)
        self.assertEqual(job.is_scheduled(), False)

    def test_repeat_old_job_last_iter(self):
        base_time = timezone.now()
        job = job_instance(self.JobClass, scheduled_time=base_time - timedelta(hours=9, minutes=30), repeat=10)
        self.assertEqual(job.repeat, 0)
        self.assertEqual(job.is_scheduled(), True)

    def test_repeat_old_job_remaining(self):
        base_time = timezone.now()
        job = job_instance(self.JobClass, scheduled_time=base_time - timedelta(minutes=30), repeat=5)
        self.assertEqual(job.repeat, 4)
        self.assertEqual(job.scheduled_time, base_time + timedelta(minutes=30))
        self.assertEqual(job.is_scheduled(), True)

    def test_repeat_none_interval_2_min(self):
        base_time = timezone.now()
        job = job_instance(self.JobClass, scheduled_time=base_time - timedelta(minutes=29), repeat=None)
        job.interval = 120
        job.interval_unit = 'seconds'
        job.schedule()
        self.assertTrue(job.scheduled_time > base_time)
        self.assertTrue(job.is_scheduled())

    @override_settings(SCHEDULER_THREAD=False)
    def test_check_rescheduled_after_execution(self):
        job = job_instance(self.JobClass, scheduled_time=timezone.now() + timedelta(seconds=1))
        queue = job.get_rqueue()
        first_run_id = job.job_id
        entry = queue.fetch_job(first_run_id)
        queue.run_sync(entry)
        job.refresh_from_db()
        self.assertTrue(job.is_scheduled())
        self.assertNotEquals(job.job_id, first_run_id)


class TestCronJob(BaseTestCases.TestBaseJob):
    JobClass = CronJob

    def test_clean(self):
        job = self.JobClass()
        job.cron_string = '* * * * *'
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        self.assertIsNone(job.clean())

    def test_clean_cron_string_invalid(self):
        job = self.JobClass()
        job.cron_string = 'not-a-cron-string'
        job.queue = list(settings.RQ_QUEUES)[0]
        job.callable = 'scheduler.tests.test_job'
        with self.assertRaises(ValidationError):
            job.clean_cron_string()

    def test_repeat(self):
        job = job_instance(self.JobClass, repeat=10)
        entry = _get_job_from_queue(job)
        self.assertEqual(entry.meta['repeat'], 10)

    def test_check_rescheduled_after_execution(self):
        job = job_instance(self.JobClass, )
        queue = job.get_rqueue()
        first_run_id = job.job_id
        entry = queue.fetch_job(first_run_id)
        queue.run_sync(entry)
        job.refresh_from_db()
        self.assertTrue(job.is_scheduled())
        self.assertNotEquals(job.job_id, first_run_id)


class TestSchedulerJob(TestCase):
    def test_scheduler_job_is_running(self):
        tools.reschedule_all_jobs()
        # assert job created
        scheduler_cron_job = CronJob.objects.filter(name='Job scheduling jobs').first()
        self.assertIsNotNone(scheduler_cron_job)

        scheduler_cron_job.unschedule()
        scheduler_cron_job.schedule()  # This should happen in ready
        queue = get_queue('default')
        jobs = queue.scheduled_job_registry.get_job_ids()
        jobs = [queue.fetch_job(job_id) for job_id in jobs]
        scheduler_job = None
        for job in jobs:
            if job.args == ('CronJob', scheduler_cron_job.id):
                scheduler_job = job
                break
        self.assertIsNotNone(scheduler_job)

        cron_job = job_instance(CronJob)
        cron_job.unschedule()
        self.assertFalse(cron_job.is_scheduled())
        cron_job.save()
        queue.run_sync(scheduler_job)
        cron_job.refresh_from_db()
        self.assertTrue(cron_job.is_scheduled())

    def test_scheduler_thread_is_running(self):
        tools.start_scheduler_thread()
        time.sleep(1)
        scheduler = DjangoRQScheduler.instance()
        self.assertIsNotNone(scheduler.thread)
        self.assertEqual(scheduler.thread.name, 'Scheduler')
        self.assertTrue(scheduler.thread.is_alive())
        scheduler.request_stop()
        scheduler.thread.join()

    @override_settings(SCHEDULER_INTERVAL=2)
    def test_scheduler_thread_is_running_interval_40(self):
        tools.start_scheduler_thread()
        scheduler = DjangoRQScheduler.instance()
        scheduler.request_stop()
        scheduler.thread.join()
        tools.start_scheduler_thread()
        self.assertEqual(scheduler.interval, 2)
        scheduler.request_stop()
        scheduler.thread.join()

    @override_settings(SCHEDULER_THREAD=False)
    def test_scheduler_process_is_not_running(self):
        scheduler = DjangoRQScheduler.instance()
        scheduler.request_stop()
        scheduler.thread.join()
        tools.start_scheduler_thread()
        assert scheduler.thread is None
