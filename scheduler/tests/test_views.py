import uuid
from datetime import datetime
from unittest.mock import patch, PropertyMock

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from scheduler.queues import get_queue
from scheduler.tools import create_worker
from . import test_settings  # noqa
from .jobs import access_self, failing_job
from ..rq_classes import JobExecution, ExecutionStatus


class ViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('foo', password='pass')
        self.user.is_staff = True
        self.user.is_active = True
        self.user.save()
        self.client = Client()
        self.client.login(username=self.user.username, password='pass')
        get_queue('django_rq_test').connection.flushall()

    def test_jobs(self):
        """Jobs in queue are displayed properly"""
        queue = get_queue('default')
        job = queue.enqueue(access_self)
        queue_name = 'default'
        response = self.client.get(reverse('queue_jobs', args=[queue_name]))
        self.assertEqual(response.context['jobs'], [job])

    def test_job_details(self):
        """Job data is displayed properly"""
        queue = get_queue('default')
        job = queue.enqueue(access_self)

        url = reverse('job_details', args=[job.id, ])
        response = self.client.get(url)
        self.assertIn('job', response.context)
        self.assertEqual(response.context['job'], job)

        # This page shouldn't fail when job.data is corrupt
        queue.connection.hset(job.key, 'data', 'non-pickleable data')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('DeserializationError', response.content.decode())

        # Bad job-id should return 404
        url = reverse('job_details', args=['bad_job_id', ])
        response = self.client.get(url)
        self.assertEqual(404, response.status_code)

    def test_job_details_on_deleted_dependency(self):
        """Page doesn't crash even if job.dependency has been deleted"""
        queue = get_queue('default')

        job = queue.enqueue(access_self)
        second_job = queue.enqueue(access_self, depends_on=job)
        job.delete()
        url = reverse('job_details', args=[second_job.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(second_job._dependency_id, response.content.decode())

    def test_requeue_job(self):
        """
        Ensure that a failed job gets re-queued when rq_requeue_job is called
        """
        queue = get_queue('default')
        queue_name = 'default'
        job = queue.enqueue(failing_job)
        worker = create_worker('default')
        worker.work(burst=True)
        job.refresh()
        self.assertTrue(job.is_failed)
        self.client.post(reverse('queue_requeue_job', args=[queue_name, job.id]), {'requeue': 'Requeue'})
        self.assertIn(job, queue.jobs)
        job.delete()

    def test_requeue_all(self):
        """
        Ensure that re-queuing all failed job work properly
        """
        queue = get_queue('default')
        queue_name = 'default'
        queue.enqueue(failing_job)
        queue.enqueue(failing_job)
        worker = create_worker('default')
        worker.work(burst=True)

        response = self.client.get(reverse('queue_requeue_all', args=[queue_name]))
        self.assertEqual(response.context['total_jobs'], 2)
        # After requeue_all is called, jobs are enqueued
        response = self.client.post(reverse('queue_requeue_all', args=[queue_name]))
        self.assertEqual(len(queue), 2)

    def test_requeue_all_if_deleted_job(self):
        """
        Ensure that re-queuing all failed job work properly
        """
        queue = get_queue('default')
        queue_name = 'default'
        job = queue.enqueue(failing_job)
        queue.enqueue(failing_job)
        worker = create_worker('default')
        worker.work(burst=True)

        response = self.client.get(reverse('queue_requeue_all', args=[queue_name]))
        self.assertEqual(response.context['total_jobs'], 2)
        job.delete()

        # After requeue_all is called, jobs are enqueued
        response = self.client.post(reverse('queue_requeue_all', args=[queue_name]))
        self.assertEqual(len(queue), 1)

    def test_delete_job(self):
        """
        In addition to deleting job from Redis, the job id also needs to be
        deleted from Queue.
        """
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'
        job = queue.enqueue(access_self)
        self.client.post(reverse('queue_delete_job', args=[queue_name, job.id]), {'post': 'yes'})
        self.assertFalse(JobExecution.exists(job.id, connection=queue.connection))
        self.assertNotIn(job.id, queue.job_ids)

    def test_action_delete_jobs(self):
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        # enqueue some jobs
        job_ids = []
        for _ in range(0, 3):
            job = queue.enqueue(access_self)
            job_ids.append(job.id)

        # remove those jobs using view
        self.client.post(reverse('queue_actions', args=[queue_name]), {'action': 'delete', 'job_ids': job_ids})

        # check if jobs are removed
        for job_id in job_ids:
            self.assertFalse(JobExecution.exists(job_id, connection=queue.connection))
            self.assertNotIn(job_id, queue.job_ids)

    def test_enqueue_jobs(self):
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        # enqueue some jobs that depends on other
        previous_job = None
        for _ in range(0, 3):
            job = queue.enqueue(access_self, depends_on=previous_job)
            previous_job = job

        # This job is deferred
        last_job = job
        self.assertEqual(last_job.get_status(), ExecutionStatus.DEFERRED)
        self.assertIsNone(last_job.enqueued_at)

        # We want to force-enqueue this job
        self.client.post(reverse('queue_enqueue_job', args=[queue_name, last_job.id]))

        # Check that job is updated correctly
        last_job = queue.fetch_job(last_job.id)
        self.assertEqual(last_job.get_status(), ExecutionStatus.QUEUED)
        self.assertIsNotNone(last_job.enqueued_at)

    def test_action_requeue_jobs(self):
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        # enqueue some jobs that will fail
        jobs = []
        job_ids = []
        for _ in range(0, 3):
            job = queue.enqueue(failing_job)
            jobs.append(job)
            job_ids.append(job.id)

        # do those jobs = fail them
        worker = create_worker('django_rq_test')
        worker.work(burst=True)

        # check if all jobs are really failed
        for job in jobs:
            self.assertTrue(job.is_failed)

        # re-nqueue failed jobs from failed queue
        self.client.post(reverse('queue_actions', args=[queue_name]), {'action': 'requeue', 'job_ids': job_ids})

        # check if we requeue all failed jobs
        for job in jobs:
            self.assertFalse(job.is_failed)

    def test_action_stop_jobs(self):
        queue_name = 'django_rq_test'
        queue = get_queue(queue_name)

        # Enqueue some jobs
        job_ids = []
        worker = create_worker('django_rq_test')
        for _ in range(3):
            job = queue.enqueue(access_self)
            job_ids.append(job.id)
            worker.prepare_job_execution(job)

        # Check if the jobs are started
        for job_id in job_ids:
            job = JobExecution.fetch(job_id, connection=queue.connection)
            self.assertEqual(job.get_status(), ExecutionStatus.STARTED)

        # Stop those jobs using the view
        started_job_registry = queue.started_job_registry
        self.assertEqual(len(started_job_registry), len(job_ids))
        self.client.post(reverse('queue_actions', args=[queue_name]), {'action': 'stop', 'job_ids': job_ids})
        self.assertEqual(len(started_job_registry), 0)

        canceled_job_registry = queue.canceled_job_registry
        self.assertEqual(len(canceled_job_registry), len(job_ids))

        for job_id in job_ids:
            self.assertIn(job_id, canceled_job_registry)

    def test_clear_queue(self):
        """Test that the queue clear actually clears the queue."""
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'
        job = queue.enqueue(access_self)
        self.client.post(reverse('queue_clear', args=[queue_name]), {'post': 'yes'})
        self.assertFalse(JobExecution.exists(job.id, connection=queue.connection))
        self.assertNotIn(job.id, queue.job_ids)

    def test_finished_jobs(self):
        """Ensure that finished jobs page works properly."""
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        job = queue.enqueue(access_self)
        registry = queue.finished_job_registry
        registry.add(job, 2)
        response = self.client.get(reverse('queue_finished_jobs', args=[queue_name]))
        self.assertEqual(response.context['jobs'], [job])

    def test_failed_jobs(self):
        """Ensure that failed jobs page works properly."""
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        # Test that page doesn't fail when FailedJobRegistry is empty
        response = self.client.get(reverse('queue_failed_jobs', args=[queue_name]))
        self.assertEqual(response.status_code, 200)

        job = queue.enqueue(access_self)
        registry = queue.failed_job_registry
        registry.add(job, 2)
        response = self.client.get(reverse('queue_failed_jobs', args=[queue_name]))
        self.assertEqual(response.context['jobs'], [job])

    def test_scheduled_jobs(self):
        """Ensure that scheduled jobs page works properly."""
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        # Test that page doesn't fail when ScheduledJobRegistry is empty
        response = self.client.get(reverse('queue_scheduled_jobs', args=[queue_name]))
        self.assertEqual(response.status_code, 200)

        job = queue.enqueue_at(datetime.now(), access_self)
        response = self.client.get(reverse('queue_scheduled_jobs', args=[queue_name]))
        self.assertEqual(response.context['jobs'], [job])

    def test_scheduled_jobs_registry_removal(self):
        """Ensure that non-existing job is being deleted from registry by view"""
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        registry = queue.scheduled_job_registry
        job = queue.enqueue_at(datetime.now(), access_self)
        self.assertEqual(len(registry), 1)

        queue.connection.delete(job.key)
        response = self.client.get(reverse('queue_scheduled_jobs', args=[queue_name]))
        self.assertEqual(response.context['jobs'], [])

        self.assertEqual(len(registry), 0)

    def test_started_jobs(self):
        """Ensure that active jobs page works properly."""
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        job = queue.enqueue(access_self)
        registry = queue.started_job_registry
        registry.add(job, 2)
        response = self.client.get(reverse('queue_started_jobs', args=[queue_name]))
        self.assertEqual(response.context['jobs'], [job])

    def test_deferred_jobs(self):
        """Ensure that active jobs page works properly."""
        queue = get_queue('django_rq_test')
        queue_name = 'django_rq_test'

        job = queue.enqueue(access_self)
        registry = queue.deferred_job_registry
        registry.add(job, 2)
        response = self.client.get(reverse('queue_deferred_jobs', args=[queue_name]))
        self.assertEqual(response.context['jobs'], [job])

    def test_workers_home(self):
        response = self.client.get(reverse('workers_home'))
        prev_workers = response.context['workers']
        worker1 = create_worker('django_rq_test')
        worker1.register_birth()
        worker2 = create_worker('test3')
        worker2.register_birth()

        response = self.client.get(reverse('workers_home'))
        self.assertEqual(response.context['workers'], prev_workers + [worker1, worker2])

    def test_queue_workers(self):
        """Worker index page should show workers for a specific queue"""
        queue_name = 'django_rq_test'

        worker1 = create_worker('django_rq_test')
        worker1.register_birth()
        worker2 = create_worker('test3')
        worker2.register_birth()

        response = self.client.get(reverse('queue_workers', args=[queue_name]))
        self.assertEqual(response.context['workers'], [worker1])

    def test_worker_details(self):
        """Worker index page should show workers for a specific queue"""

        worker = create_worker('django_rq_test', name=uuid.uuid4().hex)
        worker.register_birth()

        response = self.client.get(reverse('worker_details', args=[worker.key]))
        self.assertEqual(response.context['worker'], worker)

    def test_statistics_json_view(self):
        """
        Django-RQ's statistic as JSON only viewable by staff or with API_TOKEN
        """

        # Override testing RQ_QUEUES
        queues = {
            'default': {
                'DB': 0,
                'HOST': 'localhost',
                'PORT': 6379,
            }
        }
        with patch('scheduler.settings.QUEUES', new_callable=PropertyMock(return_value=queues)):
            response = self.client.get(reverse('queues_home'))
            self.assertEqual(response.status_code, 200)

            response = self.client.get(reverse('queues_home_json'))
            self.assertEqual(response.status_code, 200)

            # Not staff, only token
            self.user.is_staff = False
            self.user.save()

            response = self.client.get(reverse('queues_home'))
            self.assertEqual(response.status_code, 302)

            # 404 code for stats
            response = self.client.get(reverse('queues_home_json'))
            self.assertEqual(response.status_code, 404)
