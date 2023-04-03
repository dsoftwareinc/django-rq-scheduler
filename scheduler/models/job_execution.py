from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _
from model_utils import Choices


class JobExecution(models.Model):
    # Job relation
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    STATUS = Choices(
        ('done', 'Finished'),
        ('failed', 'Failed'),
        ('scheduled', 'Scheduled'),
        ('running', 'Running'),
    )

    status = models.CharField(
        _('Execution status'), max_length=12, choices=STATUS, default=STATUS.scheduled)
    worker = models.CharField(_('Worker name'), max_length=50)
    queue = models.CharField(_('Queue name'), max_length=50)

    class Meta:
        managed = False  # not in Django's database
        permissions = [['view', 'Access admin page']]
        verbose_name_plural = "Job executions"
