import logging
from typing import List

import redis
from redis.sentinel import Sentinel

from .rq_classes import JobExecution, DjangoQueue, DjangoWorker

logger = logging.getLogger("scheduler")


def _get_redis_connection(config, use_strict_redis=False):
    """
    Returns a redis connection from a connection config
    """
    redis_cls = redis.StrictRedis if use_strict_redis else redis.Redis
    logger.debug(f'Getting connection for {config}')
    if 'URL' in config:
        if config.get('SSL') or config.get('URL').startswith('rediss://'):
            return redis_cls.from_url(
                config['URL'],
                db=config.get('DB'),
                ssl_cert_reqs=config.get('SSL_CERT_REQS', 'required'),
            )
        else:
            return redis_cls.from_url(
                config['URL'],
                db=config.get('DB'),
            )

    if 'UNIX_SOCKET_PATH' in config:
        return redis_cls(unix_socket_path=config['UNIX_SOCKET_PATH'], db=config['DB'])

    if 'SENTINELS' in config:
        connection_kwargs = {
            'db': config.get('DB'),
            'password': config.get('PASSWORD'),
            'username': config.get('USERNAME'),
            'socket_timeout': config.get('SOCKET_TIMEOUT'),
        }
        connection_kwargs.update(config.get('CONNECTION_KWARGS', {}))
        sentinel_kwargs = config.get('SENTINEL_KWARGS', {})
        sentinel = Sentinel(config['SENTINELS'], sentinel_kwargs=sentinel_kwargs, **connection_kwargs)
        return sentinel.master_for(
            service_name=config['MASTER_NAME'],
            redis_class=redis_cls,
        )

    return redis_cls(
        host=config['HOST'],
        port=config['PORT'],
        db=config.get('DB', 0),
        username=config.get('USERNAME', None),
        password=config.get('PASSWORD'),
        ssl=config.get('SSL', False),
        ssl_cert_reqs=config.get('SSL_CERT_REQS', 'required'),
        **config.get('REDIS_CLIENT_KWARGS', {})
    )


class QueueNotFoundError(Exception):
    pass


def get_connection(name='default', use_strict_redis=False):
    """Returns a Redis connection to use based on parameters in RQ_QUEUES
    """
    from .settings import QUEUES

    if name not in QUEUES:
        raise QueueNotFoundError(f'Queue {name} not found, queues={QUEUES.keys()}')

    return _get_redis_connection(QUEUES[name], use_strict_redis)


def get_queue(
        name='default',
        default_timeout=None, is_async=None,
        autocommit=None,
        connection=None,
        **kwargs
) -> DjangoQueue:
    """Returns an DjangoQueue using parameters defined in ``RQ_QUEUES``
    """
    from .settings import QUEUES

    if is_async is None:
        is_async = QUEUES[name].get('ASYNC', True)

    if default_timeout is None:
        default_timeout = QUEUES[name].get('DEFAULT_TIMEOUT')
    if connection is None:
        connection = get_connection(name)
    return DjangoQueue(
        name,
        default_timeout=default_timeout,
        connection=connection,
        is_async=is_async,
        autocommit=autocommit,
        **kwargs
    )


def get_all_workers():
    from .settings import QUEUES
    workers = set()
    for queue_name in QUEUES:
        connection = get_connection(queue_name)
        try:
            curr_workers = set(DjangoWorker.all(connection=connection))
            workers.update(curr_workers)
        except redis.ConnectionError as e:
            logger.error(f'Could not connect for queue {queue_name}: {e}')
    return workers


def _filter_connection_params(queue_params):
    """
    Filters the queue params to keep only the connection related params.
    """
    CONNECTION_PARAMS = (
        'URL',
        'DB',
        'USE_REDIS_CACHE',
        'UNIX_SOCKET_PATH',
        'HOST',
        'PORT',
        'PASSWORD',
        'SENTINELS',
        'MASTER_NAME',
        'SOCKET_TIMEOUT',
        'SSL',
        'CONNECTION_KWARGS',
    )

    # return {p:v for p,v in queue_params.items() if p in CONNECTION_PARAMS}
    # Dict comprehension compatible with python 2.6
    return dict((p, v) for (p, v) in queue_params.items() if p in CONNECTION_PARAMS)


def get_queues(*queue_names, **kwargs) -> List[DjangoQueue]:
    """
    Return queue instances from specified queue names.
    All instances must use the same Redis connection.
    """
    from .settings import QUEUES

    if len(queue_names) <= 1:
        # Return "default" queue if no queue name is specified
        # or one queue with specified name
        return [get_queue(*queue_names, **kwargs)]

    kwargs['job_class'] = JobExecution
    queue_params = QUEUES[queue_names[0]]
    connection_params = _filter_connection_params(queue_params)
    queues = [get_queue(queue_names[0], **kwargs)]

    # perform consistency checks while building return list
    for name in queue_names[1:]:
        queue = get_queue(name, **kwargs)
        if type(queue) is not type(QUEUES[0]):  # noqa: E721
            raise ValueError(
                'Queues must have the same class.'
                '"{0}" and "{1}" have '
                'different classes'.format(name, queue_names[0])
            )
        if connection_params != _filter_connection_params(QUEUES[name]):
            raise ValueError(
                f'Queues must have the same redis connection. "{name}" and'
                f' "{queue_names[0]}" have different connections')
        queues.append(queue)

    return queues
