from django.test import TestCase
from scheduler.models import CronJob
from scheduler.admin import CronJobAdmin
from .testtools import job_factory
from django.contrib.admin.sites import AdminSite
from unittest.mock import Mock, patch
from django_rq import get_queue
from scheduler.scheduler import DjangoRQScheduler


class EnqueueJobNowTestCase(TestCase):
    def setUp(self):
        self.admin = CronJobAdmin(CronJob, AdminSite())
        self.scheduler = DjangoRQScheduler.instance()
        self.job = job_factory(CronJob, enabled=False)
        self.job.unschedule()
        self.job.save()

    def test_schedule_job_now_enqueues_job_at(self):
        request = Mock()
        cron_jobs = CronJob.objects.filter(id=self.job.id)
        cron_job = cron_jobs.first()
        self.assertIsNotNone(cron_jobs)
        queue = get_queue(cron_job.queue)
        self.admin.schedule_job_now(request, cron_jobs)
        self.scheduler.enqueue_scheduled_jobs()
        cron_job.refresh_from_db()
        self.assertIsNotNone(cron_job)
        self.assertTrue(cron_job.job_id in queue.get_job_ids())

    @patch.object(CronJobAdmin, 'message_user')
    def test_run_job_now_returns_message(self, mock_message_user):
        request = Mock()
        self.admin.schedule_job_now(request, CronJob.objects.filter(id=self.job.id))
        mock_message_user.assert_called_once_with(request, f'The following jobs have been enqueued: {self.job.name}')


# class RunJobNowTestCase(TestCase):
#     def setUp(self):
#         self.job = job_factory(CronJob, enabled=False)
#         self.job.unschedule()
#         self.job.save()
#         self.admin = CronJobAdmin(CronJob, AdminSite())

#     def test_run_job_now_enqueues_job(self):
#         request = Mock()
#         queue = get_queue(self.job.queue)
#         initial_queue_len = len(queue)
#         self.admin.run_job_now(request, CronJob.objects.filter(id=self.job.id))
#         self.assertEqual(len(queue), initial_queue_len + 1)
#         self.assertEqual(self.job.is_scheduled(), False)

#     @patch.object(CronJobAdmin, 'message_user')
#     def test_run_job_now_returns_message(self, mock_message_user):
#         request = Mock()
#         self.admin.run_job_now(request, CronJob.objects.filter(id=self.job.id))
#         mock_message_user.assert_called_once_with(request, f'The following jobs have been run: {self.job.name}')
