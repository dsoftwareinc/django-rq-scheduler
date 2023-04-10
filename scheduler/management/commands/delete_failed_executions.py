import click
from django.core.management.base import BaseCommand

from scheduler.queues import get_queue
from scheduler.rq_classes import JobExecution


class Command(BaseCommand):
    help = 'Delete failed jobs from Django queue.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--queue', '-q', dest='queue', default='default',
            help='Specify the queue [default]')
        parser.add_argument('-f', '--func', help='optional job function name, e.g. "app.tasks.func"')
        parser.add_argument('--dry-run', action='store_true', help='Do not actually delete failed jobs')

    def handle(self, *args, **options):
        queue = get_queue(options['queue'])
        job_ids = queue.failed_job_registry.get_job_ids()
        jobs = [JobExecution.fetch(job_id) for job_id in job_ids]
        func_name = options.get('func', None)
        if func_name is not None:
            jobs = [job for job in jobs if job.func_name == func_name]
        if options['dry_run']:
            click.echo(f'Found {len(jobs)} failed jobs')
            return

        for job in jobs:
            job.delete()
        click.echo(f'Deleted {len(jobs)} failed jobs')
