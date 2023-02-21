import importlib.metadata

__version__ = importlib.metadata.version('django-rq-scheduler')

import logging

logger = logging.Logger(__name__)
