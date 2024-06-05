import copy

class GroupChange:
    RENAMED=1
    DELETED=2

    def __init__(self, name, change_type, new_name=""):
        self.name = name
        self.change_type = change_type
        self.new_name = new_name

class Endpoint:
    """An endpoint in a group

    Attributes
    ----------
    group : str
        The group this endpoint belongs to
    endpoint_name : str
        The name of this endpoint in the group
    """
    def __init__(self, group, endpoint_name):
        """
        Parameters:
        group : str
            The name of the group
        endpoint_name : str
            The name of the endpoint
        """
        self.group = group
        self.endpoint_name = endpoint_name

class Group:
    """A group, which has a name, an app-id, a version within the app,
    and a map of endpoints that can be linked to endpoints in other groups

    Attributes
    ----------
    name : str
        The name of this group
    app_id : str
        The type of application this group belongs to (e.g. "github", "webgme")
    path : str
        The path of this group within the application
    version : str
        The version of this group within the application

    Methods
    -------
    add_endpoint(name : str)
        Adds an endpoint to the group
    delete_endpoint(name : str)
        Deletes an endpoint from the group
    get_endpoints()
        Returns a list of the group's endpoints
    """
    def __init__(self, name, app_id, path, version, endpoints=None):
        """
        Parameters
        ----------
        name : str
            The name of the group
        app_id : str
            The application that this group belongs to
        path : str
            The path of this group within the application
        version : str
            The version of this group within the application
        """
        self.name = name
        self.app_id = app_id
        self.version = version
        self.path = path
        if endpoints is None:
            self.endpoints = []
        else:
            self.endpoints = endpoints
        self.deleted_endpoints = []
        self.is_changed = False

    def get_endpoint(self, name):
        if name in self.endpoints:
            return Endpoint(self, name)
        else:
            return None

    def add_endpoint(self, name):
        """
        Adds an endpoint, which is the name of an item in the group

        Parameters
        ----------
        name : str
            The name of the endpoint to add
        """
        if name not in self.endpoints:
            self.endpoints.append(name)
        if name in self.deleted_endpoints:
            del self.deleted_endpoints[name]
        self.is_changed = True

    def delete_endpoint(self, name):
        """
        Deletes an endpoint

        Parameters
        ----------
        name : str
            The name of the endpoint to delete
        """
        self.is_changed = True
        if name in self.endpoints:
            del self.endpoints[name]
        if name not in self.deleted_endpoints:
            self.deleted_endpoints.append(name)

    def get_endpoints(self):
        """Returns a list of all the endpoints this group has"""
        return self.endpoints[:]

class Link:
    """
    A link between multiple endpoints in groups

    Attributes
    ----------
    name : str
        The name of the link
    endpoints : list
        A list of endpoints participating in this link
    """
    def __init__(self, name, endpoints, is_new=False):
        self.name = name
        self.endpoints = endpoints
        self.is_new = is_new
        self.is_deleted = False
        self.dirty = False

class Version:
    """A version of a project, which can contain groups and links

    Attributes
    ----------
    parent : Project
        The project this version belongs to
    version : str
        The version number that this version had when it
        was retrieved from the database
    is_new : bool
        This is the first version in a new project

    Methods
    -------
    create_group(name, app_id, path, version)
        Creates a new group
    get_group(name, app_id=None)
        Retrieves a group by name and optional app_id
    create_link(self, group_a, endpoint_a, group_b, endpoint_b)
        Creates a link between two endpoints
    delete_link(self, link):
        deletes a link between two group endpoints
    get_endpoint_links(self, group, my_endpoint)
        Locates all the links between the named group endpoint and another endpoint
    get_links_by_app(self, target_app)
        Locates all the links in this group that link to resources in the named target app
    save()
        Saves this version to the database under a new version number

    """
    def __init__(self, db, parent, version="", groups=None, tags=None, links=None, is_new=False):
        """
        Parameters
        ----------
        parent : Parent
            The project this version belongs to
        version : str
            The version number that this version had when it was
            retrieved from the database
        tags : list
            The tags associated with this version
        """
        self.db = db
        self.parent = parent
        self.version = version
        self.is_new = is_new
        if links is None:
            self.links = {}
        else:
            self.links = links
        if tags is None:
            self.tags = []
        else:
            self.tags = tags
        self.deleted_tags = []
        if groups is None:
            self.groups = {}
        else:
            self.groups = groups

    def create_group(self, name, app_id, path, version):
        """Creates a new group within this version. A group typically represents
        some kind of repository. In addition to having a name, a group has an app_id,
        which indicates what kind of app the group represents (e.g. git for apps
        stored in Git, webgme for apps stored in WebGME). A group's version is
        the version that the group has within its particular app. For instance, a
        commit id in Git.

        Parameters
        ----------
        name : str
            The name of the group
        app_id : str
            The application this group is associated with
        path : str
            The path of the group within the application
        version : str
            The version of the group within the application


        Returns
        -------
        Group
            The group that has been created
        """
        group = Group(name, app_id, path, version)
        self.groups[name] = group
        return group

    def get_group(self, name, app_id=None):
        """Retrieves a group by name

        Parameters
        ----------
        name : str
            The name of the group to retrieve
        app_id : str (default = None)
            An optional application id that the group should have


        Returns
        -------
        Group
            The named group, or None if no such group exists
        """
        if name in self.groups:
            group = self.groups[name]
            if group.app_id == app_id:
                return group
        return None

    def get_groups(self):
        g = []
        for k in self.groups:
            g.append(self.groups[k])
        return g
            
    def create_link(self, name, endpoints=None):
        """Creates a link between an endpoint in this group, and an endpoint
        in another group. An endpoint
        in a group is an item that can be associated with one or more endpoints
        in another group. The basic idea is that this would let you associate
        a file in Git with an object in WebGME, and keep the association even
        if the file is renamed.

        Parameters
        ----------
        name : str
            The name of the link
        endpoints : list
            A list of endpoints that this link refers to

        Returns
        -------
        Link
            The created link
        """
        ep = endpoints
        if ep is None:
            ep = []
        l = Link(name, ep, True)
        self.links[name] = l
        return l

    def delete_link(self, link):
        """deletes a link between two group endpoints

        Parameters
        ----------
        link : Link
            The link to delete
        """
        link.is_deleted = True

    def get_links_by_endpoint(self, group, my_endpoint):
        """Locates all the links between the named group endpoint and another endpoint

        Parameters
        ----------
        group : Group
            The group containing the endpoint whose links are being fetched
        endpoint : str
            The endpoint within the group whose links are being fetched

        Returns
        -------
        list
            A list of Link objects representing links to the named endpoint
        """
        for l in self.links:
            if l.group_a == group.name and l.endpoint_a == endpoint:
                other_group = self.groups[l.group_b]
                other_endpoint = l.endpoint_b
            elif l.group_b == group.name and l.endpoint_b == endpoint:
                other_group = self.groups[l.group_a]
                other_endpoint = l.endpoint_a
            if other_group.app_id == target_app:
                return other_group.endpoints[other_endpoint]
        return None

    def get_links_by_app(self, target_app):
        """Locates all the links in this group that link to resources in the named target app

        Parameters
        ----------
        target_app : str
            The app_id of the application whose links are being fetched

        Returns
        -------
        list
            A list of Link objects representing all the links with
            endpoints in the named application
        """
        return self.db.get_links_by_app(self, target_app)

    def apply_group_endpoint_changes(self, group, changes=[]):
        """
        Applies a list of endpoint changes to a group. Typically these
        changes are deletions and renamings. This is done at the version
        level since it affects both groups and links.

        Parameters
        ----------
        group : Group
            The group the changes apply to
        changes : list
            A list of GroupChange items indicating which group
            resources have been deleted or renamed
        """
        # TODO - iterate through the links looking for endpoints
        # in the group that have been deleted/renamed
        # What to do when something is deleted? can a link have
        # an empty endpoint? probably
        pass

    def save(self, new_version_number):
        """
        Saves this version to the database under a new version number
        """
        return self.db.save_version(self, new_version_number)

class Project(object):
    """
    Contains a single Depi project

    Attributes
    ----------
    db : DepiDB
        A reference to a class that does the database operations
        defined in the DepiDB class
    name : str
        The name of this project
    """

    HEAD="~~HEAD~~"

    def __init__(self, db, name):
        """
        Parameters
        ----------
        db : DepiDB
            The database implementation class
        name : str
            The name of this project
        """
        self.db = db
        self.name = name

    def get_version(self, version="~~HEAD~~", create_if_new=True):
        """Locates an existing version

        Arguments
        ---------
        version : str
        the version to locate, the default is Project.HEAD, which is the current head version

        Returns
        -------
        Version
            A version object representing the retrieved version,
            or None if no such version exists
        """

        v = self.db.load_version(self, version)
        
        if v is None and version == self.HEAD and create_if_new:
            return Version(self.db, self, "")

        return v

    def get_versions(self):
        """Returns all the versions of this project

        Returns
        -------
        list
            A list of all the version numbers of this project
        """
        return self.db.get_versions(self.name)       

class Depi:
    """Provides a top-level interface into the Depi, allowing
    you to access projects

    Attributes
    ----------
    db : DepiDB
        A reference to a class that does the database operations
        defined in the DepiDB class

    """
    def __init__(self, db):
        """
        Parameters
        ----------
        db : DepiDB
            The database implementation class
        """
        self.db = db

    def create_project(self, name):
        """Creates a new project with the specified name

        Parameters
        ----------
        name : str
            The name of the project to create
        """
        return Project(self.db, name)

    def get_project_names(self):
        """Returns a list of all available projects

        Returns
        -------
        list
            A list of the available project names
        """
        return self.db.get_project_names()

    def get_project(self, name):
        """Locates an existing project with the specified name

        Parameters
        ----------
        name : str
            The name of the project to retrieve

        Returns
        -------
        Project
            A project object representing the existing project or
            None of the project doesn't exist
        """
        return Project(self.db, name)

