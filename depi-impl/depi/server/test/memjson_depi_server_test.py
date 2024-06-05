import os
import unittest
import shutil
import sys
import json

sys.path.append("src")
sys.path.append("test")

from depi_server.db import depi_db_mem_json
import depi_pb2
import depi_server
import depi_server_test

from depi_server.model.depi_model import (ResourceRef)
from depi_server import depi_server

class TestDepiServerMemJson(depi_server_test.TestDepiServer):
    json_config_str = """
{
  "tools": {
    "git": { "pathSeparator": "/" },
    "webgme": { "pathSeparator": "/" },
    "git-gsn": { "pathSeparator": "/" }
  },
  "db": {
    "type": "memjson",
    "stateDir": ".teststate"
  },
  "server": {
    "authorization_enabled": false
  },
  "authorization": {
    "auth_def_file": "depi_auth.txt"
  },
  "audit": {
    "directory": "audit_test"
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
        json_config = json.loads(TestDepiServerMemJson.json_config_str)
        depi_server.config = depi_server.Config(json_config)
        state_dir = depi_server.config.dbConfig["stateDir"]
        if os.path.exists(state_dir):
            shutil.rmtree(state_dir)
        os.mkdir(state_dir)
        self.depi: depi_server.DepiServer = depi_server.DepiServer()

        main_branch = self.depi.db.getBranch("main")
        main_branch.saveBranchState()

    def reSetUp(self):
        json_config = json.loads(TestDepiServerMemJson.json_config_str)
        depi_server.config = depi_server.Config(json_config)
        state_dir = depi_server.config.dbConfig["stateDir"]
        self.depi: depi_server.DepiServer = depi_server.DepiServer()

        self.login()

    def test_create_tag(self):
        self.depi.db.createTag("testtag", "main")
        state_dir = depi_server.config.dbConfig["stateDir"]

        tag_path = state_dir+"/tags/testtag"
        self.assertTrue(os.path.exists(tag_path), tag_path+" should exist")

        tag_file = open(tag_path)
        tag_json = json.load(tag_file)
        tag_file.close()
        self.assertEqual(tag_json["branch"], "main", "tag branch in file should be named 'main'")
        self.assertEqual(tag_json["version"], 1, "tag version should be 1")

    def test_create_tag_then_change(self):
        self.depi.db.createTag("testtag", "main")
        state_dir = depi_server.config.dbConfig["stateDir"]

        tag_path = state_dir + "/tags/testtag"
        self.assertTrue(os.path.exists(tag_path), tag_path + " should exist")

        tag_file = open(tag_path)
        tag_json = json.load(tag_file)
        tag_file.close()
        self.assertEqual(tag_json["branch"], "main", "tag branch in file should be named 'main'")
        self.assertEqual(tag_json["version"], 1, "tag version should be 1")

        self.make_data_model()

        r1_rg, r1_res = self.r1
        self.assertIsNone(self.depi.db.tags["testtag"].getResource(ResourceRef.fromResourceGroupAndRes(r1_rg, r1_res)), "Tag branch should not contain created resource")

    def test_create_tag_then_load_as_branch(self):
        self.depi.db.createTag("testtag", "main")
        state_dir = depi_server.config.dbConfig["stateDir"]

        tag_path = state_dir + "/tags/testtag"
        self.assertTrue(os.path.exists(tag_path), tag_path + " should exist")

        tag_file = open(tag_path)
        tag_json = json.load(tag_file)
        tag_file.close()
        self.assertEqual(tag_json["branch"], "main", "tag branch in file should be named 'main'")
        self.assertEqual(tag_json["version"], 1, "tag version should be 1")

        self.make_data_model()

        r1_rg, r1_res = self.r1
        self.assertIsNone(self.depi.db.tags["testtag"].getResource(ResourceRef.fromResourceGroupAndRes(r1_rg, r1_res)), "Tag branch should not contain created resource")

# load the db from disk
        new_db = depi_db_mem_json.MemJsonDB(depi_server.config)
        tag_branch = new_db.getTag("testtag")
        self.assertIsNone(tag_branch.getResource(ResourceRef.fromResourceGroupAndRes(r1_rg, r1_res)), "Tag branch should not contain created resource")

    def test_tag_save_fails(self):
        self.depi.db.createTag("testtag", "main")
        state_dir = depi_server.config.dbConfig["stateDir"]

        tag_path = state_dir + "/tags/testtag"
        self.assertTrue(os.path.exists(tag_path), tag_path + " should exist")

        tag_file = open(tag_path)
        tag_json = json.load(tag_file)
        tag_file.close()
        self.assertEqual(tag_json["branch"], "main", "tag branch in file should be named 'main'")
        self.assertEqual(tag_json["version"], 1, "tag version should be 1")

        self.make_data_model()

        r1_rg, r1_res = self.r1
        self.assertFalse(self.depi.db.tags["testtag"].getResource(ResourceRef.fromResourceGroupAndRes(r1_rg, r1_res)), "Tag branch should not contain created resource")

        # load the db from disk
        new_db = depi_db_mem_json.MemJsonDB(depi_server.config)
        tag_branch = new_db.getTag("testtag")
        self.assertFalse(tag_branch.getResource(ResourceRef.fromResourceGroupAndRes(r1_rg, r1_res)), "Tag branch should not contain created resource")

        with self.assertRaises(Exception, msg="Saving a tag as a branch should cause an exception"):
            tag_branch.saveBranchState()

    def test_tag_then_branch_save_ok(self):
        self.depi.db.createTag("testtag", "main")
        state_dir = depi_server.config.dbConfig["stateDir"]

        tag_path = state_dir + "/tags/testtag"
        self.assertTrue(os.path.exists(tag_path), tag_path + " should exist")

        tag_file = open(tag_path)
        tag_json = json.load(tag_file)
        tag_file.close()
        self.assertEqual(tag_json["branch"], "main", "tag branch in file should be named 'main'")
        self.assertEqual(tag_json["version"], 1, "tag version should be 1")

        self.make_data_model()

        r1_rg, r1_res = self.r1
        self.assertFalse(self.depi.db.tags["testtag"].getResource(ResourceRef.fromResourceGroupAndRes(r1_rg, r1_res)),
                         "Tag branch should not contain created resource")

        # load the db from disk
        new_db = depi_db_mem_json.MemJsonDB(depi_server.config)
        tag_branch = new_db.getTag("testtag")
        self.assertFalse(tag_branch.getResource(ResourceRef.fromResourceGroupAndRes(r1_rg, r1_res)),
                         "Tag branch should not contain created resource")

        new_branch = new_db.createBranchFromTag("newbranch", "testtag")
        new_branch.saveBranchState()

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


if __name__ == '__main__':
    unittest.main()
