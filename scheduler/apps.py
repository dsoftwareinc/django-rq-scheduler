
from django.apps import AppConfig
from django.db.models.functions import Now
from django.utils.translation import gettext_lazy as _


class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'scheduler'
    verbose_name = _('Django RQ Scheduler')

    def ready(self):
        try:
            self.reschedule_cron_jobs()
            self.reschedule_repeatable_jobs()
            self.reschedule_scheduled_jobs()
        except Exception:
            # Django isn't ready yet, example a management command is being
            # executed
            pass

    def reschedule_cron_jobs(self):
        cron_job_class = self.get_model('CronJob')
        jobs = cron_job_class.objects.filter(enabled=True)
        self.reschedule_jobs(jobs)

    def reschedule_repeatable_jobs(self):
        repeatable_job_class = self.get_model('RepeatableJob')
        jobs = repeatable_job_class.objects.filter(enabled=True)
        self.reschedule_jobs(jobs)

    def reschedule_scheduled_jobs(self):
        scheduled_job_class = self.get_model('ScheduledJob')
        jobs = scheduled_job_class.objects.filter(
            enabled=True, scheduled_time__lte=Now())
        self.reschedule_jobs(jobs)

    @staticmethod
    def reschedule_jobs(jobs):
        for job in jobs:
            if job.is_scheduled() is False:
                job.save()
