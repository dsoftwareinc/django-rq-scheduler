from __future__ import unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class SchedulerConfig(AppConfig):
    name = 'scheduler'
    verbose_name = _('Django RQ Scheduler')

    def ready(self):
        self.reschedule_repeatable_jobs()
        self.reschedule_scheduled_jobs()

    def reschedule_repeatable_jobs(self):
        from scheduler.models import RepeatableJob  # noqa
        jobs = RepeatableJob.objects.filter(enabled=True)
        self.reschedule_jobs(jobs)

    def reschedule_scheduled_jobs(self):
        from scheduler.models import ScheduledJob  # noqa
        jobs = ScheduledJob.objects.filter(enabled=True)
        self.reschedule_jobs(jobs)

    def reschedule_jobs(self, jobs):
        for job in jobs:
            if job.is_scheduled() is False:
                job.save()
