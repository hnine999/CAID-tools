import depi
from depi_db_redis import RedisDB

db = RedisDB("depi")
db.clean()
