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

3. Configure Django RQ. See https://github.com/ui/django-rq#installation.
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

