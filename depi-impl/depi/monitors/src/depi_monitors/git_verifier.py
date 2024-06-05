"""
Synchronizes a Git repo with the Depi
"""
import logging
import argparse
import os.path
import traceback

from git import Repo
from flask import Flask
import grpc
import depi_pb2_grpc
import depi_pb2
from gsn_monitor import gsn_model_parser

SUPPORTED_TOOLS = ['git', 'git-gsn']
verifier: 'GitVerifier'
app = Flask(__name__)


def get_current_repo_version(repo: Repo):
    return repo.commit(repo.head).binsha.hex()


class DepiClient:
    """
    Wrapper around depi-stub for a single session.
    """
    def __init__(self, channel):
        self.stub: depi_pb2_grpc.DepiStub = depi_pb2_grpc.DepiStub(channel)
        self.session_id: str = ''

    def login(self, user: str, password: str, project: str, tool_id: str):
        login_resp = self.stub.Login(depi_pb2.LoginRequest(user=user,
                                                           password=password,
                                                           project=project,
                                                           toolId=tool_id))
        if not login_resp.ok:
            raise Exception(login_resp.msg)

        self.session_id = login_resp.sessionId

    def logout(self):
        # TODO: We need to be able to logout.
        pass


class GitVerifier:
    """
    Class implementing functionality
    """

    def __init__(self, args):
        if args.toolid not in SUPPORTED_TOOLS:
            raise NotImplemented(f'Tool-id={args.toolid} not supported!')
        self.args = args
        self.tool_id: str = args.toolid
        self.user: str = args.userName
        self.password: str = args.password
        self.project: str = args.project
        self.depi_url: str = args.depi_url
        self.repos_dir: str = os.path.abspath(args.repos_dir)
        if not os.path.exists(self.repos_dir):
            os.makedirs(self.repos_dir)

        if args.port and args.port > 0:
            self.port: int = args.port

    def url_to_file_path(self, path: str):
        return os.path.join(self.repos_dir, path.replace("/", "_").replace("\\", "_").replace(":", "_"))

    def verify_resource_groups_from_git_repo(self, depi_client: DepiClient, tool_id: str, git_url: str, resource_groups: list[depi_pb2.ResourceGroup]):
        gsn_subdir = ""
        rg_url = git_url
        if tool_id == "git-gsn":
            pound_idx = git_url.index("#")
            if pound_idx >= 0:
                gsn_subdir = git_url[pound_idx+1:]
                git_url = git_url[:pound_idx]

        local_dir = self.url_to_file_path(git_url)
        print(f'local dir {local_dir}')
        if os.path.exists(local_dir):
            repo = Repo(local_dir)
            if len(repo.remotes) > 0:
                print("Fetching repo {}".format(git_url))
                repo.remotes[0].fetch('refs/heads/*:refs/heads/*')
            else:
                print("No remotes in repo {}".format(git_url))
                return
        else:
            print("Did not exist - cloning repo {}".format(git_url))
            repo = Repo.clone_from(git_url, local_dir, bare=(tool_id == "git"))

        new_version = get_current_repo_version(repo)

        req = depi_pb2.GetLastKnownVersionRequest(
            sessionId=depi_client.session_id,
            toolId=tool_id,
            name=resource_groups[0].name,
            URL=resource_groups[0].URL)

        resp = depi_client.stub.GetLastKnownVersion(req)

        if not resp.ok:
            print("Error getting last known version for {}: {}".format(git_url, resp.msg))
            return

        if resp.version == "":
            print("No version available for repo {}".format(git_url))
        else:
            print("Latest version for repo {} is {}".format(git_url, resp.version))
            print("Git version is {}".format(new_version))

        if resp.version == new_version:
            print("Versions of {} are the same, checking for inconsistencies".format(git_url))
        else:
            print("Version of {} in Depi needs to be updated".format(git_url))
            return

        resp = depi_client.stub.GetResources(
            depi_pb2.GetResourcesRequest(sessionId=depi_client.session_id,
                                         patterns=[
                                             depi_pb2.ResourceRefPattern(toolId=tool_id,
                                                                         resourceGroupURL=rg_url,
                                                                         URLPattern=".*")]))
        if not resp.ok:
            print("Unable to fetch resource group resources for {}: {}".format(
                git_url, resp.msg))
            return

        if tool_id == 'git':
            head_commit = repo.tree(repo.head)
            repo_files = set()
            repo_dirs = set()
            for item in head_commit.list_traverse():
                if item.type == "blob":
                    item_path = item.path
                    if not item_path.startswith("/"):
                        item_path = "/" + item_path
                    if item_path.endswith("/"):
                        repo_dirs.add(item_path)
                    else:
                        repo_files.add(item_path)

            all_ok = True
            for res in resp.resources:
                if not res.deleted and not res.URL.endswith("/") and res.URL not in repo_files:
                    all_ok = False
                    print("Resource {} is present in Depi but not in the git repo".format(res.URL))
            if all_ok:
                print("Depi resource group {} is in sync with git".format(git_url))

        elif tool_id == 'git-gsn':
            print("Loading model from {}".format(repo.working_dir + "/" + gsn_subdir))
            nodes = gsn_model_parser.get_gsn_nodes(repo.working_dir + "/" + gsn_subdir)
            gsn_paths = set()
            for node in nodes:
                gsn_paths.add(node.url)

            all_ok = True
            for res in resp.resources:
                if not res.deleted and not res.URL.endswith("/") and res.URL not in gsn_paths:
                    all_ok = False
                    print("Resource {} is present in Depi but not in the git repo".format(res.URL))
            if all_ok:
                print("Depi resource group {} is in sync with git".format(git_url))

    def run(self):
        self._run_verifier()

    def _run_verifier(self):
        with grpc.insecure_channel(self.depi_url) as channel:
            depi_client = DepiClient(channel)
            depi_client.login(self.user, self.password, self.project, self.tool_id)
            response = depi_client.stub.GetResourceGroups(
                depi_pb2.GetResourceGroupsRequest(sessionId=depi_client.session_id))

            for resource_group in response.resourceGroups:
#                if resource_group.toolId != self.tool_id:
#                    continue

                self.verify_resource_groups_from_git_repo(depi_client, resource_group.toolId, resource_group.URL, [resource_group])

def run():
    logging.basicConfig()
    parser = argparse.ArgumentParser(
        prog="Depi Git",
        description="Synchronizes a Git repo with the Depi",
        epilog="")

    parser.add_argument("--depi", dest="depi_url", default="localhost:5150", help="The hostname:port of the depi")
    parser.add_argument("--user", dest="user", default="mark", help="The Depi user name")
    parser.add_argument("--password", dest="password", default="mark", help="The Depi password")
    parser.add_argument("--project", dest="project", default=None, help="The Depi project")
    parser.add_argument("--toolid", dest="toolid", default="git", help="The Depi tool ID")
    parser.add_argument("--port", type=int, dest="port", default=3002,
                        help="If provided - will start a httpserver listening on the port instead of polling")
    parser.add_argument("--repos-dir", dest="repos_dir", default="./repos",
                        help="Repos are by default placed in %cwd%/repos")

    args = parser.parse_args()
    print(args)
    try:
        global verifier
        verifier = GitVerifier(args)
        verifier.run()
    except:
        traceback.print_exc()


if __name__ == "__main__":
    run()
