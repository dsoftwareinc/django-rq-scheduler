# Usage

## Scheduler thread settings

There is a scheduler thread running the background by deafult.
You can control this by adding to your django project settings:

```python
SCHEDULER_THREAD = False  # This means disable the scheduler thread
```

You can also control how often the scheduler thread will check for
jobs to be scheduled using `SCHEDULER_INTERVAL` setting (default is 60 seconds).

```python
# Scheduler thread will check for jobs to be scheduled every 10 seconds
SCHEDULER_INTERVAL = 10
```

!!! warning

    It is not recommended to have the `SCHEDULER_INTERVAL` less than 10 seconds.

## Making a method in your code a schedulable job to be run by a worker.

See http://python-rq.org/docs/jobs/ or https://github.com/ui/django-rq#job-decorator

An example (**myapp/jobs.py** file):

```python
from django_rq import job


@job
def count():
    return 1 + 1
```

## Scheduling a Job

### Scheduled Job

1. Sign in to the Django Admin site, http://localhost:8000/admin/ and locate the **Django RQ Scheduler** section.
2. Click on the **Add** link for Scheduled Job.
3. Enter a unique name for the job in the **Name** field.
4. In the **Callable** field, enter a Python dot notation path to the method that defines the job. For the example
   above, that would be `myapp.jobs.count`
5. Choose your **Queue**. Side Note: The queues listed are defined in the Django Settings.
6. Enter the time the job is to be executed in the **Scheduled time** field. Side Note: Enter the date via the browser's
   local timezone, the time will automatically convert UTC.
7. Click the **Save** button to schedule the job.

### Repeatable Job

1. Sign in to the Django Admin site, http://localhost:8000/admin/ and locate the **Django RQ Scheduler** section.
2. Click on the **Add** link for Repeatable Job
3. Enter a unique name for the job in the **Name** field.
4. In the **Callable** field, enter a Python dot notation path to the method that defines the job. For the example
   above, that would be `myapp.jobs.count`
5. Choose your **Queue**. Side Note: The queues listed are defined in the Django Settings.
6. Enter the time the first job is to be executed in the **Scheduled time** field. Side Note: Enter the date via the
   browser's local timezone, the time will automatically convert UTC.
7. Enter an **Interval**, and choose the **Interval unit**. This will calculate the time before the function is called
   again.
8. In the **Repeat** field, enter the number of time the job is to be run. Leaving the field empty, means the job will
   be scheduled to run forever.
9. Click the **Save** button to schedule the job.

## Jobs with arguments

django-rq-scheduler supports scheduling jobs with arguments, and even supports
callable arguments that will be calculated in runtime.

```python

from django_rq import job


@job
def job_args_kwargs(*args, **kwargs):
    func = "job_args_kwargs({})"
    args_list = [repr(arg) for arg in args]
    kwargs_list = [f'{k}={v}' for (k, v) in kwargs.items()]
    return func.format(', '.join(args_list + kwargs_list))
```

### Schedule job with custom arguments to be calculated when scheduling

- Follow instructions to add a job above.
- Below, you have the ability to add arguments to `args` and to `kwargs`
    - Pick the argument type and enter value (and key if `kwarg`)

# Reporting issues or Features requests

Please report issues via [GitHub Issues](https://github.com/dsoftwareinc/django-rq-scheduler/issues) .
