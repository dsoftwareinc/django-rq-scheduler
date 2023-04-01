import click
from django.apps import apps
from django.core.management.base import BaseCommand

from scheduler.tools import MODEL_NAMES


class Command(BaseCommand):
    """
    Export all scheduled jobs
    """
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            '-o', '--output',
            action='store',
            choices=['json', 'yaml'],
            default='json',
            dest='format',
            help='format of output',
        )

        parser.add_argument(
            '-e', '--enabled',
            action='store_true',
            dest='enabled',
            help='Export only enabled jobs',
        )

    def handle(self, *args, **options):
        res = list()
        for model_name in MODEL_NAMES:
            model = apps.get_model(app_label='scheduler', model_name=model_name)
            jobs = model.objects.all()
            if options.get('enabled'):
                jobs = jobs.filtered(enabled=True)
            for job in jobs:
                res.append(job.to_dict())

        if options.get("format") == 'json':
            import json
            click.echo(json.dumps(res, indent=2))
            return

        if options.get("format") == 'yaml':
            try:
                import yaml
            except ImportError:
                click.echo("Aborting. LibYAML is not installed.")
                return
            # Disable YAML alias
            yaml.Dumper.ignore_aliases = lambda *args: True
            click.echo(yaml.dump(res, default_flow_style=False))
            return
