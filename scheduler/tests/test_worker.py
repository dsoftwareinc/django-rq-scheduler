import os

from scheduler.tests.testtools import SchedulerBaseCase
from scheduler.tools import create_worker
from . import test_settings  # noqa


class TestWorker(SchedulerBaseCase):
    def test_create_worker__two_workers_same_queue(self):
        worker1 = create_worker('default', 'django_rq_scheduler_test')
        worker1.register_birth()
        worker2 = create_worker('default')
        worker2.register_birth()
        hostname = os.uname()[1]
        self.assertEqual(f'{hostname}-worker:1', worker1.name)
        self.assertEqual(f'{hostname}-worker:2', worker2.name)

    def test_create_worker__worker_with_queues_different_connection(self):
        with self.assertRaises(ValueError):
            create_worker('default', 'test1')
