Django RQ Scheduler
===================
[![Django CI](https://github.com/dsoftwareinc/django-rq-scheduler/actions/workflows/test.yml/badge.svg)](https://github.com/dsoftwareinc/django-rq-scheduler/actions/workflows/test.yml)
![badge](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/cunla/b756396efb895f0e34558c980f1ca0c7/raw/django-rq-scheduler-4.json)

[![badge](https://img.shields.io/pypi/dm/django-rq-scheduler)](https://pypi.org/project/django-rq-scheduler/)
[![Open Source Helpers](https://www.codetriage.com/dsoftwareinc/django-rq-scheduler/badges/users.svg)](https://www.codetriage.com/dsoftwareinc/django-rq-scheduler)

Documentation can be found in https://django-rq-scheduler.readthedocs.io/en/latest/

> Notice:
> 
> In v2023.3.0, django-rq-scheduler was refactored significantly to support
> calculation of parameters in runtime.
> 
> You can now add a callable param to your scheduled job, and it will be
> calculated when the job is performed.
> 
> 1. It is highly recommended you save your existing database before upgrading!
> 2. Once you upgraded, recreate your jobs.

> Notice:
> 
> Starting v2023.1, requirement for rq_scheduler was removed and instead
> one of the django-rq workers should run with `--with-scheduler` parameter
> as mentioned [here](https://github.com/rq/django-rq#support-for-scheduled-jobs).


# Sponsor

django-rq-scheduler is developed for free.

You can support this project by becoming a sponsor using [this link](https://github.com/sponsors/cunla).


## Security contact information

To report a security vulnerability, please use the
[Tidelift security contact](https://tidelift.com/security).
Tidelift will coordinate the fix and disclosure.