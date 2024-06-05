import grpc
import depi_pb2_grpc
import depi_pb2
import logging
from git import Repo
import argparse
import os.path
from urllib.parse import urlparse

from gsn_monitor import gsn_model_parser


class GsnToolAdaptor:
    def __init__(self, stub, user, password, project, toolid, repo, local=False):
        self.repo_dir = repo
        self.repo = Repo(repo, search_parent_directories=True)
        self.isLocal = local
        name = None
        if not local and len(self.repo.remotes) > 0:
            self.url = self.repo.remotes[0].url
            a = urlparse(self.url)
            name = os.path.basename(a.path)
        else:
            self.url = self.repo.working_dir
            name = os.path.basename(self.url)

        if project is None:
            project = name

        self.toolid = toolid
        self.project = project
        self.stub = stub

        response = stub.Login(depi_pb2.LoginRequest(user=user, password=password, project=project, toolId=toolid))
        if not response.ok:
            raise Exception(response.msg)

        self.depi_session_id = response.sessionId

    def get_current_repo_version(self):
        return self.repo.commit(self.repo.head).binsha.hex()

    def get_resource_name(self, filename):
        return os.path.basename(filename)

    def get_resource_group_name(self, git_url, working_dir, repo_dir):
        filename = repo_dir[len(working_dir)+1:]
        return git_url + "#" + filename;

    def do_add(self, args):
        resources = []

        curr_ver = self.get_current_repo_version()

        nodes = gsn_model_parser.get_gsn_nodes(self.repo_dir)
        rg_url = self.get_resource_group_name(self.url, self.repo.working_dir, self.repo_dir)

        for node in nodes:
            rr = depi_pb2.Resource(toolId = self.toolid,
                                   resourceGroupName = self.project,
                                   resourceGroupURL = rg_url,
                                   resourceGroupVersion = curr_ver,
                                   name = node.name,
                                   id = node.uuid,
                                   URL = node.url)
            resources.append(rr)

        resp = self.stub.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.depi_session_id,
                resources=resources)
        )

        if not resp.ok:
            raise Exception(resp.msg)

        print("Resources added to blackboard")
    
def run():
    logging.basicConfig()
    parser = argparse.ArgumentParser(
        prog="Depi Git",
        description="Synchronizes a Git repo with the Depi",
        epilog="")

    parser.add_argument("--depi", dest="depi_url", default="localhost:5150", help="The hostname:port of the depi")
    parser.add_argument("--user", dest="user", default="mark", help="The Depi user name")
    parser.add_argument("--password", dest="password", default="foo", help="The Depi password")
    parser.add_argument("--project", dest="project", default=None, help="The Depi project")
    parser.add_argument("--toolid", dest="toolid", default="git", help="The Depi tool ID")
    parser.add_argument("--repo", dest="repo", default=".", help="The Git repo to operate on")
    parser.add_argument("--local", dest="local", default=False, action=argparse.BooleanOptionalAction, help="The Git repo to operate on")
    parser.add_argument("op", default="add", help="The operation to perform")
    parser.add_argument("args", default=[], nargs="*", help="Additional operation arguments")

    args = parser.parse_args()

    with grpc.insecure_channel(args.depi_url) as channel:
        stub = depi_pb2_grpc.DepiStub(channel)

        adaptor = GsnToolAdaptor(stub, args.user, args.password,
                             args.project, args.toolid, args.repo,
                             args.local)


        if args.op == "add":
            adaptor.do_add(args.args)

if __name__ == "__main__":
    run()
