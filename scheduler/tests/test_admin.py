from django.test import TestCase
from scheduler.models import CronJob
from scheduler.admin import CronJobAdmin
from .testtools import job_factory
from django.contrib.admin.sites import AdminSite
from unittest.mock import Mock, patch
from rq.registry import ScheduledJobRegistry
from django_rq import get_queue
from scheduler.scheduler import DjangoRQScheduler


class EnqueueJobNowTestCase(TestCase):
    def setUp(self):
        self.job = job_factory(CronJob)
        self.job.enabled = False
        self.job.save()
        self.admin = CronJobAdmin(CronJob, AdminSite())

    def test_enqueue_job_now_enqueues_job(self):
        request = Mock()
        queue = get_queue(self.job.queue)
        registry = ScheduledJobRegistry(queue=queue)
        initial_registry_len = len(registry)
        self.admin.enqueue_job_now(request, CronJob.objects.filter(id=self.job.id))
        scheduler = DjangoRQScheduler.instance()
        scheduler.acquire_locks()
        # Jobs created using enqueue_at is put in the ScheduledJobRegistry
        self.assertEqual(len(queue), 0)
        self.assertEqual(len(registry), initial_registry_len + 1)
        # enqueue_at set job status to "scheduled"
        self.assertTrue(self.job.is_scheduled())

        # After enqueue_scheduled_jobs() is called, the registry is empty
        # and job is enqueued
        scheduler.enqueue_scheduled_jobs()
        self.assertEqual(len(queue), 1)
        self.assertEqual(len(registry), initial_registry_len)

    @patch.object(CronJobAdmin, 'message_user')
    def test_run_job_now_returns_message(self, mock_message_user):
        request = Mock()
        self.admin.enqueue_job_now(request, CronJob.objects.filter(id=self.job.id))
        mock_message_user.assert_called_once_with(request, f'The following jobs have been enqueued: {self.job.name}')


class RunJobNowTestCase(TestCase):
    def setUp(self):
        self.job = job_factory(CronJob)
        self.job.enabled = False
        self.job.save()
        self.admin = CronJobAdmin(CronJob, AdminSite())

    def test_run_job_now_enqueues_job(self):
        request = Mock()
        queue = get_queue(self.job.queue)
        initial_queue_len = len(queue)
        self.admin.run_job_now(request, CronJob.objects.filter(id=self.job.id))
        self.assertEqual(len(queue), initial_queue_len + 1)
        self.assertEqual(self.job.is_scheduled(), True)

    @patch.object(CronJobAdmin, 'message_user')
    def test_run_job_now_returns_message(self, mock_message_user):
        request = Mock()
        self.admin.run_job_now(request, CronJob.objects.filter(id=self.job.id))
        mock_message_user.assert_called_once_with(request, f'The following jobs have been run: {self.job.name}')
