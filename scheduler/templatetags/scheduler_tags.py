from django import template

from scheduler.scheduler import DjangoRQScheduler

register = template.Library()


@register.simple_tag()
def scheduler_status(*args, **kwargs):
    sched = DjangoRQScheduler.instance()
    return str(sched.status.value.upper()) if sched else "No internal scheduler"
