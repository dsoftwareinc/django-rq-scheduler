from django.conf import settings
from django.contrib import admin

from scheduler import views
from scheduler.models import Queue
from scheduler.models.worker import Worker

QUEUES = [(key, key) for key in settings.RQ_QUEUES.keys()]


class ImmutableAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False  # Hide the admin "+ Add" link for Queues

    def has_change_permission(self, request, obj=None):
        return True

    def has_module_permission(self, request):
        """
        return True if the given request has any permission in the given
        app label.

        Can be overridden by the user in subclasses. In such case it should
        return True if the given request has permission to view the module on
        the admin index page and access the module's index page. Overriding it
        does not restrict access to the add, change or delete views. Use
        `ModelAdmin.has_(add|change|delete)_permission` for that.
        """
        return request.user.has_module_perms('django-rq-scheduler')


@admin.register(Queue)
class QueueAdmin(ImmutableAdmin):
    """Admin View for Django-RQ Queue"""

    def changelist_view(self, request, extra_context=None):
        """The 'change list' admin view for this model."""
        # proxy request to stats view
        return views.stats(request)


@admin.register(Worker)
class WorkerAdmin(ImmutableAdmin):
    """Admin View for workers"""

    def changelist_view(self, request, extra_context=None):
        """The 'change list' admin view for this model."""
        # proxy request to stats view
        return views.workers(request)
