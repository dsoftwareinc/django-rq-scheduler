import os
import sys

import click
from django.core.management.base import BaseCommand
from django.db import connections
from redis.exceptions import ConnectionError
from rq import use_connection
from rq.logutils import setup_loghandlers

from scheduler.tools import create_worker

LOG_LEVELS = {
    0: "CRITICAL",
    1: "WARNING",
    2: "INFO",
    3: "DEBUG",
}


def reset_db_connections():
    for c in connections.all():
        c.close()


class Command(BaseCommand):
    """
    Runs RQ workers on specified queues. Note that all queues passed into a
    single rqworker command must share the same connection.

    Example usage:
    python manage.py rqworker high medium low
    """

    args = '<queue queue ...>'

    def add_arguments(self, parser):
        parser.add_argument('--pid', action='store', dest='pidfile',
                            default=None, help='file to write the worker`s pid into')
        parser.add_argument('--burst', action='store_true', dest='burst',
                            default=False, help='Run worker in burst mode')
        parser.add_argument('--name', action='store', dest='name',
                            default=None, help='Name of the worker')
        parser.add_argument('--worker-ttl', action='store', type=int, dest='worker_ttl', default=420,
                            help='Default worker timeout to be used')
        parser.add_argument('--max-jobs', action='store', default=None, dest='max_jobs', type=int,
                            help='Maximum number of jobs to execute before terminating worker')
        parser.add_argument(
            'queues', nargs='*', type=str,
            help='The queues to work on, separated by space, all queues should be using the same redis')

    def handle(self, *queues, **options):
        pidfile = options.get('pidfile')
        if pidfile:
            with open(os.path.expanduser(pidfile), "w") as fp:
                fp.write(str(os.getpid()))

        # Verbosity is defined by default in BaseCommand for all commands
        verbosity = options.get('verbosity', 1)
        level = LOG_LEVELS.get(verbosity, 'INFO')
        setup_loghandlers(level)

        try:
            # Instantiate a worker
            w = create_worker(*queues, name=options['name'], default_worker_ttl=options['worker_ttl'], )

            # Call use_connection to push the redis connection into LocalStack
            # without this, jobs using RQ's get_current_job() will fail
            use_connection(w.connection)

            # Close any opened DB connection before any fork
            reset_db_connections()

            w.work(burst=options.get('burst', False),
                   with_scheduler=True,
                   logging_level=verbosity,
                   max_jobs=options['max_jobs'], )
        except ConnectionError as e:
            click.echo(str(e), err=True)
            sys.exit(1)
