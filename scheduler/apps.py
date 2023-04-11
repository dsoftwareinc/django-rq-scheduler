from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'scheduler'
    verbose_name = _('Django RQ Scheduler')

    def ready(self):
        pass  # Django isn't ready yet, example a management command is being executed
