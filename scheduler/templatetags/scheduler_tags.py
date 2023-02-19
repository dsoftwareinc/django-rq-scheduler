from django import template
from django.shortcuts import render
from django_rq.utils import get_statistics

from scheduler.scheduler import DjangoRQScheduler

register = template.Library()


@register.simple_tag()
def scheduler_status(*args, **kwargs):
    sched = DjangoRQScheduler.instance()
    return str(sched.status.value.upper())
