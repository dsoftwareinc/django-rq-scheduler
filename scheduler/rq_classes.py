from redis import Redis
from rq import Worker
from rq.command import send_stop_job_command
from rq.job import Job, JobStatus
from rq.queue import Queue
from rq.registry import (
    DeferredJobRegistry, FailedJobRegistry, FinishedJobRegistry,
    ScheduledJobRegistry, StartedJobRegistry, CanceledJobRegistry,
)

ExecutionStatus = JobStatus


class JobExecution(Job):
    def __eq__(self, other):
        return isinstance(other, Job) and self.id == other.id

    @property
    def is_scheduled_job(self):
        return self.meta.get('scheduled_job_id', None) is not None

    def is_execution_of(self, scheduled_job):
        return (self.meta.get('job_type', None) == scheduled_job.JOB_TYPE
                and self.meta.get('scheduled_job_id', None) == scheduled_job.id)

    def stop_execution(self, connection: Redis):
        send_stop_job_command(connection, self.id)

    def to_json(self):
        return dict(
            id=self.id,
            status=self.get_status(),
            started_at=self.started_at,
            ended_at=self.ended_at,
            worker_name=self.worker_name,
        )


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
        return hash((self.name, self.key, ','.join(self.queue_names())))

    def __str__(self):
        return f"{self.name}/{','.join(self.queue_names())}"

    def work(self, **kwargs) -> bool:
        kwargs.setdefault('with_scheduler', True)
        return super(DjangoWorker, self).work(**kwargs)


class DjangoQueue(Queue):
    """
    A subclass of RQ's QUEUE that allows jobs to be stored temporarily to be
    enqueued later at the end of Django's request/response cycle.
    """

    def __init__(self, *args, **kwargs):
        kwargs['job_class'] = JobExecution
        super(DjangoQueue, self).__init__(*args, **kwargs)

    @property
    def finished_job_registry(self):
        return FinishedJobRegistry(self.name, self.connection)

    @property
    def started_job_registry(self):
        return StartedJobRegistry(self.name, self.connection, job_class=JobExecution, )

    @property
    def deferred_job_registry(self):
        return DeferredJobRegistry(self.name, self.connection, job_class=JobExecution, )

    @property
    def failed_job_registry(self):
        return FailedJobRegistry(self.name, self.connection, job_class=JobExecution, )

    @property
    def scheduled_job_registry(self):
        return ScheduledJobRegistry(self.name, self.connection, job_class=JobExecution, )

    @property
    def canceled_job_registry(self):
        return CanceledJobRegistry(self.name, self.connection, job_class=JobExecution, )
