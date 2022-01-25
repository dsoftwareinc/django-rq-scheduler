from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SchedulerConfig(AppConfig):
    name = 'scheduler'
    verbose_name = _('Django RQ Scheduler')

    def ready(self):
        try:
            self.reschedule_jobs('ScheduledJob')
            self.reschedule_jobs('CronJob')
            self.reschedule_jobs('RepeatableJob')
        except:
            # Django isn't ready yet, example a management command is being
            # executed
            pass

    def reschedule_jobs(self, model_name: str):
        Model = self.get_model(model_name)
        jobs = Model.objects.filter(enabled=True)
        for job in jobs:
            if job.is_scheduled() is False:
                job.save()
