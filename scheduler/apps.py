from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from scheduler.rq_classes import DjangoScheduler


class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'scheduler'
    verbose_name = _('Django RQ Scheduler')

    def ready(self):
        DjangoScheduler.reschedule_all_jobs()
