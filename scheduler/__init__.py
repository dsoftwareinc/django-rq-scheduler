import importlib.metadata

__version__ = importlib.metadata.version('django-rq-scheduler')

from .decorators import job  # noqa: F401
