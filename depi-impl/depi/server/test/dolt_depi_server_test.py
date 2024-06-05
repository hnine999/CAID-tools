import os
import json

import depi_pb2
from depi_server import depi_server
import depi_server_test

from depi_server.model.depi_model import (ResourceRef)

class TestDepiServerDolt(depi_server_test.TestDepiServer):
    json_config_str = """
{
  "tools": {
    "git": { "pathSeparator": "/" },
    "webgme": { "pathSeparator": "/" },
    "git-gsn": { "pathSeparator": "/" }
  },
  "db": {
    "type": "dolt",
    "host": "127.0.0.1",
    "port": 3306,
    "user": "depitest",
    "password": "depitest",
    "database": "depitest",
    "pool_size": 1
  },
  "server": {
    "authorization_enabled": false
  },
  "authorization": {
    "auth_def_file": "depi_auth.txt"
  },
  "audit": {
    "directory": ""
  },
  "users": [
    { "name": "mark", "password": "mark", "auth_rules": ["readonly_git"] },
    { "name": "patrik", "password": "patrik", "auth_rules": ["readonly_res"] },
    { "name": "daniel", "password": "daniel", "auth_rules": ["readonly_res"] },
    { "name": "azhar", "password": "azhar", "auth_rules": ["readonly_res"] },
    { "name": "gabor", "password": "gabor", "auth_rules": ["readonly_res"] },
    { "name": "nag", "password": "nag", "auth_rules": ["readonly_res"] },
    { "name": "nobody", "password": "nobody", "auth_rules": [] }
  ]
}
    """

    def setUp(self):
        #os.system("./run_dolt_client.sh sql-client -u root < depi_mysql_test.sql")
        test_root = os.path.dirname(__file__)
        os.system(test_root+"/run_dolt_client.sh sql-client -u depiadmin -p depiadmin < "+test_root+"/depi_mysql_test.sql")
        json_config = json.loads(TestDepiServerDolt.json_config_str)
        depi_server.config = depi_server.Config(json_config)
        self.depi: depi_server.DepiServer = depi_server.DepiServer()

    def tearDown(self):
        self.depi.db.shutdown()

    def reSetUp(self):
        self.depi.db.shutdown()
        #os.system("./run_dolt_client.sh sql-client -u root < depi_mysql_test.sql")
        json_config = json.loads(TestDepiServerDolt.json_config_str)
        depi_server.config = depi_server.Config(json_config)
        self.depi: depi_server.DepiServer = depi_server.DepiServer()
        self.login()

    def test_create_tag(self):
        self.depi.db.createTag("testtag", "main")

        self.depi.db.createBranch("testbranch", "testtag")

    def test_create_tag_then_change(self):
        self.depi.db.createTag("testtag", "main")

        main_branch = self.depi.db.getBranch("main")

        self.make_data_model(main_branch)

        r1_rg, r1_res = self.r1

        self.depi.db.createBranch("testbranch", "testtag")
        tag_branch = self.depi.db.getBranch("testbranch")

        self.assertFalse(tag_branch.getResource(ResourceRef.fromResourceGroupAndRes(r1_rg, r1_res)), "Tag branch should not contain created resource")

    def test_get_last_known_version(self):
        self.login()
        self.make_data_model()

        req = depi_pb2.GetLastKnownVersionRequest(
            sessionId=self.session,
            toolId=self.r5[0].toolId,
            name=self.r5[0].name,
            URL=self.r5[0].URL
        )
        resp = self.depi.GetLastKnownVersion(req, None)
        self.assertTrue(resp.ok, "GetLastKnownVersion should succeed")
        self.assertEqual(resp.version, self.r5[0].version, "Version should be "+self.r5[0].version)
