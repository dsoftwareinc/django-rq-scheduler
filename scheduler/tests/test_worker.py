import os

from scheduler.tests.testtools import SchedulerBaseCase
from scheduler.tools import create_worker


class TestWorker(SchedulerBaseCase):
    def test_create_worker__two_workers_same_queue(self):
        worker1 = create_worker('default')
        worker1.register_birth()
        worker2 = create_worker('default')
        worker2.register_birth()
        hostname = os.uname()[1]
        self.assertEqual(f'{hostname}-worker:1', worker1.name)
        self.assertEqual(f'{hostname}-worker:2', worker2.name)
