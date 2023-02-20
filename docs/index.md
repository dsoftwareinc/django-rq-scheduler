# Django RQ Scheduler

[![Django CI](https://github.com/dsoftwareinc/django-rq-scheduler/actions/workflows/test.yml/badge.svg)](https://github.com/dsoftwareinc/django-rq-scheduler/actions/workflows/test.yml)
![badge](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/cunla/b756396efb895f0e34558c980f1ca0c7/raw/django-rq-scheduler-4.json)

[![badge](https://img.shields.io/pypi/dm/django-rq-scheduler)](https://pypi.org/project/django-rq-scheduler/)
[![Open Source Helpers](https://www.codetriage.com/dsoftwareinc/django-rq-scheduler/badges/users.svg)](https://www.codetriage.com/dsoftwareinc/django-rq-scheduler)

---

A database backed job scheduler for Django RQ.

!!! danger
    In v2023.3.0, django-rq-scheduler was refactored significantly to support
    calculation of parameters in runtime.
    
    You can now add a callable param to your scheduled job, and it will be
    calculated when the job is performed.

    1. It is highly recommended you save your existing database before upgrading!
    2. Once you upgraded, recreate your jobs.


!!! tip
    Starting v2023.1, requirement for rq_scheduler was removed and instead
    one of the django-rq workers should run with `--with-scheduler` parameter
    as mentioned [here](https://github.com/rq/django-rq#support-for-scheduled-jobs).
    
This allows remembering scheduled jobs, their parameters, etc.

Based on original [django-rq-scheduler](https://github.com/isl-x/django-rq-scheduler) - Now supports Django 4.0.



