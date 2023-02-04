from django.apps import AppConfig
from django.apps import apps
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_rq import job

from scheduler.scheduler import DjangoRQScheduler


@job
def reschedule_all_jobs():
    MODEL_NAMES = ['ScheduledJob', 'RepeatableJob', 'CronJob']
    for model_name in MODEL_NAMES:
        model = apps.get_model(app_label='scheduler', model_name=model_name)
        enabled_jobs = model.objects.filter(enabled=True)
        unscheduled_jobs = filter(lambda j: not j.is_scheduled(), enabled_jobs)
        for item in unscheduled_jobs:
            item.save()


class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'scheduler'
    verbose_name = _('Django RQ Scheduler')

    def ready(self):
        try:
            reschedule_all_jobs()
        except Exception:
            # Django isn't ready yet, example a management command is being
            # executed
            pass
        start_scheduler_as_thread = getattr(settings, 'SCHEDULER_THREAD', True)
        if start_scheduler_as_thread:
            interval = getattr(settings, 'SCHEDULER_INTERVAL', 60)
            scheduler = DjangoRQScheduler(interval=interval)
            scheduler.start()
