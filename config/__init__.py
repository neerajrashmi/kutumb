import pymysql
from django.db.backends.mysql.base import DatabaseWrapper
pymysql.install_as_MySQLdb()
# DatabaseWrapper.check_database_version_supported = lambda self: None