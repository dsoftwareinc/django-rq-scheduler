from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

from scheduler.tools import reschedule_all_jobs


class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'scheduler'
    verbose_name = _('Django RQ Scheduler')

    def ready(self):
        try:
            reschedule_all_jobs()
        except Exception:
            pass  # Django isn't ready yet, example a management command is being executed
