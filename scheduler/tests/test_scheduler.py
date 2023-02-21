import time

from django.test import TestCase, override_settings
from django_rq.queues import get_queue

from scheduler import tools
from scheduler.models import CronJob
from scheduler.scheduler import DjangoRQScheduler
from .testtools import job_factory


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

        cron_job = job_factory(CronJob)
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
