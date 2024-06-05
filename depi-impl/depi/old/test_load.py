import depi
from depi_db_redis import RedisDB

db = RedisDB("depi")
depi = depi.Depi(db)

proj = depi.get_project("mark")
v = proj.get_version("2")

print(v)
for g in v.get_groups():
    print("got group {}\n".format(g.name))
