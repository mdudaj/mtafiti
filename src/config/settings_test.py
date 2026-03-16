from .settings import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ['*']

DB_NAME = os.environ.get('POSTGRES_DB', 'mtafiti_test')  # noqa: F405

DATABASES['default']['NAME'] = DB_NAME  # noqa: F405
