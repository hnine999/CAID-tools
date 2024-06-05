"""
Synchronizes a Git repo with the Depi
"""
import logging
import argparse
import os.path
import time
import sys
import traceback

import git
from git import Repo
from flask import Flask, request, jsonify

sys.path.append("src")

import grpc
import depi_pb2_grpc
import depi_pb2

from gsn_monitor.get_gsn_updates import get_gsn_updates, GSN_URL_MODEL_TAG

SUPPORTED_TOOLS = ['git', 'git-gsn']
monitor: 'GitMonitor'
app = Flask(__name__)


class ResourceGroupInfo:
    """
    Parsed pieces of a git resource-group url.
    """
    def __init__(self, resource_group_url) -> None:
        rg_info = parse_resource_group_url(resource_group_url)
        self.host = rg_info['host']
        self.owner = rg_info['owner']
        self.name = rg_info['name']
        self.host_name = rg_info['host_name']
        self.host_prefix = rg_info['host_prefix']
        self.is_ssh = rg_info['is_ssh']


def parse_resource_group_url(resource_group_url):
    # git@git.isis.vanderbilt.edu:aa-caid/depi-impl.git
    # http://localhost:3001/patrik/c-sources.git
    # git@github.com:webgme/webgme.git
    # https://git.isis.vanderbilt.edu/aa-caid/depi-impl.git
    # git-vandy:VUISIS/p-state-visualizer.git

    last_slash_index = resource_group_url.rfind('/')
    host_divider_index = 0
    host = ''
    host_name = ''
    host_prefix = ''
    is_ssh = False

    is_http = resource_group_url.startswith('http://')
    is_https = resource_group_url.startswith('https://')

    if is_http or is_https:
        is_ssh = False
        host_divider_index = resource_group_url.rfind('/', 0, last_slash_index - 1)
        host = resource_group_url[:host_divider_index]
        if is_http:
            host_prefix = 'http://'
            host_name = host[len('http://'):]
        else:
            host_prefix = 'https://'
            host_name = host[len('https://'):]
    else:
        # ssh
        is_ssh = True
        host_divider_index = resource_group_url.rfind(':')
        host = resource_group_url[:host_divider_index]
        at_index = host.find('@')
        if at_index > -1:
            host_prefix = host[:at_index + 1]
            host_name = host[at_index + 1:]
        else:
            host_name = host
            host_prefix = ''

    owner = resource_group_url[host_divider_index + 1:last_slash_index]
    name = resource_group_url[last_slash_index + 1:].replace('.git', '')

    return {'host': host, 'owner': owner, 'name': name, 'host_name': host_name, 'host_prefix': host_prefix,
            'is_ssh': is_ssh}


def get_start_commit(repo: Repo, version: str):
    queue = [repo.commit(repo.head)]

    start_commit = None
    checked = set()
    roots = {}
    while len(queue) > 0:
        commit = queue.pop()
        cver = commit.binsha.hex()
        checked.add(cver)
        if version == cver:
            start_commit = commit
            break
        if len(commit.parents) == 0:
            if cver not in roots:
                roots[cver] = commit

        for parent_commit in commit.parents:
            if parent_commit.binsha.hex() not in checked:
                queue.append(parent_commit)

    if start_commit is not None:
        return start_commit

    if len(roots) == 1:
        return list(roots.values())[0]

    raise Exception(f"Can't find version {version} and unable to find a unique root")


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


class GitMonitor:
    """
    Class implementing functionality
    """

    def __init__(self, args):
        if args.toolid not in SUPPORTED_TOOLS:
            raise NotImplemented(f'Tool-id={args.toolid} not supported!')
        self.args = args
        self.tool_id: str = args.toolid
        self.user: str = args.user
        self.password: str = args.password
        self.project: str = args.project
        self.depi_url: str = args.depi_url
        self.repos_dir: str = os.path.abspath(args.repos_dir)
        self.use_ssl = args.ssl
        self.cert = args.cert
        self.ssl_target_name = args.ssl_target_name
        self.ignore_submodules = args.ignore_submodules
        self.git_platform = args.git_platform
        if not os.path.exists(self.repos_dir):
            os.makedirs(self.repos_dir)

        if args.port and args.port > 0:
            self.port: int = args.port

    def url_to_file_path(self, path: str):
        return os.path.join(self.repos_dir, path.replace("/", "_").replace("\\", "_").replace(":", "_"))

    def update_resource_groups_from_git_repo(self, depi_client: DepiClient, git_url: str,
                                             resource_groups: list[depi_pb2.ResourceGroup]):
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
            repo = Repo.clone_from(git_url, local_dir, bare=True)

        new_version = get_current_repo_version(repo)

        req = depi_pb2.GetLastKnownVersionRequest(
            sessionId=depi_client.session_id,
            toolId=self.tool_id,
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
            print("Versions of {} are the same".format(git_url))
            return

        start_commit = get_start_commit(repo, resp.version)

        if self.tool_id == 'git':
            resource_group_updates = get_git_file_updates(repo, resource_groups[0], start_commit, new_version, self.ignore_submodules)
        elif self.tool_id == 'git-gsn':
            resource_group_updates = get_gsn_updates(depi_client,
                                                     repo,
                                                     resource_groups,
                                                     start_commit,
                                                     new_version,
                                                     self.ignore_submodules)
        else:
            raise NotImplemented(f'Unsupported repository type {self.tool_id}')

        for resource_group_update, branch in resource_group_updates:
            resp = depi_client.stub.UpdateResourceGroup(depi_pb2.UpdateResourceGroupRequest(
                sessionId=depi_client.session_id,
                resourceGroup=resource_group_update,
                updateBranch=branch))
            if not resp.ok:
                raise Exception(resp.msg)

            print(f"Updated {resource_group_update.URL}")

    def run(self):
        if self.port:
            from waitress import serve
            print(f'Routes: [POST] http://0.0.0.0:{self.port}/webhook')
            serve(app, host="0.0.0.0", port=self.port)
        else:
            self._run_poller()

    def open_channel(self):
        if self.use_ssl:
            options = None
            if self.ssl_target_name is not None and len(self.ssl_target_name) > 0:
                options = (("grpc.ssl_target_name_override", self.ssl_target_name),)

            if self.cert is not None and len(self.cert) > 0:
                with open(self.cert, "rb") as file:
                    cert_pem = file.read()
                cred = grpc.ssl_channel_credentials(root_certificates=cert_pem)
            else:
                cred = grpc.ssl_channel_credentials()
            return grpc.secure_channel(self.depi_url, cred, options=options)
        else:
            return grpc.insecure_channel(self.depi_url)

    def _run_poller(self):
        while True:
            with grpc.insecure_channel(self.depi_url) as channel:
                depi_client = DepiClient(channel)
                depi_client.login(self.user, self.password, self.project, self.tool_id)
                response = depi_client.stub.GetResourceGroups(
                    depi_pb2.GetResourceGroupsRequest(sessionId=depi_client.session_id))

                for resource_group in response.resourceGroups:
                    if resource_group.toolId != self.tool_id:
                        continue

                    self.update_resource_groups_from_git_repo(resource_group.URL, [resource_group])

                time.sleep(5)

    def handle_update(self, git_url: str):
        print('\n### Incoming update URL:', git_url, '###')
        repo_info = ResourceGroupInfo(git_url)

        with grpc.insecure_channel(self.depi_url) as channel:
            depi_client = DepiClient(channel)
            depi_client.login(self.user, self.password, self.project, self.tool_id)

            response = depi_client.stub.GetResourceGroups(
                depi_pb2.GetResourceGroupsRequest(sessionId=depi_client.session_id))

            resource_groups = []
            for resource_group in response.resourceGroups:
                if self.tool_id != resource_group.toolId:
                    continue

                print('Matching against Resource-Group [', resource_group.toolId, '] URL:', resource_group.URL)
                if self.tool_id == 'git-gsn':
                    rg_info = ResourceGroupInfo(resource_group.URL.split(GSN_URL_MODEL_TAG)[0])
                else:
                    rg_info = ResourceGroupInfo(resource_group.URL)

                if rg_info.owner == repo_info.owner and rg_info.name == repo_info.name:
                    resource_groups.append(resource_group)
                    print('Matched!')
                    if self.tool_id == 'git':
                        break
                else:
                    print('Did NOT match!')

            if len(resource_groups) > 0:
                self.update_resource_groups_from_git_repo(depi_client, git_url, resource_groups)
            else:
                print(f'Could not find resource-group for repo {git_url}, skipping..')


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        git_url = ''
        if monitor.git_platform in ['gitea', 'github']:
            if 'repository' not in data or 'clone_url' not in data['repository']:
                print(data)
                raise Exception('gitea/github: missing repository.clone_url')
            git_url = data['repository']['clone_url']
        elif monitor.git_platform == 'gitlab':
            if 'repository' not in data or 'git_http_url' not in data['repository']:
                print(data)
                raise Exception('gitlab: missing repository.git_http_url')
        else:
            print(data)
            raise Exception('unsupported git_platform "' + monitor.git_platform + '".')

        monitor.handle_update(git_url)
        result = {'message': 'JSON data received and processed successfully'}
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        error_msg = {'error': str(e)}
        return jsonify(error_msg), 400


def get_resource_update(old_blob, new_blob, change_type):
    url = '/' + old_blob.path
    new_url = '/' + new_blob.path
    return depi_pb2.ResourceChange(
        name=os.path.basename(url),
        URL=url,
        id=url,
        changeType=change_type,
        new_name=os.path.basename(new_url),
        new_URL=new_url,
        new_id=new_url)


def get_git_file_updates(repo: git.Repo, resource_group: depi_pb2.ResourceGroup, start_commit: str, head_commit: str,
                         ignore_submodules: bool = False):
    if ignore_submodules:
        diff = repo.commit(start_commit).diff(head_commit, ignore_submodules="all")
    else:
        diff = repo.commit(start_commit).diff(head_commit)
    updates = []
    for added in diff.iter_change_type('A'):
        updates.append(get_resource_update(added.b_blob, added.b_blob, depi_pb2.ChangeType.Added))

    for deleted in diff.iter_change_type('D'):
        updates.append(get_resource_update(deleted.a_blob, deleted.a_blob, depi_pb2.ChangeType.Removed))

    for renamed in diff.iter_change_type('R'):
        updates.append(get_resource_update(renamed.a_blob, renamed.b_blob, depi_pb2.ChangeType.Renamed))

    for modified in diff.iter_change_type('M'):
        updates.append(get_resource_update(modified.a_blob, modified.b_blob, depi_pb2.ChangeType.Modified))

    return [(depi_pb2.ResourceGroupChange(name=resource_group.name,
                                          toolId=resource_group.toolId,
                                          URL=resource_group.URL,
                                          version=head_commit,
                                          resources=updates), None)]


def run():
    logging.basicConfig()
    parser = argparse.ArgumentParser(
        prog="Depi Git",
        description="Synchronizes a Git repo with the Depi",
        epilog="")

    parser.add_argument("--depi", dest="depi_url", default="localhost:5150", help="The hostname:port of the depi")
    parser.add_argument("--ssl", dest="ssl", action="store_true", help="If true¸ use SSL for connection")
    parser.add_argument("--ssl-target-name", dest="ssl_target_name", default="",
                        help="Specify the name expected to be in the host ssl certificate")
    parser.add_argument("-cert", "--cert", dest="cert",
                        default="", help="A certificate authority for a self-signed server certificate")
    parser.add_argument("--user", dest="user", default="mark", help="The Depi user name")
    parser.add_argument("--password", dest="password", default="mark", help="The Depi password")
    parser.add_argument("--project", dest="project", default=None, help="The Depi project")
    parser.add_argument("--toolid", dest="toolid", default="git", help="The Depi tool ID - ('git', 'git-gsn').")
    parser.add_argument("--ignore-submodules", dest="ignore_submodules",
                        help="Should submodules be ignored when looking for changes", action="store_true")
    parser.add_argument("--port", type=int, dest="port", default=3002,
                        help="If provided - will start a httpserver listening on the port instead of polling")
    parser.add_argument("--git-platform", dest="git_platform", default="gitea",
                        help="If using webhook, specifiy git-platform so payload can be interpreted correctly ('gitea', 'gitlab', 'github').")
    parser.add_argument("--repos-dir", dest="repos_dir", default="./repos",
                        help="Repos are by default placed in %cwd%/repos")

    args = parser.parse_args()
    print(args)
    while True:
        try:
            global monitor
            monitor = GitMonitor(args)
            monitor.run()
        except:
            traceback.print_exc()
        time.sleep(1)


if __name__ == "__main__":
    run()
