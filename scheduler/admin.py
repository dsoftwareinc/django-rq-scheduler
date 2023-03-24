from django.conf import settings
from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericStackedInline
from django.db.models import QuerySet
from django.templatetags.tz import utc
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from scheduler import tools
from scheduler.models import CronJob, JobArg, JobKwarg, RepeatableJob, ScheduledJob, BaseJob

QUEUES = [(key, key) for key in settings.RQ_QUEUES.keys()]


class HiddenMixin(object):
    class Media:
        js = ['admin/js/jquery.init.js', 'scheduler/js/base.js']


class JobArgInline(HiddenMixin, GenericStackedInline):
    model = JobArg
    extra = 0
    fieldsets = (
        (None, {
            'fields': ('arg_type', 'val',),
        }),
    )


class JobKwargInline(HiddenMixin, GenericStackedInline):
    model = JobKwarg
    extra = 0
    fieldsets = (
        (None, {
            'fields': ('key', 'arg_type', 'val',),
        }),
    )


class JobAdmin(admin.ModelAdmin):
    actions = ['delete_model', 'disable_selected', 'enable_selected', 'schedule_job_now']
    inlines = [JobArgInline, JobKwargInline]
    list_filter = ('enabled',)
    list_display = ('enabled', 'name', 'job_id', 'function_string', 'is_scheduled',)
    list_display_links = ('name',)
    readonly_fields = ('job_id',)
    fieldsets = (
        (None, {
            'fields': ('name', 'callable', 'enabled', 'at_front',),
        }),
        (_('RQ Settings'), {
            'fields': ('queue', 'job_id',),
        }),
    )

    def get_actions(self, request):
        actions = super(JobAdmin, self).get_actions(request)
        actions.pop('delete_selected', None)
        return actions

    def get_form(self, request, obj=None, **kwargs):
        queue_field = self.model._meta.get_field('queue')
        queue_field.choices = QUEUES
        return super(JobAdmin, self).get_form(request, obj, **kwargs)

    @admin.action(description=_("Delete selected %(verbose_name_plural)s"), permissions=('delete',))
    def delete_model(self, request, queryset):
        rows_deleted = 0
        if isinstance(queryset, BaseJob):
            queryset.delete()
            rows_deleted += 1
        elif isinstance(queryset, QuerySet):
            rows_deleted, _ = queryset.delete()
        message_bit = "1 job was" if rows_deleted == 1 else f"{rows_deleted} jobs were"
        level = messages.WARNING if not rows_deleted else messages.INFO
        self.message_user(request, f"{message_bit} successfully deleted.", level=level)

    @admin.action(description=_("Disable selected %(verbose_name_plural)s"), permissions=('change',))
    def disable_selected(self, request, queryset):
        rows_updated = 0
        for obj in queryset.filter(enabled=True).iterator():
            obj.enabled = False
            obj.save()
            rows_updated += 1

        message_bit = "1 job was" if rows_updated == 1 else f"{rows_updated} jobs were"

        level = messages.WARNING if not rows_updated else messages.INFO
        self.message_user(request, f"{message_bit} successfully disabled.", level=level)

    @admin.action(description=_("Enable selected %(verbose_name_plural)s"), permissions=('change',))
    def enable_selected(self, request, queryset):
        rows_updated = 0
        for obj in queryset.filter(enabled=False).iterator():
            obj.enabled = True
            obj.save()
            rows_updated += 1

        message_bit = "1 job was" if rows_updated == 1 else f"{rows_updated} jobs were"
        level = messages.WARNING if not rows_updated else messages.INFO
        self.message_user(request, f"{message_bit} successfully enabled.", level=level)

    @admin.action(description="Run now", permissions=('change',))
    def schedule_job_now(self, request, queryset):
        job_names = []
        for job in queryset:
            job.schedule(utc(now()))
            job.save()
            job_names.append(job.name)
        self.message_user(request, "The following jobs have been enqueued: %s" % (', '.join(job_names),))

    # @admin.action(description="Run now", permissions=('change',))
    # def run_job_now(self, request, queryset):
    #     job_names = []
    #     for job in queryset:
    #         job.enqueue_to_run()
    #         job.save()
    #         job_names.append(job.name)
    #     self.message_user(request, "The following jobs have been run: %s" % (', '.join(job_names),))


@admin.register(ScheduledJob)
class ScheduledJobAdmin(JobAdmin):
    list_display = JobAdmin.list_display + ('scheduled_time',)

    fieldsets = JobAdmin.fieldsets + (
        (_('Scheduling'), {
            'fields': (
                'scheduled_time',
                'timeout',
                'result_ttl'
            ),
        }),
    )


@admin.register(RepeatableJob)
class RepeatableJobAdmin(JobAdmin):
    list_display = JobAdmin.list_display + ('scheduled_time', 'interval_display')

    fieldsets = JobAdmin.fieldsets + (
        (_('Scheduling'), {
            'fields': (
                'scheduled_time',
                ('interval', 'interval_unit',),
                'repeat',
                'timeout',
                'result_ttl',
            ),
        }),
    )


@admin.register(CronJob)
class CronJobAdmin(JobAdmin):
    list_display = JobAdmin.list_display + ('cron_string', 'next_run')

    fieldsets = JobAdmin.fieldsets + (
        (_('Scheduling'), {
            'fields': (
                'cron_string',
                'repeat',
                'timeout',
                'result_ttl',
            ),
        }),
    )

    @admin.display(description='Next run')
    def next_run(self, o):
        return tools.get_next_cron_time(o.cron_string)
