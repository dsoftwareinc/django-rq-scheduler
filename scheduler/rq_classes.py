from rq import Worker
from rq.job import Job, JobStatus
from rq.queue import Queue

ExecutionStatus = JobStatus


class JobExecution(Job):
    def __eq__(self, other):
        return isinstance(other, Job) and self.id == other.id

    @property
    def is_scheduled_job(self):
        return self.meta.get('scheduled_job_id', None) is not None


class DjangoWorker(Worker):
    def __init__(self, *args, **kwargs):
        kwargs['job_class'] = JobExecution
        kwargs['queue_class'] = DjangoQueue
        super(DjangoWorker, self).__init__(*args, **kwargs)

    def __eq__(self, other):
        return (isinstance(other, Worker)
                and self.key == other.key
                and self.name == other.name)

    def __hash__(self):
        return hash((self.name, self.key))

    def work(self, **kwargs) -> bool:
        super(DjangoWorker, self).work(with_scheduler=True, **kwargs)


class DjangoQueue(Queue):
    """
    A subclass of RQ's QUEUE that allows jobs to be stored temporarily to be
    enqueued later at the end of Django's request/response cycle.
    """

    def __init__(self, *args, **kwargs):
        super(DjangoQueue, self).__init__(*args, **kwargs)
