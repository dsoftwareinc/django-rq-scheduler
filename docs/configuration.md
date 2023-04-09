# Configure your django-rq-scheduler

## settings.py

All default settings for scheduler can be in one dictionary in `settings.py`:

```python
SCHEDULER = {
    'EXECUTIONS_IN_PAGE': 20,
    'DEFAULT_RESULT_TTL': 500,
    'DEFAULT_TIMEOUT': 300,  # 5 minutes
}
SCHEDULER_QUEUES = {
    'default': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
        'USERNAME': 'some-user',
        'PASSWORD': 'some-password',
        'DEFAULT_TIMEOUT': 360,
        'REDIS_CLIENT_KWARGS': {  # Eventual additional Redis connection arguments
            'ssl_cert_reqs': None,
        },
    },   
    'high': {
        'URL': os.getenv('REDISTOGO_URL', 'redis://localhost:6379/0'),  # If you're on Heroku
        'DEFAULT_TIMEOUT': 500,
    },
    'low': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
    }
}
```

### `EXECUTIONS_IN_PAGE`

Number of job executions to show in a page in a ScheduledJob admin view.

Default: `20`.

### `DEFAULT_RESULT_TTL`

Default time to live for job execution result.

Default: `600` (10 minutes).

### `DEFAULT_TIMEOUT`

Default timeout for job when it is not mentioned in queue.
Default: `300` (5 minutes).

### `SCHEDULER_QUEUES`
You can configure