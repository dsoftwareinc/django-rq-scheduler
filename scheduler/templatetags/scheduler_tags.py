from django import template

from scheduler.rq_classes import JobExecution
from scheduler.tools import get_scheduled_job

register = template.Library()


@register.filter
def show_func_name(rq_job: JobExecution) -> str:
    try:
        if rq_job.func_name == 'scheduler.tools.run_job':
            job = get_scheduled_job(*rq_job.args)
            return job.function_string()
        return rq_job.func_name
    except Exception as e:
        return repr(e)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
