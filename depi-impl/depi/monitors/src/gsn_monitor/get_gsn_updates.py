"""
Script for comparing states of gsn-models and report changes into depi.
"""
import os
import json
import traceback
from git import Repo
import depi_pb2

from gsn_monitor.gsn_model_parser import get_gsn_nodes, GSNNode

GSN_URL_MODEL_TAG = '#'
GSN_FILE_EXT = '.gsn'
TMP_DIR = '/tmp'
HEAD_DIR_NAME = 'head'
START_COMMIT_DIR_NAME = 'start_commit'
REVIEW_INFO_FILE = './.gsn-editor/review.json'


def _ensure_dir(directory_path):
    """
    Ensure the existence of a directory at the specified path. If the directory does not
    already exist, it will be created along with any necessary parent directories.

    Parameters:
    directory_path (str): The path to the directory that needs to be ensured.

    Returns:
    bool: True if the directory already existed or was successfully created, False otherwise.
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        return False

    return True


def get_gsn_updates(depi_client: 'DepiClient',
                    repo: Repo,
                    resource_groups: list[depi_pb2.ResourceGroup],
                    start_commit: str,
                    head_commit: str,
                    ignore_submodules: bool = False)\
        -> list[(depi_pb2.ResourceGroupChange, str)]:
    """
    Fetches updates from a Git repository

    Parameters:
    client (DepiStub): An instance of the DepiStub client used for communication with depi.
    repo (Repo): An object representing the Git repository to fetch updates from.
    start_commit (str): The commit identifier from which to start fetching updates.
    local_dir (str): The local directory where the retrieved files will be stored.

    Raises:
    SomeException: If there's an error during the update retrieval process.

    Returns:
    dict[]: list of changes that should be reported in depi.
    """
    parent_dir = os.path.join(TMP_DIR, os.path.basename(repo.git_dir))
    _ensure_dir(parent_dir)

    head_dir = os.path.join(parent_dir, HEAD_DIR_NAME)
    start_commit_dir = os.path.join(parent_dir, START_COMMIT_DIR_NAME)

    if ignore_submodules:
        diff = repo.commit(start_commit).diff(head_commit, ignore_submodules="all")
    else:
        diff = repo.commit(start_commit).diff(head_commit)

    altered_gsn_files = []

    for added in diff.iter_change_type('A'):
        altered_gsn_files.append(added.b_blob.path)

    for deleted in diff.iter_change_type('D'):
        altered_gsn_files.append(deleted.a_blob.path)

    for renamed in diff.iter_change_type('R'):
        altered_gsn_files.append(renamed.a_blob.path)
        altered_gsn_files.append(renamed.b_blob.path)

    for modified in diff.iter_change_type('M'):
        altered_gsn_files.append(modified.a_blob.path)

    gsn_dirs = set()
    for fpath in altered_gsn_files:
        if os.path.splitext(fpath)[1] == GSN_FILE_EXT:
            gsn_dirs.add(os.path.dirname(fpath))

    if not _ensure_dir(head_dir):
        head_repo = Repo.clone_from(repo.git_dir, head_dir)
        print(f'Head dir {head_dir} did not exist - cloned it.')
    else:
        head_repo = Repo(head_dir)
        head_repo.remotes[0].fetch()

    if not _ensure_dir(start_commit_dir):
        start_commit_repo = Repo.clone_from(repo.git_dir, start_commit_dir)
        print(f'Start-commit dir {start_commit_dir} did not exist - cloned it.')
    else:
        start_commit_repo = Repo(start_commit_dir)
        start_commit_repo.remotes[0].fetch()

    print('Checking out respective commits..')
    head_repo.git.checkout(head_commit)
    start_commit_repo.git.checkout(start_commit)
    print(f'gsn_dirs {gsn_dirs}')

    rg_updates = []
    for resource_group in resource_groups:
        gsn_dir = resource_group.URL.split(GSN_URL_MODEL_TAG)[-1]
        changes = []

        if gsn_dir in gsn_dirs:
            print(f'Resource Group {resource_group.name} had modified files.')
            pattern = depi_pb2.ResourceRefPattern(toolId=resource_group.toolId,
                                                  resourceGroupURL=resource_group.URL,
                                                  URLPattern='.*')
            resource_request = depi_pb2.GetResourcesRequest(sessionId=depi_client.session_id, patterns=[pattern])
            response = depi_client.stub.GetResources(resource_request)

            if not response.ok:
                raise Exception(response.msg)

            uuids = [resource.id for resource in response.resources]
            if len(uuids) == 0:
                print('But no tracked resources in depi - will only update version.')
            else:
                print(f'There are/(is) {len(uuids)} tracked resource(s) in depi - computing changes..')
                changes = get_node_changes(os.path.join(start_commit_dir, gsn_dir),
                                           os.path.join(head_dir, gsn_dir),
                                           uuids)
        else:
            print(f'Resource Group {resource_group.name} had NO modified files - will only update version.')

        review_file_path = os.path.join(head_dir, gsn_dir, REVIEW_INFO_FILE)

        if os.path.exists(review_file_path):
            with open(review_file_path, 'r') as json_file:
                review_data = json.load(json_file)
            review_branch = review_data['tag']
            print(f'Found review_branch "{review_branch}" in review.json')
            if review_branch:
                rg_updates.append((depi_pb2.ResourceGroupChange(name=resource_group.name,
                                                                toolId=resource_group.toolId,
                                                                URL=resource_group.URL,
                                                                version=head_commit,
                                                                resources=changes), review_branch))
        else:
            print('No review.json found - no tag.')

        rg_updates.append((depi_pb2.ResourceGroupChange(name=resource_group.name,
                                                        toolId=resource_group.toolId,
                                                        URL=resource_group.URL,
                                                        version=head_commit,
                                                        resources=changes), None))

    print('Updating resources group:\n', rg_updates)
    return rg_updates


def get_changes(change_type: depi_pb2.ChangeType, start_node: GSNNode, head_node: GSNNode or None):
    """
    Returns ResourceChange
    """
    return depi_pb2.ResourceChange(
        name=start_node.name,
        URL=start_node.url,
        id=start_node.uuid,
        changeType=change_type,
        new_name=head_node.name if head_node else None,
        new_URL=head_node.url if head_node else None,
        new_id=head_node.uuid if head_node else None
    )


def get_node_changes(model_dir_start: str, model_dir_head: str, uuids: list[str] or None) \
        -> list[depi_pb2.ResourceChange]:
    """
    Gets changes
    """
    result = []
    try:
        nodes_start: dict[str, GSNNode] = get_gsn_nodes(model_dir_start, True)
        nodes_head: dict[str, GSNNode] = get_gsn_nodes(model_dir_head, True)

        if not uuids:
            uuids = list(nodes_start.keys())
            print('uuids were not provided - will use start nodes as basis to find changes')

        for uuid in uuids:
            if uuid not in nodes_start:
                print(f'Node {uuid} not in previous depi state..?')
                if uuid not in nodes_head:
                    print(f'Node not in new state either, TODO: remove it.')
                else:
                    print(f'Node was in new state - will leave it as is.')

                continue

            start_node = nodes_start[uuid]
            if uuid not in nodes_head:
                result.append(get_changes(depi_pb2.ChangeType.Removed, start_node, None))
                continue

            start_node = nodes_start[uuid]
            head_node = nodes_head[uuid]

            if start_node.get_content_hash(nodes_start) != head_node.get_content_hash(nodes_head):
                result.append(get_changes(depi_pb2.ChangeType.Modified, start_node, head_node))
            elif start_node.url != head_node.url:
                result.append(get_changes(depi_pb2.ChangeType.Renamed, start_node, head_node))
    except Exception as e:
        print(f'Error: {e}: { traceback.format_exc()} ')
        print(f'An error occurred parsing the gsn-model, will only update resource group version!')
        result = []

    return result


if __name__ == '__main__':
    start_directory = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'tests', 'single')
    head_directory = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'tests', 'single_v2')
    node_changes = get_node_changes(start_directory, head_directory, None)

    print(node_changes)
