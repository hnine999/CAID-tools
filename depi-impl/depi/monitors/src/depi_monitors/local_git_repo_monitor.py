import grpc
import depi_pb2_grpc
import depi_pb2
import logging
from git import Repo
import argparse
import os.path
import time
import traceback
from urllib.parse import urlparse


# from gsn_monitor.get_gsn_updates import get_gsn_updates

class GitToolAdaptor:
    def __init__(self, args):
        self.stub = None
        self.depi_session_id = None
        self.args = args

        self.toolId = args.toolid
        self.project = args.project
        self.depi_url = args.depi_url

    def get_start_commit(self, repo, version):
        queue = [repo.commit(repo.head)]

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
                raise Exception("Can't find version " + version +
                                " and unable to find a unique root")

    def get_current_repo_version(self, repo):
        return repo.commit(repo.head).binsha.hex()

    def get_resource_name(self, filename):
        return os.path.basename(filename)

    def is_remote(self, url):
        return ':' in url

    def path_to_filename(self, path):
        return path.replace("/", "_").replace("\\", "_")

    def update_resource_group(self, rg):
        local_dir = None
        if self.is_remote(rg.URL):
            # Use the other monitor for remote repositories
            return
        else:
            print("Using local repo {}".format(rg.URL))
            local_dir = rg.URL
            repo = Repo(rg.URL, search_parent_directories=True)

        name = None

        if self.is_remote(rg.URL) and len(repo.remotes) > 0:
            self.url = repo.remotes[0].url
            a = urlparse(self.url)
            name = os.path.basename(a.path)
        else:
            self.url = repo.working_dir
            name = os.path.basename(self.url)

        new_version = self.get_current_repo_version(repo)

        req = depi_pb2.GetLastKnownVersionRequest(
            sessionId=self.depi_session_id,
            toolId=self.toolId,
            name=rg.name,
            URL=rg.URL)

        resp = self.stub.GetLastKnownVersion(req)

        if resp.version == "":
            print("No version available for repo {}".format(rg.URL))
        else:
            print("Latest version for repo {} is {}".format(rg.URL, resp.version))
            print("Git version is {}".format(new_version))
        if not resp.ok:
            print("Error getting last known version for {}: {}".format(rg.URL, resp.msg))
            return

        if resp.version == new_version:
            print("Versions of {} are the same".format(rg.URL))
            return

        start_commit = self.get_start_commit(repo, resp.version)
        updated = get_git_file_updates(repo, start_commit)

        if len(updated) > 0:
            resourceGroup = depi_pb2.ResourceGroupChange(name=name,
                                                         toolId=self.toolId,
                                                         URL=self.url,
                                                         version=new_version,
                                                         resources=updated)

            resp = self.stub.UpdateResourceGroup(depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.depi_session_id,
                resourceGroup=resourceGroup
            ))
            if not resp.ok:
                raise Exception(resp.msg)

            print("Updated {}".format(rg.URL))

    def run(self):
        with grpc.insecure_channel(self.depi_url) as channel:
            self.stub = depi_pb2_grpc.DepiStub(channel)

            response = self.stub.Login(
                depi_pb2.LoginRequest(user=self.args.userName, password=self.args.password, project=self.args.project,
                                      toolId=self.args.toolid))
            if not response.ok:
                print(response.msg)
                return

            self.depi_session_id = response.sessionId

            while True:
                response = self.stub.GetResourceGroups(
                    depi_pb2.GetResourceGroupsRequest(sessionId=self.depi_session_id))

                for rg in response.resourceGroups:
                    if rg.toolId != self.toolId:
                        continue

                    self.update_resource_group(rg)

                time.sleep(5)


def get_resource_update(git_change, change_type):
    url = '/' + git_change.a_blob.path
    new_url = '/' + git_change.b_blob.path
    return depi_pb2.ResourceChange(
        name=os.path.basename(url),
        URL=url,
        id=url,
        changeType=change_type,
        new_name=os.path.basename(new_url),
        new_URL=new_url,
        new_id=new_url)


def get_git_file_updates(repo, start_commit):
    diff = repo.commit(repo.head).diff(start_commit)
    updates = []
    for added in diff.iter_change_type('A'):
        updates.append(get_resource_update(added, depi_pb2.ChangeType.Added))

    for deleted in diff.iter_change_type('D'):
        updates.append(get_resource_update(deleted, depi_pb2.ChangeType.Removed))

    for renamed in diff.iter_change_type('R'):
        updates.append(get_resource_update(renamed, depi_pb2.ChangeType.Renamed))

    for modified in diff.iter_change_type('M'):
        updates.append(get_resource_update(modified, depi_pb2.ChangeType.Modified))

    return updates


def run():
    parser = argparse.ArgumentParser(
        prog="Depi Git",
        description="Synchronizes a Git repo with the Depi",
        epilog="")

    parser.add_argument("--depi", dest="depi_url", default="localhost:5150", help="The hostname:port of the depi")
    parser.add_argument("--user", dest="user", default="mark", help="The Depi user name")
    parser.add_argument("--password", dest="password", default="foo", help="The Depi password")
    parser.add_argument("--project", dest="project", default=None, help="The Depi project")
    parser.add_argument("--toolid", dest="toolid", default="git", help="The Depi tool ID")

    args = parser.parse_args()

    if args.toolid != 'git':
        raise Exception(f'Invalid toolid provided {args.toolid} only git valid for local repos.')

    while True:
        try:
            client = GitToolAdaptor(args)
            client.run()

        except:
            traceback.print_exc()
        time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig()
    run()
