import json
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase

from scheduler.models import ScheduledJob
from scheduler.queues import get_queue
from scheduler.tests.jobs import failing_job, test_job
from scheduler.tests.testtools import job_factory


class RqworkerTestCase(TestCase):

    def test_rqworker__run_jobs(self):
        queue = get_queue('default')

        # enqueue some jobs that will fail
        jobs = []
        job_ids = []
        for _ in range(0, 3):
            job = queue.enqueue(failing_job)
            jobs.append(job)
            job_ids.append(job.id)

        # Create a worker to execute these jobs
        call_command('rqworker', 'default', burst=True)

        # check if all jobs are really failed
        for job in jobs:
            self.assertTrue(job.is_failed)


class RqstatsTest(TestCase):
    def test_rqstats__does_not_fail(self):
        call_command('rqstats', '-j')
        call_command('rqstats', '-y')
        call_command('rqstats')


class RunJobTest(TestCase):
    def test_run_job__should_schedule_job(self):
        queue = get_queue('default')
        queue.empty()
        func_name = f'{test_job.__module__}.{test_job.__name__}'
        # act
        call_command('run_job', func_name, queue='default')
        # assert
        job_list = queue.get_jobs()
        self.assertEqual(1, len(job_list))
        self.assertEqual(func_name + '()', job_list[0].get_call_string())


class ExportTest(TestCase):
    def setUp(self) -> None:
        self.tmpfile = tempfile.NamedTemporaryFile()

    def tearDown(self) -> None:
        os.remove(self.tmpfile.name)

    def test_export__should_export_job(self):
        job = job_factory(ScheduledJob, enabled=True)

        # act
        call_command('export', filename=self.tmpfile.name)
        # assert
        result = json.load(self.tmpfile)
        self.assertEqual(2, len(result))
        self.assertEqual(result[0], job.to_dict())


class ImportTest(TestCase):
    def setUp(self) -> None:
        self.tmpfile = tempfile.NamedTemporaryFile(mode='w')

    def tearDown(self) -> None:
        os.remove(self.tmpfile.name)

    def test_import__should_schedule_job(self):
        job = job_factory(ScheduledJob, instance_only=True, enabled=True)
        res = json.dumps([job.to_dict(), ])
        self.tmpfile.write(res)
        self.tmpfile.flush()
        # act
        call_command('import', filename=self.tmpfile.name)
        # assert
        self.assertEqual(1, ScheduledJob.objects.count())
        db_job = ScheduledJob.objects.first()
        attrs = ['name', 'queue', 'callable', 'enabled', 'timeout']
        for attr in attrs:
            self.assertEqual(getattr(job, attr), getattr(db_job, attr))
