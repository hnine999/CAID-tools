"""
Module for parsing .gsn-models and extracting information for determining changes in nodes.
"""
import hashlib
import json
import os
import sys
import glob
import itertools

from textx import metamodel_from_str
import textx.scoping.providers as scoping_providers
from textx.scoping.providers import FQN
    

NSP_COLLECTIONS_KEYS = ['goals', 'contexts', 'assumptions', 'justifications', 'solutions']
CHILDREN_KEY = 'nodedetails'
ATTRIBUTE_KEY = 'details'

NAMESPACE_KEYWORDS = ['GOALS', 'CONTEXTS', 'ASSUMPTIONS', 'JUSTIFICATIONS', 'SOLUTIONS']
NODE_KEYWORDS = ['goal', 'strategy', 'solution', 'context', 'assumption', 'justification']
MULTILINE_KEYWORDS=['summary','info']

def _read_metamodel(grammar_file_path=''):
    if not grammar_file_path:
        cur_dir = os.path.abspath(os.path.dirname(__file__))
        grammar_file_path = os.path.join(cur_dir, 'gsn.tx')

    with open(grammar_file_path, 'r', encoding='UTF-8') as file:
        grammar_str = file.read()

    return grammar_str


def _read_model(model_dir):
    model_files = glob.glob(os.path.join(model_dir, "*.gsn"))

    if len(model_files) == 0:
        print(' no model found')
        sys.exit(1)

    model_files_content = []
    for filename in model_files:
        with open(filename, 'r', encoding='UTF-8') as file:
            model_files_content.extend(file.readlines())
    
    return model_files_content

def get_indent(line):
    lwslen = len(line)-len(line.lstrip())
    return (int) (lwslen/4)

def check_end_multiline(in_multi_line, line):
    sline = line.strip()
    if in_multi_line:
        if (len(sline)==1 and sline[-1] == '\"' ):
            return True
        if (len(sline) > 1 and sline[-2]!='\\' and sline[-1] == '\"'):
            return True
    else:
        pos = sline.find("\"")
        posl = sline.rfind("\"")
        if (posl!=-1) and (posl != pos) and (sline[posl-1]!="\""):
            return True
    return False
    

def _update_model(model_str):
    updated_content = []
    cur_indent = 0
    in_multi_line = False
    for line in model_str:
        if (line.strip() == ""):
            updated_content.append(line)
            continue
        if (in_multi_line):
            updated_content.append(line)
            if (check_end_multiline(True,line)):
                in_multi_line = False
            continue
        new_indent = get_indent(line)
        if (new_indent < cur_indent):
            for i in range(cur_indent - new_indent):
                updated_content.append('}\n')
        cur_indent = new_indent
        first_token = line.lstrip().split()[0]
        updated_content.append(line)
        if ( first_token in NODE_KEYWORDS) or ( first_token in NAMESPACE_KEYWORDS):
            updated_content.append('{\n')
        if (first_token in MULTILINE_KEYWORDS):
            if (not check_end_multiline(False, line)):
                in_multi_line = True
            
    for k in range(cur_indent):
        updated_content.append('}\n')
    return ''.join(updated_content)
    

def _get_uuid(textx_node_or_ref):
    """
    Extracts the uuid of the node. If a ref node - it gets the uuid of the referenced node.
    """

    if hasattr(textx_node_or_ref, 'name'):
        textx_node = textx_node_or_ref
    else:
        textx_node = textx_node_or_ref.ref

    return textx_node.details[0].uuid.data


class GSNNode:
    """
    Simple wrapper class extracting all attributes and children from a textx node.
    """
    str_attribute_names = [
        'name',
        'uuid',
        'info',
        'summary',
        'status',
    ]

    def __init__(self, textx_node):
        self.name = textx_node.name
        self.uuid = _get_uuid(textx_node)

        textx_attributes = textx_node.details[0]

        self.info = ''
        if hasattr(textx_attributes, 'info') and hasattr(textx_attributes.info, 'data'):
            self.info = textx_attributes.info.data

        self.summary = ''
        if hasattr(textx_attributes, 'summary') and hasattr(textx_attributes.summary, 'data'):
            self.summary = textx_attributes.summary.data

        self.status = ''
        if hasattr(textx_node, 'status'):
            self.status = getattr(textx_node, 'status', 'NotReviewed')
            self.status = 'NotReviewed' if self.status is None else self.status

        self.url = ''
        textx_parent = textx_node
        while hasattr(textx_parent, 'name'):
            self.url = '/' + textx_parent.name + self.url
            textx_parent = getattr(textx_parent, 'parent')

        self.labels = []  # TODO: Extract and sort!
        self.child_uuids = []
        # Resolved on demand
        self.children = None
        self.content_hash = None

    def __repr__(self) -> str:
        return f'{self.name} - [{self.uuid}] @ {self.url}'

    def add_child_uuid(self, uuid):
        """
        Register child for node using uuid.
        Child can be either a ref node or contained node.
        """
        self.child_uuids.append(uuid)
        self.child_uuids.sort()

    def get_children(self, nodes: dict[str, 'GSNNode']) -> list['GSNNode']:
        """
        Resolves children for the given GSN nodes.

        Parameters:
        nodes (Dict[str, GSNNode]): A dictionary where keys are strings and values are GSNNode instances.

        Returns:
        GSNNode[]: list of direct children
        """
        if self.children:
            return self.children

        self.children = []

        for child_uuid in self.child_uuids:
            child_node = nodes[child_uuid]
            child_node.get_children(nodes)
            self.children.append(child_node)

        return self.children

    def get_content_hash(self, nodes: dict[str, 'GSNNode']) -> str:
        """
        Calculate a content hash for the current GSNNode and its descendants.
        N.B. This hash does not include the name or url - rename/move needs to be checked separately.

        This method recursively calculates a content hash based on the content of the current
        node and its child nodes. The provided dictionary 'nodes' should contain mappings
        from node names to GSNNode instances to allow traversing the hierarchy.

        Parameters:
        nodes (Dict[str, GSNNode]): A dictionary where keys are strings and values are GSNNode instances.
            This dictionary is used to resolve child nodes within the hierarchy.

        Returns:
        str: A unique content hash representing the content of the node and its descendants.
        """
        if self.content_hash:
            return self.content_hash

        json_repr = {
            # 'uuid': self.uuid,
            # 'name': self.name,
            # 'url': self.url,
            'info': self.info,
            'summary': self.summary,
            'status': self.status,
            'labels': self.labels,
            'children': [child.get_content_hash(nodes) for child in self.get_children(nodes)]
        }

        self.content_hash = hashlib.sha256((json.dumps(json_repr)).encode()).hexdigest()

        return self.content_hash

    def pretty_print(self):
        """
        Prints out node-data.
        """
        print('###############################')
        print('###  ' + self.url + '  ###')
        print('###############################')
        print('-== Attributes ==-')
        for attr_name in GSNNode.str_attribute_names:
            print(f' {attr_name} = {getattr(self, attr_name)}')

        print(f' labels = [{",".join(self.labels)}]')
        print('-== Children ==-')
        if len(self.child_uuids) > 0:
            print('  ' + '\n  '.join(self.child_uuids))
        else:
            print('  No children')

    def compare(self, other):
        """
        Compares nodes with other
        """
        return self.uuid == other.uuid


def _flatten_out_nodes_rec(textx_node):
    """
    Recursively gathers all nodes defined within node (including node itself).
    """
    node = GSNNode(textx_node)

    nodes = [node]
    for child in getattr(textx_node, CHILDREN_KEY, []):
        node.add_child_uuid(_get_uuid(child))
        name = getattr(child, 'name', None)
        if not name:
            # Quack-quack -> ref node
            continue

        nodes = itertools.chain(nodes, _flatten_out_nodes_rec(child))

    return nodes


def get_gsn_nodes(model_dir, as_dict: bool = False):
    """
    Retrieve GSN nodes from the specified model directory.

    Args:
        model_dir (str): The path to the directory containing GSN model files.
        as_dict (bool): If true - returns a dict with uuids as keys, otherwise a list of GSNNodes.

    Returns:
        list of GSNNode

    Example:
        model_dir = "/path/to/model/directory"
        get_gsn_nodes(model_dir)
    """
    metamodel_str = _read_metamodel()
    model_contents = _read_model(model_dir)
    model_str = _update_model(model_contents)
    #model_str = ''.join(model_contents)
    print(model_str)

    metamodel = metamodel_from_str(metamodel_str)
    metamodel.register_scope_providers({'*.*': FQN()})
    #metamodel.register_scope_providers(
    #    {"*.*": scoping_providers.FQNGlobalRepo(os.path.join(model_dir, '*.gsn'))})

    model = metamodel.model_from_str(model_str)

    nodes = []
    for nsp in model.assurancemodels:
        for collection_name in NSP_COLLECTIONS_KEYS:
            for textx_node in getattr(nsp, collection_name, []):
                nodes = itertools.chain(nodes, _flatten_out_nodes_rec(textx_node))

    if as_dict:
        nodes_dict = {}
        for node in nodes:
            nodes_dict[node.uuid] = node

        return nodes_dict

    return list(nodes)


###
### Usage:
### python get_gsn_nodes.py [gsn_files_folder]
### default value for gsn_files_folder is the ./tests/single-folder relative this dir
###
if __name__ == '__main__':
    FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'tests', 'single')

    if len(sys.argv) == 2:
        FOLDER = sys.argv[1]
    else:
        print(f'No folder provided using default {FOLDER}')

    if not os.path.exists(FOLDER):
        print(f'folder: {FOLDER} does not exist')
        sys.exit(1)

    gsn_nodes = get_gsn_nodes(FOLDER)

    for gsn_node in gsn_nodes:
        gsn_node.pretty_print()
        # print(gsn_node)

    print(f'Number of nodes {len(gsn_nodes)}')
