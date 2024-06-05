import depi
from depi_db_redis import RedisDB

db = RedisDB("depi")
depi = depi.Depi(db)

proj = depi.create_project("mark")
v1 = proj.get_version()
mgroup = v1.create_group("model", "webgme", "/", "1.0.0")
print(mgroup.endpoints)
cgroup = v1.create_group("code", "github", "/", "1.2.3")
mgroup.add_endpoint("foo")
mgroup.add_endpoint("bar")
mgroup.add_endpoint("baz")

cgroup.add_endpoint("quux")
cgroup.add_endpoint("fred")

v1.create_link("ref1", [mgroup.get_endpoint("bar"), cgroup.get_endpoint("quux")])

v1.save("2")

