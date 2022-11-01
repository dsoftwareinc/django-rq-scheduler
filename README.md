# Django RQ Scheduler 
[![Django CI](https://github.com/dsoftwareinc/django-rq-scheduler/actions/workflows/test.yml/badge.svg)](https://github.com/dsoftwareinc/django-rq-scheduler/actions/workflows/test.yml)
![badge](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/cunla/b756396efb895f0e34558c980f1ca0c7/raw/django-rq-scheduler-4.json)
[![badge](https://img.shields.io/pypi/dm/django-rq-scheduler)](https://pypi.org/project/django-rq-scheduler/)


A database backed job scheduler for Django RQ.
Based on original [django-rq-scheduler](https://github.com/isl-x/django-rq-scheduler) - Now supports Django 4.0.

This allows remembering scheduled jobs, their parameters, etc.

# Installation

1. Use pip to install:
   ```shell
   pip install django-rq-scheduler
   ```

2. In `settings.py`, add `django_rq` and `scheduler` to  `INSTALLED_APPS`:
   ```python
   INSTALLED_APPS = [
       ...
       'django_rq',
       'scheduler',
       ...
   ]
   ```

3. Configure Django RQ. See https://github.com/ui/django-rq#installation
   
   Add at least one Redis Queue to your `settings.py`:
   ```python
   RQ_QUEUES = {
     'default': {
         'HOST': 'localhost',
         'PORT': 6379,
         'DB': 0,
         'PASSWORD': 'some-password',
         'DEFAULT_TIMEOUT': 360,
     },
   }
   ```

4. Run migrations.
    ```shell
    ./manage.py migrate
    ```

# Usage

## Making a method in your code a schedulable job to be run by a worker.

See http://python-rq.org/docs/jobs/ or https://github.com/ui/django-rq#job-decorator

An example:

**myapp.jobs.py**

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

4. In the **Callable** field, enter a Python dot notation path to the method that defines the job. For the example above, that would be `myapp.jobs.count`

5. Choose your **Queue**. Side Note: The queues listed are defined in the Django Settings.

6. Enter the time the job is to be executed in the **Scheduled time** field. Side Note: Enter the date via the browser's local timezone, the time will automatically convert UTC.

7. Click the **Save** button to schedule the job.

### Repeatable Job

1. Sign in to the Django Admin site, http://localhost:8000/admin/ and locate the **Django RQ Scheduler** section.

2. Click on the **Add** link for Repeatable Job

3. Enter a unique name for the job in the **Name** field.

4. In the **Callable** field, enter a Python dot notation path to the method that defines the job. For the example above, that would be `myapp.jobs.count`

5. Choose your **Queue**. Side Note: The queues listed are defined in the Django Settings.

6. Enter the time the first job is to be executed in the **Scheduled time** field. Side Note: Enter the date via the browser's local timezone, the time will automatically convert UTC.

7. Enter an **Interval**, and choose the **Interval unit**. This will calculate the time before the function is called again.

8. In the **Repeat** field, enter the number of time the job is to be ran. Leaving the field empty, means the job will be scheduled to run forever.

9. Click the **Save** button to schedule the job.

# Advanced usage using jobs with args

django-rq-scheduler supports 
```python

from django_rq import job
@job
def job_args_kwargs(*args, **kwargs):
    func = "test_args_kwargs({})"
    args_list = [repr(arg) for arg in args]
    kwargs_list = [k + '=' + repr(v) for (k, v) in kwargs.items()]
    return func.format(', '.join(args_list + kwargs_list))
```


### Schedule job with custom arguments to be calculated when scheduling

1. Sign in to the Django Admin site, http://localhost:8000/admin/ and locate the **Django RQ Scheduler** section.

2. Click on the **Add** link for Scheduled Job.

3. Enter a unique name for the job in the **Name** field.

4. In the **Callable** field, enter a Python dot notation path to the method that defines the job. For the example above, that would be `myapp.jobs.job_args_kwargs`

5. Choose your **Queue**. Side Note: The queues listed are defined in the Django Settings.

6. Enter the time the job is to be executed in the **Scheduled time** field. Side Note: Enter the date via the browser's local timezone, the time will automatically convert UTC.

7. Click the **Save** button to schedule the job.

8. Add arguments to the job, pick argument type.

9. Add arguments with keys to the job, pick argument type and value.

# Reporting issues or Features requests

Please report issues via [GitHub Issues](https://github.com/dsoftwareinc/django-rq-scheduler/issues) .

