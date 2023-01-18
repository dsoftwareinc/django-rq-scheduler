from django.apps import AppConfig
from django.apps import apps
from django.utils.translation import gettext_lazy as _
from django_rq import job


@job
def reschedule_all_jobs():
    MODEL_NAMES = ['ScheduledJob', 'RepeatableJob', 'CronJob']
    for model_name in MODEL_NAMES:
        model = apps.get_model(app_label='scheduler', model_name=model_name)
        enabled_jobs = model.objects.filter(enabled=True)
        unscheduled_jobs = filter(lambda job: not job.is_scheduled(), enabled_jobs)
        for item in unscheduled_jobs:
            item.save()


class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'scheduler'
    verbose_name = _('Django RQ Scheduler')

    def ready(self):
        try:
            cronjob_model = apps.get_model(app_label='scheduler', model_name='CronJob')
            scheduler_job = cronjob_model.objects.filter(name='Job scheduling jobs').first()
            if scheduler_job is None:
                scheduler_job = cronjob_model.objects.create(
                    cron_string='* * * * *',
                    name='Job scheduling jobs',
                    callable='scheduler.apps.reschedule_all_jobs',
                    enabled=True,
                    queue='default',
                )
            scheduler_job.save()
        except Exception:
            # Django isn't ready yet, example a management command is being
            # executed
            pass
