import importlib
from datetime import datetime, timedelta

import croniter
from django.apps import apps
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.templatetags.tz import utc
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_rq.queues import get_queue
from model_utils import Choices
from model_utils.models import TimeStampedModel

RQ_SCHEDULER_INTERVAL = getattr(settings, "DJANGO_RQ_SCHEDULER_INTERVAL", 60)


def callback_save_job(job, connection, result, *args, **kwargs):
    model_name = job.meta.get('job_type', None)
    if model_name is None:
        return
    model = apps.get_model(app_label='scheduler', model_name=model_name)
    scheduled_job = model.objects.filter(job_id=job.id).first()
    if scheduled_job:
        scheduled_job.save()


class BaseJobArg(models.Model):
    ARG_TYPE = Choices(
        ('str_val', _('string')),
        ('int_val', _('int')),
        ('bool_val', _('boolean')),
        ('datetime_val', _('Datetime')),
    )
    arg_type = models.CharField(
        _('Argument Type'), max_length=12, choices=ARG_TYPE, default=ARG_TYPE.str_val
    )
    str_val = models.CharField(_('String Value'), blank=True, max_length=255)
    int_val = models.IntegerField(_('Int Value'), blank=True, null=True)
    bool_val = models.BooleanField(_('Boolean Value'), default=False)
    datetime_val = models.DateTimeField(_('Datetime Value'), blank=True, null=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    def __repr__(self):
        return repr(self.value())

    def __str__(self):
        return str(self.value())

    def clean(self):
        self.clean_one_value()

    def clean_one_value(self):
        count = 0
        count += 1 if self.str_val != '' else 0
        count += 1 if self.int_val else 0
        count += 1 if self.datetime_val else 0
        count += 1 if self.bool_val else 0
        # Catch case where bool_val is intended to be false and bool is selected.
        count += 1 if self.arg_type == 'bool_val' and self.bool_val is False else 0
        if count == 0:
            raise ValidationError({
                'arg_type': ValidationError(
                    _('At least one arg type must have a value'), code='invalid')
            })
        if count > 1:
            raise ValidationError({
                'arg_type': ValidationError(
                    _('There are multiple arg types with values'), code='invalid')
            })

    def save(self, **kwargs):
        super(BaseJobArg, self).save(**kwargs)
        self.content_object.save()

    def delete(self, **kwargs):
        super(BaseJobArg, self).delete(**kwargs)
        self.content_object.save()

    def value(self):
        return getattr(self, self.arg_type)

    class Meta:
        abstract = True
        ordering = ['id']


class JobArg(BaseJobArg):
    pass


class JobKwarg(BaseJobArg):
    key = models.CharField(max_length=255)

    def __str__(self):
        key, value = self.value()
        return 'key={} value={}'.format(key, value)

    def value(self):
        return self.key, super(JobKwarg, self).value()


class BaseJob(TimeStampedModel):
    JOB_TYPE = 'BaseJob'
    name = models.CharField(_('name'), max_length=128, unique=True)
    callable = models.CharField(_('callable'), max_length=2048)
    callable_args = GenericRelation(JobArg, related_query_name='args')
    callable_kwargs = GenericRelation(JobKwarg, related_query_name='kwargs')
    enabled = models.BooleanField(_('enabled'), default=True)
    queue = models.CharField(
        _('queue'),
        max_length=16,
        help_text='Queue name', )
    job_id = models.CharField(
        _('job id'), max_length=128, editable=False, blank=True, null=True)
    repeat = models.PositiveIntegerField(_('repeat'), blank=True, null=True)
    at_front = models.BooleanField(_('At front'), default=False, blank=True, null=True)
    timeout = models.IntegerField(
        _('timeout'), blank=True, null=True,
        help_text=_(
            'Timeout specifies the maximum runtime, in seconds, for the job '
            'before it\'ll be considered \'lost\'. Blank uses the default '
            'timeout.'
        )
    )
    result_ttl = models.IntegerField(
        _('result ttl'), blank=True, null=True,
        help_text=_('The TTL value (in seconds) of the job result. -1: '
                    'Result never expires, you should delete jobs manually. '
                    '0: Result gets deleted immediately. >0: Result expires '
                    'after n seconds.')
    )

    def __str__(self):
        return self.name

    def callable_func(self):
        path = self.callable.split('.')
        module = importlib.import_module('.'.join(path[:-1]))
        func = getattr(module, path[-1])
        if callable(func) is False:
            raise TypeError("'{}' is not callable".format(self.callable))
        return func

    def clean(self):
        self.clean_callable()
        self.clean_queue()

    def clean_callable(self):
        try:
            self.callable_func()
        except TypeError:
            raise ValidationError({
                'callable': ValidationError(
                    _('Invalid callable, must be importable'), code='invalid')
            })

    def clean_queue(self):
        queue_keys = settings.RQ_QUEUES.keys()
        if self.queue not in queue_keys:
            raise ValidationError({
                'queue': ValidationError(
                    _('Invalid queue, must be one of: {}'.format(
                        ', '.join(queue_keys))), code='invalid')
            })

    def is_scheduled(self) -> bool:
        if not self.job_id:
            return False
        return self.job_id in self.get_rqueue().scheduled_job_registry.get_job_ids()

    is_scheduled.short_description = _('is scheduled?')
    is_scheduled.boolean = True

    def save(self, **kwargs):
        if kwargs.get('schedule_job', True):
            self.schedule()
        super(BaseJob, self).save(**kwargs)

    def delete(self, **kwargs):
        self.unschedule()
        super(BaseJob, self).delete(**kwargs)

    def function_string(self) -> str:
        func = self.callable + "(\u200b{})"  # zero-width space allows textwrap
        args = self.parse_args()
        args_list = [repr(arg) for arg in args]
        kwargs = self.schedule_kwargs()['kwargs']
        kwargs_list = [k + '=' + repr(v) for (k, v) in kwargs.items()]
        return func.format(', '.join(args_list + kwargs_list))

    function_string.short_description = 'Callable'

    def parse_args(self):
        args = self.callable_args.all()
        return [arg.value() for arg in args]

    def schedule_kwargs(self) -> dict:
        kwargs = self.callable_kwargs.all()
        res = dict(
            meta=dict(
                repeat=self.repeat,
                job_type=self.JOB_TYPE,
            ),
            args=self.parse_args(),
            on_success=callback_save_job,
            on_failure=callback_save_job,
            kwargs=dict([kwarg.value() for kwarg in kwargs])
        )
        if self.at_front:
            res['at_front'] = self.at_front
        if self.timeout:
            res['job_timeout'] = self.timeout
        if self.result_ttl is not None:
            res['result_ttl'] = self.result_ttl
        return res

    def get_rqueue(self):
        return get_queue(self.queue)

    def is_schedulable(self) -> bool:
        return self.enabled and not self.is_scheduled()

    def schedule(self) -> bool:
        self.unschedule()
        if self.is_schedulable() is False:
            return False
        return True

    def unschedule(self) -> bool:
        queue = self.get_rqueue()
        if self.is_scheduled():
            queue.remove(self.job_id)
            queue.scheduled_job_registry.remove(self.job_id)
        self.job_id = None
        return True

    class Meta:
        abstract = True


class ScheduledTimeMixin(models.Model):
    scheduled_time = models.DateTimeField(_('scheduled time'))

    def schedule_time_utc(self):
        return utc(self.scheduled_time)

    class Meta:
        abstract = True


class ScheduledJob(ScheduledTimeMixin, BaseJob):
    repeat = None
    JOB_TYPE = 'ScheduledJob'

    def schedule(self) -> bool:
        result = super(ScheduledJob, self).schedule()
        if self.scheduled_time is not None and self.scheduled_time < timezone.now():
            return False
        if result is False:
            return False
        kwargs = self.schedule_kwargs()
        job = self.get_rqueue().enqueue_at(
            self.schedule_time_utc(),
            self.callable_func(),
            **kwargs
        )
        self.job_id = job.id
        return True

    class Meta:
        verbose_name = _('Scheduled Job')
        verbose_name_plural = _('Scheduled Jobs')
        ordering = ('name',)


class RepeatableJob(ScheduledTimeMixin, BaseJob):
    UNITS = Choices(
        ('seconds', _('seconds')),
        ('minutes', _('minutes')),
        ('hours', _('hours')),
        ('days', _('days')),
        ('weeks', _('weeks')),
    )

    interval = models.PositiveIntegerField(_('interval'))
    interval_unit = models.CharField(
        _('interval unit'), max_length=12, choices=UNITS, default=UNITS.hours
    )
    JOB_TYPE = 'RepeatableJob'

    def clean(self):
        super(RepeatableJob, self).clean()
        self.clean_interval_unit()
        self.clean_result_ttl()

    def clean_interval_unit(self):
        if RQ_SCHEDULER_INTERVAL > self.interval_seconds():
            raise ValidationError(
                _("Job interval is set lower than %(queue)r queue's interval."),
                code='invalid',
                params={'queue': self.queue})
        if self.interval_seconds() % RQ_SCHEDULER_INTERVAL:
            raise ValidationError(
                _("Job interval is not a multiple of rq_scheduler's interval frequency: %(interval)ss"),
                code='invalid',
                params={'interval': RQ_SCHEDULER_INTERVAL})

    def clean_result_ttl(self) -> None:
        """
        Throws an error if there are repeats left to run and the result_ttl won't last until the next scheduled time.
        :return: None
        """
        if self.result_ttl and self.result_ttl != -1 and self.result_ttl < self.interval_seconds() and self.repeat:
            raise ValidationError(
                _("Job result_ttl must be either indefinite (-1) or "
                  "longer than the interval, %(interval)s seconds, to ensure rescheduling."),
                code='invalid',
                params={'interval': self.interval_seconds()}, )

    def interval_display(self):
        return '{} {}'.format(self.interval, self.get_interval_unit_display())

    def interval_seconds(self):
        kwargs = {
            self.interval_unit: self.interval,
        }
        return timedelta(**kwargs).total_seconds()

    def _prevent_duplicate_runs(self):
        """
        Counts the number of repeats lapsed between scheduled time and now
        and decrements that amount from the repeats remaining and updates the scheduled time to the next repeat.
        :return:
        """
        while self.scheduled_time < timezone.now() and (self.repeat is None or self.repeat > 0):
            self.scheduled_time += timedelta(seconds=self.interval_seconds())
            if self.repeat and self.repeat > 0:
                self.repeat -= 1

    def schedule(self):
        result = super(RepeatableJob, self).schedule()
        self._prevent_duplicate_runs()
        if self.scheduled_time < timezone.now():
            return False
        if result is False:
            return False
        kwargs = self.schedule_kwargs()
        kwargs['meta']['interval'] = self.interval_seconds()
        job = self.get_rqueue().enqueue_at(
            self.schedule_time_utc(),
            self.callable_func(),
            **kwargs
        )
        self.job_id = job.id
        return True

    class Meta:
        verbose_name = _('Repeatable Job')
        verbose_name_plural = _('Repeatable Jobs')
        ordering = ('name',)


def _get_next_scheduled_time(cron_string):
    """Calculate the next scheduled time by creating a crontab object
    with a cron string"""
    now = timezone.now()
    itr = croniter.croniter(cron_string, now)
    return itr.get_next(datetime)


class CronJob(BaseJob):
    JOB_TYPE = 'CronJob'

    cron_string = models.CharField(
        _('cron string'), max_length=64,
        help_text=_('Define the schedule in a crontab like syntax. Times are in UTC.')
    )

    def clean(self):
        super(CronJob, self).clean()
        self.clean_cron_string()

    def clean_cron_string(self):
        try:
            croniter.croniter(self.cron_string)
        except ValueError as e:
            raise ValidationError({
                'cron_string': ValidationError(
                    _(str(e)), code='invalid')
            })

    def schedule(self):
        result = super(CronJob, self).schedule()
        if result is False:
            return False

        kwargs = self.schedule_kwargs()
        scheduled_time = _get_next_scheduled_time(self.cron_string)
        job = self.get_rqueue().enqueue_at(
            scheduled_time,
            self.callable_func(),
            **kwargs
        )
        self.job_id = job.id
        return True

    class Meta:
        verbose_name = _('Cron Job')
        verbose_name_plural = _('Cron Jobs')
        ordering = ('name',)
