from typing import List, Any, Optional, Union

from redis import Redis
from redis.client import Pipeline
from rq import Worker
from rq.command import send_stop_job_command
from rq.job import Job, JobStatus
from rq.queue import Queue
from rq.registry import (
    DeferredJobRegistry, FailedJobRegistry, FinishedJobRegistry,
    ScheduledJobRegistry, StartedJobRegistry, CanceledJobRegistry,
)
from rq.scheduler import RQScheduler


def as_text(v: Union[bytes, str]) -> Optional[str]:
    """Converts a bytes value to a string using `utf-8`.

    :param v: The value (bytes or string)
    :raises: ValueError: If the value is not bytes or string
    :returns: Either the decoded string or None
    """
    if v is None:
        return None
    elif isinstance(v, bytes):
        return v.decode('utf-8')
    elif isinstance(v, str):
        return v
    else:
        raise ValueError('Unknown type %r' % type(v))


def compact(lst: List[Any]) -> List[Any]:
    """Excludes `None` values from a list-like object.

    :param lst: A list (or list-like) object

    :returns: The list without None values
    """
    return [item for item in lst if item is not None]


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

    def _set_property(self, prop_name: str, val, pipeline: Optional[Pipeline] = None):
        connection = pipeline if pipeline is not None else self.connection
        if val is None:
            connection.hdel(self.key, prop_name)
        else:
            connection.hset(self.key, prop_name, val)

    def _get_property(self, prop_name: str, pipeline: Optional[Pipeline] = None):
        connection = pipeline if pipeline is not None else self.connection
        return as_text(connection.hget(self.key, prop_name))

    def scheduler_pid(self) -> int:
        pid = self.connection.get(RQScheduler.get_locking_key(self.queues[0].name))
        return int(pid.decode()) if pid is not None else None


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

    def get_all_job_ids(self) -> List[str]:
        res = list()
        res.extend(self.get_job_ids())
        res.extend(self.finished_job_registry.get_job_ids())
        res.extend(self.started_job_registry.get_job_ids())
        res.extend(self.deferred_job_registry.get_job_ids())
        res.extend(self.failed_job_registry.get_job_ids())
        res.extend(self.scheduled_job_registry.get_job_ids())
        res.extend(self.canceled_job_registry.get_job_ids())
        return res

    def get_all_jobs(self):
        job_ids = self.get_all_job_ids()
        return compact([self.fetch_job(job_id) for job_id in job_ids])
