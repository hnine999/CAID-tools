import grpc
import depi_pb2_grpc
import depi_pb2
import logging
from git import Repo
import argparse
import os.path
from urllib.parse import urlparse

class GitToolAdaptor:
    def __init__(self, stub, user, password, project, toolid, repo, local=False):
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

    def get_start_commit(self, version):
        queue = [self.repo.commit(self.repo.head)]

        start_commit = None
        checked = set()
        roots = {}
        while len(queue) > 0:
            c = queue.pop()
            cver = c.binsha.hex()
            checked.add(cver)
            if version == cver:
                start_commit = c
                break
            if len(c.parents) == 0:
                if not cver in roots:
                    roots[cver] = c

            for cp in c.parents:
                if cp.binsha.hex() not in checked:
                    queue.append(cp)

        if start_commit is not None:
            return start_commit
        else:
            if len(roots) == 1:
                return list(roots.values())[0]
            else:
                raise Exception("Can't find version "+version+
                                " and unable to find a unique root")

    def get_current_repo_version(self):
        return self.repo.commit(self.repo.head).binsha.hex()

    def get_resource_name(self, filename):
        return os.path.basename(filename)

    def do_update(self, args):
        req = depi_pb2.GetTrackedResourcesRequest(
            sessionId = self.depi_session_id,
            toolId = self.toolid,
            name = self.project,
            URL = self.url
        )

        resp = self.stub.GetTrackedResources(req)
        if not resp.ok:
            raise Exception(resp.msg)

        resp_index = {}
        for r in resp.resources:
            resp_index[r.URL] = r


        new_version = self.get_current_repo_version()

        start_commit = self.get_start_commit(resp.version)
        diff = self.repo.commit(self.repo.head).diff(start_commit)
        updated = []
        for added in diff.iter_change_type('A'):
            if added.a_blob.path in resp_index:
                updated.append(resp_index[added.a_blob.path])
        for deleted in diff.iter_change_type('D'):
            if deleted.a_blob.path in resp_index:
                updated.append(resp_index[deleted.a_blob.path])
        for renamed in diff.iter_change_type('R'):
            if renamed.a_blob.path in resp_index:
                updated.append(resp_index[renamed.a_blob.path])
        for modified in diff.iter_change_type('M'):
            if modified.a_blob.path in resp_index:
                updated.append(resp_index[modified.a_blob.path])

        resourceGroup = depi_pb2.ResourceGroup(name = self.project,
                                               toolId = self.toolid,
                                               URL = self.url,
                                               version = new_version,
                                               resources = updated)

        resp = self.stub.UpdateResourceGroup(depi_pb2.UpdateResourceGroupRequest(
                                            sessionId = self.depi_session_id,
                                            resourceGroup = resourceGroup
                                        ))
        if not resp.ok:
            raise Exception(resp.msg)

        print("Update complete.")

    def do_add(self, args):
        resources = []
        curr_ver = self.get_current_repo_version()
        for arg in args:
            arg_fullpath = os.path.abspath(arg)
            repo_dir = self.repo.working_dir
            arg_fullpath = arg_fullpath[len(repo_dir)+1:]

            if os.path.isdir(arg_fullpath):
                arg_fullpath = arg_fullpath + "/"
            rr = depi_pb2.Resource(toolId = self.toolid,
                                   resourceGroupName = self.project,
                                   resourceGroupURL = self.url,
                                   resourceGroupVersion = curr_ver,
                                   name = self.get_resource_name(arg),
                                   id = os.path.basename(arg_fullpath),
                                   URL = arg_fullpath)
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
    parser.add_argument("op", default="update", help="The operation to perform")
    parser.add_argument("args", default=[], nargs="*", help="Additional operation arguments")

    args = parser.parse_args()

    with grpc.insecure_channel(args.depi_url) as channel:
        stub = depi_pb2_grpc.DepiStub(channel)

        adaptor = GitToolAdaptor(stub, args.user, args.password,
                             args.project, args.toolid, args.repo,
                             args.local)


        if args.op == "update":
            adaptor.do_update(args.args)
        elif args.op == "add":
            adaptor.do_add(args.args)

if __name__ == "__main__":
    run()
