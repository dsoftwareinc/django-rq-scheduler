Django RQ Scheduler
===================
[![Django CI](https://github.com/dsoftwareinc/django-rq-scheduler/actions/workflows/test.yml/badge.svg)](https://github.com/dsoftwareinc/django-rq-scheduler/actions/workflows/test.yml)
![badge](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/cunla/b756396efb895f0e34558c980f1ca0c7/raw/django-rq-scheduler-4.json)
[![badge](https://img.shields.io/pypi/dm/django-rq-scheduler)](https://pypi.org/project/django-rq-scheduler/)
[![Open Source Helpers](https://www.codetriage.com/dsoftwareinc/django-rq-scheduler/badges/users.svg)](https://www.codetriage.com/dsoftwareinc/django-rq-scheduler)

Documentation can be found in https://django-rq-scheduler.readthedocs.io/en/latest/

> **Note**: Starting v2023.5.0, django-rq-scheduler does not require django-rq.
> All required views were migrated. Make sure to read the installation notes in the documentation.
> Particularly how to set up your `urls.py`.

> **Note** Starting v2023.1, requirement for rq_scheduler was removed and instead
> one of the django-rq workers should run with `--with-scheduler` parameter
> as mentioned [here](https://github.com/rq/django-rq#support-for-scheduled-jobs).


# Sponsor

django-rq-scheduler is developed for free.

You can support this project by becoming a sponsor using [this link](https://github.com/sponsors/cunla).


