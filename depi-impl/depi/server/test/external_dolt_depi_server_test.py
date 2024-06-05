import os
import json
import subprocess
import time

import depi_pb2_grpc
import grpc

import external_depi_server_test

class TestDepiServerDolt(external_depi_server_test.TestExternalDepiServer):
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
    "authorization_enabled": false,
    "insecure_port": 5150
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
        path = test_root+"/../../go-impl/depiserver"
        self.server_pipe = subprocess.Popen([path, "-test"], stdin=subprocess.PIPE)
        self.server_pipe.stdin.write(bytes(self.json_config_str, "utf-8"))
        self.server_pipe.stdin.write(bytes([0]))
        self.server_pipe.stdin.flush()
        time.sleep(1)
        self.channel = grpc.insecure_channel("127.0.0.1:5150")
        self.depi = depi_pb2_grpc.DepiStub(self.channel)

    def tearDown(self):
        self.server_pipe.stdin.close()
        time.sleep(1)
        self.server_pipe.wait(10)

    def reSetUp(self):
        self.server_pipe.stdin.close()
        test_root = os.path.dirname(__file__)
        path = test_root+"/../../go-impl/depiserver"
        self.server_pipe = subprocess.Popen([path, "-test"], stdin=subprocess.PIPE)
        self.server_pipe.stdin.write(bytes(self.json_config_str, "utf-8"))
        self.server_pipe.stdin.write(bytes([0]))
        self.server_pipe.stdin.flush()
        time.sleep(1)
        self.channel = grpc.insecure_channel("127.0.0.1:5150")
        self.depi = depi_pb2_grpc.DepiStub(self.channel)
        self.login()