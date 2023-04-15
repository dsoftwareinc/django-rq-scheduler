import time

from django.test import TestCase

from scheduler import job, settings
from . import test_settings  # noqa
from ..queues import get_queue


@job
def test_job():
    time.sleep(1)
    return 1 + 1


@job(timeout=1)
def test_job_timeout():
    time.sleep(1)
    return 1 + 1


@job(result_ttl=1)
def test_job_result_ttl():
    return 1 + 1


class JobDecoratorTest(TestCase):
    def setUp(self) -> None:
        get_queue('default').connection.flushall()

    def test_job_decorator_no_params(self):
        test_job.delay()

        queue = get_queue('default')
        jobs = queue.get_jobs()
        self.assertEqual(1, len(jobs))
        config = getattr(settings, 'SCHEDULER', {})
        j = jobs[0]
        self.assertEqual(j.func, test_job)
        self.assertEqual(j.result_ttl, config.get('DEFAULT_RESULT_TTL'))
        self.assertEqual(j.timeout, config.get('DEFAULT_TIMEOUT'))

    def test_job_decorator_timeout(self):
        test_job_timeout.delay()

        queue = get_queue('default')
        jobs = queue.get_jobs()
        self.assertEqual(1, len(jobs))
        config = getattr(settings, 'SCHEDULER', {})
        j = jobs[0]
        self.assertEqual(j.func, test_job_timeout)
        self.assertEqual(j.result_ttl, config.get('DEFAULT_RESULT_TTL'))
        self.assertEqual(j.timeout, 1)

    def test_job_decorator_result_ttl(self):
        test_job_result_ttl.delay()

        queue = get_queue('default')
        jobs = queue.get_jobs()
        self.assertEqual(1, len(jobs))
        config = getattr(settings, 'SCHEDULER', {})
        j = jobs[0]
        self.assertEqual(j.func, test_job_result_ttl)
        self.assertEqual(j.result_ttl, 1)
        self.assertEqual(j.timeout, config.get('DEFAULT_TIMEOUT'))
