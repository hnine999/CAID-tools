import datetime
import time

import depi_pb2_grpc
import depi_pb2
import grpc
from google.protobuf import text_format
import uuid
from concurrent import futures
import queue
import json
from threading import Lock, Thread
import argparse
import base64

from depi_server.db.depi_db import DepiBranch
from depi_server.model.depi_model import Resource, ResourceRef, ResourceGroup, Link, LinkWithResources, ResourceGroupChange, \
    ResourceRefPattern, ResourceLinkPattern, ChangeType
from depi_server.db.depi_db_mem_json import MemJsonDB
from depi_server.db.depi_db_dolt import DoltDB
from depi_server.auth.depi_authorization import *

DEPI_CONFIG_ENV_VAR_NAME = 'DEPI_CONFIG'


class ToolConfig:
    def __init__(self, name, jsonConfig=None):
        self.name = name
        self.pathSeparator = '/'
        if jsonConfig is not None:
            self.loadFromJson(jsonConfig)

    def loadFromJson(self, jsonConfig):
        if "pathSeparator" in jsonConfig:
            self.pathSeparator = jsonConfig["pathSeparator"][0]


class Config:
    def __init__(self, jsonConfig=None):
        self.toolConfig = {}
        self.dbConfig = {}
        self.loggingConfig = {}
        self.serverConfig = {}
        self.usersConfig = {}
        self.authConfig = {}
        self.auditConfig = {}
        if jsonConfig is not None:
            self.loadFromJson(jsonConfig)

    def loadFromJson(self, jsonConfig):
        if "db" in jsonConfig:
            self.dbConfig = jsonConfig["db"]

        if "logging" in jsonConfig:
            self.loggingConfig = jsonConfig["logging"]

        if "server" in jsonConfig:
            self.serverConfig = jsonConfig["server"]

        if "users" in jsonConfig:
            self.usersConfig = jsonConfig["users"]

        if "authorization" in jsonConfig:
            self.authConfig = jsonConfig["authorization"]

        if "audit" in jsonConfig:
            self.auditConfig = jsonConfig["audit"]

        for toolName, toolJson in jsonConfig["tools"].items():
            tool = ToolConfig(toolName, toolJson)
            self.toolConfig[toolName] = tool

    def getToolConfig(self, toolId):
        return self.toolConfig[toolId]


config = Config()


def loadConfig(server_root,  config_filename=None):
    if config_filename is not None:
        config_file_name = config_filename
    elif DEPI_CONFIG_ENV_VAR_NAME in os.environ and os.environ[DEPI_CONFIG_ENV_VAR_NAME]:
        config_file_name = server_root+f"/configs/depi_config_{os.environ[DEPI_CONFIG_ENV_VAR_NAME]}.json"
        print(f'Using config-file: {config_file_name}')
    else:
        print(f'Using default config file, set env_var {DEPI_CONFIG_ENV_VAR_NAME} to load alternative config.')
        print(f'Example: $export {DEPI_CONFIG_ENV_VAR_NAME}=mem - would load depi_config.mem.json.')
        config_file_name = server_root+"/configs/depi_config_mem.json"

    if os.path.exists(config_file_name):
        with open(config_file_name, 'r') as config_file:
            config_json = json.load(config_file)
            config.loadFromJson(config_json)
    else:
        print(f"Config file {config_file_name} does not exist.")


class Blackboard:
    def __init__(self):
        self.changedLinks: set[LinkWithResources] = set()
        self.resources: dict[str, dict[str, ResourceGroup]] = {}
        self.deletedLinks: set[LinkWithResources] = set()

    def getResources(self) -> list[tuple[ResourceGroup, Resource]]:
        resList = []
        for tool in self.resources.values():
            for rg in tool.values():
                for res in rg.resources.values():
                    resList.append((rg, res))
        return resList

    def addResource(self, resourceGroup: ResourceGroup, resource: Resource) -> bool:
        toolResources = self.resources.get(resourceGroup.toolId)
        if toolResources is None:
            toolResources = {}
            self.resources[resourceGroup.toolId] = toolResources

        toolGroup = toolResources.get(resourceGroup.URL)
        if toolGroup is None:
            toolGroup = ResourceGroup(resourceGroup.name,
                                      resourceGroup.toolId,
                                      resourceGroup.URL,
                                      resourceGroup.version)
            toolResources[resourceGroup.URL] = toolGroup

        newRes = Resource(resource.name, resource.id, resource.URL)
        return toolGroup.addResource(newRes)

    def removeResource(self, ref: ResourceRef) -> bool:
        toolResources = self.resources.get(ref.toolId)
        if toolResources is None:
            return False

        toolGroup = toolResources.get(ref.resourceGroupURL)
        if toolGroup is None:
            return False

        return toolGroup.removeResource(ref.URL)

    def expandResource(self, toolId, resourceGroupURL, resourceURL) -> tuple[ResourceGroup, Resource] | None:
        if toolId in self.resources:
            if resourceGroupURL in self.resources[toolId]:
                group = self.resources[toolId][resourceGroupURL]
                if resourceURL in group.resources:
                    return group, group.resources[resourceURL]
        return None

    def linkResources(self, links: list[LinkWithResources]):
        updates = []
        for lk in links:
            if lk not in self.changedLinks:
                self.changedLinks.add(lk)
                update = depi_pb2.Update(updateType=depi_pb2.UpdateType.AddLink,
                                         link=lk.toGrpc())
                updates.append(update)
                if lk in self.deletedLinks:
                    self.deletedLinks.remove(lk)
            elif lk in self.deletedLinks:
                self.deletedLinks.remove(lk)
                update = depi_pb2.Update(updateType=depi_pb2.UpdateType.AddLink,
                                         link=lk.toGrpc())
                updates.append(update)
        return updates

    def unlinkResources(self, links):
        newChanged = set()
        updates = []
        for cl in self.changedLinks:
            if cl not in links:
                newChanged.add(cl)
            else:
                if cl not in self.deletedLinks:
                    self.deletedLinks.add(cl)
                    update = depi_pb2.Update(updateType=depi_pb2.UpdateType.RemoveLink,
                                             link=cl.toGrpc())
                    updates.append(update)

        self.changedLinks = newChanged
        return updates


class User:
    def __init__(self, name: str, password: str, authorization: Authorization = None):
        self.name = name
        self.password = password
        self.authorization = authorization


class Session:
    def __init__(self, sessionId: str, toolId: str, user: User, mainBranch: DepiBranch):
        self.watchedGroups = set()
        self.watchingResources = False
        self.watchingBlackboard = False
        self.watchingDepi = False
        self.lastRequest = datetime.datetime.now()
        self.resourceUpdates = queue.Queue()
        self.blackboardUpdates = queue.Queue()
        self.depiUpdates = queue.Queue()
        self.branch: DepiBranch = mainBranch
        #        self.toolId: str = toolId
        self.user: User = user
        self.sessionId = sessionId

    def printGRPC(self, msg):
        msgType = type(msg).__name__.split(".")[0]
        logging.debug(
            "{}({}): {}".format(msgType, self.sessionId, text_format.MessageToString(message=msg, as_one_line=True)))
        return msg

    def close_session(self):
        if self.watchingResources:
            self.resourceUpdates.put("quit")
        if self.watchingBlackboard:
            self.blackboardUpdates.put("quit")
        if self.watchingDepi:
            self.depiUpdates.put("quit")

class DepiServer(depi_pb2_grpc.DepiServicer):
    def __init__(self):
        self.tools = {"webgme", "git", "gitlfs", "git-gsn"}

        if config.dbConfig["type"] == "memjson":
            self.db = MemJsonDB(config)
        elif config.dbConfig["type"] == "dolt":
            self.db = DoltDB(config)

        self.sessions: dict[str, Session] = {}
        self.blackboards: dict[str, Blackboard] = {}
        self.updateLock = Lock()
        self.blackboardAlwaysMain = True
        self.authorizationEnabled = False
        self.session_lock = Lock()
        self.session_timeout = 3600

        self.audit_dir = "audit_logs"
        if "directory" in config.auditConfig:
            self.audit_dir = config.auditConfig["directory"]
        if self.audit_dir is not None and len(self.audit_dir) > 0:
            os.makedirs(self.audit_dir, exist_ok=True)
        self.audit_lock = Lock()
        self.curr_audit_date = None
        self.audit_file = None

        if "authorization_enabled" in config.serverConfig:
            self.authorizationEnabled = config.serverConfig["authorization_enabled"]

        if "session_timeout" in config.serverConfig:
            self.session_timeout = config.serverConfig["session_timeout"]

        if self.authorizationEnabled:
            if "auth_def_file" in config.authConfig:
                self.auth_rules = AuthorizationConfigParser.parse_config_file(config.authConfig["auth_def_file"])
            else:
                self.auth_rules = None
        else:
            self.auth_rules = None

        self.logins = {}
        for user in config.usersConfig:
            if self.authorizationEnabled:
                user_auth = Authorization.create_from_user_config(user["auth_rules"],
                                                                  self.auth_rules,
                                                                  user["name"])
            else:
                user_auth = None
            self.logins[user["name"]] = User(user["name"], user["password"], user_auth)

        self.session_thread = Thread(target=self.check_session_thread, args=[])
        self.session_thread.daemon = True
        self.session_thread.start()

    def check_session_thread(self):
        while True:
            try:
                self.check_sessions()

                time.sleep(300)

            except Exception as exc:
                logging.error("Error checking sessions", exc_info=exc)

    def check_sessions(self):
        try:
            self.session_lock.acquire()
            expired_sessions = []
            for session_key in self.sessions:
                session = self.sessions[session_key]
                if (datetime.datetime.now() - session.lastRequest).total_seconds() > self.session_timeout:
                    expired_sessions.append(session_key)
            for session_key in expired_sessions:
                logging.info("Session {} has timed out".format(session_key))
                self.sessions[session_key].close_session()
                self.sessions.pop(session_key)
        finally:
            self.session_lock.release()

    def get_audit_file(self):
        if self.audit_dir is None or len(self.audit_dir) == 0:
            return None
        curr_date = datetime.date.today()
        if curr_date == self.curr_audit_date and self.audit_file is not None:
            return self.audit_file
        if self.audit_file is not None:
            self.audit_file.close()
        log_filename = "{:4d}{:02d}{:02d}".format(curr_date.year, curr_date.month, curr_date.day)
        self.audit_file = open(self.audit_dir+os.path.sep+log_filename, "a")
        return self.audit_file

    def write_audit_log_entry(self, user, operation, data):
        try:
            self.audit_lock.acquire()
            audit_file = self.get_audit_file()
            if audit_file is None:
                return
            curr_time = datetime.datetime.now()

            print("{:02d}:{:02d}:{:02d}.{:03d}|{}|{}|{}".format(curr_time.hour, curr_time.minute,
                                                              curr_time.second, int(curr_time.microsecond / 1000.0),
                                                              user, operation, data), file=audit_file)
            audit_file.flush()
        finally:
            self.audit_lock.release()

    def get_session(self, session_id):
        try:
            self.session_lock.acquire()
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.lastRequest = datetime.datetime.now()
                return session
            else:
                return None
        finally:
            self.session_lock.release()

    def add_session(self, session):
        try:
            self.session_lock.acquire()
            self.sessions[session.sessionId] = session
        finally:
            self.session_lock.release()

    def remove_session(self, session_id):
        try:
            self.session_lock.acquire()
            self.sessions.pop(session_id)
        finally:
            self.session_lock.release()

    def printGRPC(self, msg):
        msgType = type(msg).__name__.split(".")[0]
        logging.debug("{}: {}".format(msgType, text_format.MessageToString(message=msg, as_one_line=True)))
        return msg

    def isAuthorized(self, user, capability, *args):
        if not self.authorizationEnabled:
            return True

        if user.authorization is None:
            return False

        return user.authorization.is_authorized(capability, *args)

    def hasCapability(self, user, capability):
        if not self.authorizationEnabled:
            return True

        if user.authorization is None:
            return False

        return user.authorization.has_capability(capability)

    def numDepiWatchers(self, branch_name):
        n=0
        for session in self.sessions.values():
           if branch_name is not None and branch_name != session.branch.name:
               continue
           if session.watchingDepi:
               n += 1
        return n

    def Login(self, request: depi_pb2.LoginRequest, context):
        self.printGRPC(request)
        if request.user in self.logins:
            if self.logins[request.user].password == request.password:
                if request.toolId != "blackboard" and \
                        request.toolId != "cli" and \
                        request.toolId not in self.tools:
                    return self.printGRPC(depi_pb2.LoginResponse(ok=False,
                                                                 msg="Invalid toolId {}".format(request.toolId),
                                                                 sessionId=""))
                sessionId = uuid.uuid4().hex
                self.add_session(Session(
                    sessionId, request.toolId, self.logins[request.user], self.db.getBranch("main")))
                if request.user not in self.blackboards:
                    self.blackboards[request.user] = Blackboard()
                return self.printGRPC(depi_pb2.LoginResponse(ok=True, msg="",
                                                             sessionId=sessionId))
        return self.printGRPC(depi_pb2.LoginResponse(ok=False, msg="Invalid login",
                                                     sessionId=""))

    def Logout(self, request: depi_pb2.LogoutRequest, context):
        self.printGRPC(request)
        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        session.close_session()
        self.remove_session(request.sessionId)

        return self.printGRPC(self.GetSuccessResponse())

    def RegisterCallback(self, request: depi_pb2.RegisterCallbackRequest, context):
        self.printGRPC(request)

        def generator(err=None):
            if err is not None:
                yield err
                return

            try:
                while True:
                    update = session.resourceUpdates.get()
                    if isinstance(update, str):
                        break
                    yield depi_pb2.ResourcesUpdatedNotification(ok=True, msg='', updates=[update])
            finally:
                session.watchingResources = False

        session = self.get_session(request.sessionId)
        if session is None:
            return generator(self.printGRPC(depi_pb2.ResourcesUpdatedNotification(ok=False,
                                                                 msg="Invalid session {}".format(request.sessionId),
                                                                 updates=[])))

        session.watchingResources = True

        return generator()

    def WatchBlackboard(self, request: depi_pb2.WatchBlackboardRequest, context):
        self.printGRPC(request)
        session = self.get_session(request.sessionId)

        def generator(err=None):
            if err is not None:
                yield err
                return
            try:
                while True:
                    update = session.blackboardUpdates.get()
                    if isinstance(update, str):
                        break
                    yield update
            finally:
                session.watchingBlackboard = False

        if session is None:
            return generator(self.printGRPC(
                depi_pb2.BlackboardUpdate(ok=False, msg="Invalid session {}".format(request.sessionId), updates=[])))

        session.watchingBlackboard = True

        def on_rpc_done():
            session.watchingBlackboard = False
            logging.debug("Client on {} disconnected from watching".format(request.sessionId))

        if context is not None:
            context.add_callback(on_rpc_done)

        return generator()

    def UnwatchBlackboard(self, request: depi_pb2.UnwatchBlackboardRequest, context):
        self.printGRPC(request)
        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        session.watchingBlackboard = False
        session.blackboardUpdates.put("quit")
        return self.GetSuccessResponse()

    def WatchDepi(self, request: depi_pb2.WatchDepiRequest, context):
        self.printGRPC(request)

        def generator(err=None):
            if err is not None:
                yield err
                return

            try:
                while True:
                    update = session.depiUpdates.get()
                    if isinstance(update, str):
                        break
                    yield update
            finally:
                session.watchingDepi = False

        session = self.get_session(request.sessionId)
        if session is None:
            return generator(self.printGRPC(
                depi_pb2.DepiUpdate(ok=False, msg="Invalid session {}".format(request.sessionId), updates=[])))

        session.watchingDepi = True

        def on_rpc_done():
            session.watchingDepi = False
            logging.debug("Depi watcher on {} disconnected".format(request.sessionId))

        if context is not None:
            context.add_callback(on_rpc_done)

        return generator()

    def UnwatchDepi(self, request: depi_pb2.WatchDepiRequest, context):
        self.printGRPC(request)
        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        session.watchingDepi = False
        session.depiUpdates.put("quit")
        return self.GetSuccessResponse()

    def WatchResourceGroup(self, request: depi_pb2.WatchResourceGroupRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        session.watchingResources = True

        session.watchedGroups.add((request.toolId, request.URL))

    def UnwatchResourceGroup(self, request: depi_pb2.UnwatchResourceGroupRequest, context):
        self.printGRPC(request)
        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        key = (request.toolId, request.URL)

        if key in session.watchedGroups:
            session.watchedGroups.remove(key)
        return session.printGRPC(self.GetSuccessResponse())

    def CreateBranch(self, request: depi_pb2.CreateBranchRequest, context):
        self.printGRPC(request)
        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        if self.db.branchExists(request.branchName):
            return session.printGRPC(self.GetFailureResponse("Branch already exists"))

        isFromTag = False
        fromBranch = request.fromBranch
        fromTag = request.fromTag
        if fromBranch != "":
            if not self.db.branchExists(fromBranch) and not self.db.tagExists(fromBranch):
                return session.printGRPC(self.GetFailureResponse("Unknown branch"))
        elif fromTag != "":
            isFromTag = True
            if not self.db.tagExists(fromTag):
                return session.printGRPC(self.GetFailureResponse("Unknown tag"))
        else:
            fromBranch = session.branch.name

        if not self.isAuthorized(session.user, CapBranchCreate):
            return session.printGRPC(
                self.GetFailureResponse("User {} is not authorized to create a branch".format(session.user.name)))

        if not isFromTag:
            self.db.createBranch(request.branchName, fromBranch)
            fromName=fromBranch
            op="CreateBranch"
        else:
            self.db.createBranchFromTag(request.branchName, fromTag)
            fromName=fromTag
            op="CreateBranchFromTag"

        self.write_audit_log_entry(session.user.name, op, "from={};to={}".format(
            fromName, request.branchName))
        return session.printGRPC(self.GetSuccessResponse())

    def CreateTag(self, request: depi_pb2.CreateTagRequest, context):
        self.printGRPC(request)
        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        fromBranch = request.fromBranch
        if fromBranch != "":
            if not self.db.branchExists(fromBranch):
                return session.printGRPC(self.GetFailureResponse("Unknown branch"))
        else:
            fromBranch = session.branch.name

        if not self.isAuthorized(session.user, CapBranchTag):
            return session.printGRPC(
                self.GetFailureResponse("User {} is not authorized to create a tag".format(session.user.name)))

        self.db.createTag(request.tagName, fromBranch)

        self.write_audit_log_entry(session.user.name, "CreateTag", "from={};to={}".format(
            fromBranch, request.tagName))
        return session.printGRPC(self.GetSuccessResponse())

    def SetBranch(self, request: depi_pb2.SetBranchRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        if not self.isAuthorized(session.user, CapBranchSwitch):
            return session.printGRPC(
                self.GetFailureResponse("User {} is not authorized to switch branches".format(session.user.name)))

        if self.db.branchExists(request.branch):
            session.branch = self.db.getBranch(request.branch)
            return session.printGRPC(self.GetSuccessResponse())
        else:
            return session.printGRPC(self.GetFailureResponse("Unknown branch"))

    def GetLastKnownVersion(self, request: depi_pb2.GetLastKnownVersionRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(depi_pb2.GetLastKnownVersionResponse(
                ok=False, msg="Invalid session {}".format(request.sessionId),
                version=""))

        branch = session.branch

        return session.printGRPC(
            depi_pb2.GetLastKnownVersionResponse(
                ok=True, msg="",
                version=branch.getResourceGroupVersion(
                    request.toolId, request.URL)))

    def AddResourceGroup(self, request: depi_pb2.AddResourceGroupRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if not self.hasCapability(session.user, CapResGroupAdd):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to create resource groups".format(
                        session.user.name)))

            if not self.isAuthorized(session.user, CapResGroupAdd,
                                     request.resourceGroup.toolId,
                                     request.resourceGroup.URL):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to create this resource group".format(
                        session.user.name)))

            branch.addResource(ResourceGroup.fromGrpcResourceGroup(
                request.resourceGroup), None)

            branch.saveBranchState()

            depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=[
                depi_pb2.Update(updateType=depi_pb2.UpdateType.AddResourceGroup,
                                addResourceGroup=request.resourceGroup)])
            for session in self.sessions.values():
                if session.branch.name != branch.name:
                    continue
                if session.watchingDepi:
                    session.depiUpdates.put(depiUpdate)

            self.write_audit_log_entry(session.user.name, "AddResourceGroup",
                                       "toolId={};URL={};name={};version={}".format(
                                           request.resourceGroup.toolId,
                                           request.resourceGroup.URL,
                                           request.resourceGroup.name,
                                           request.resourceGroup.version))
            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def AddResource(self, request: depi_pb2.AddResourceRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if not self.hasCapability(session.user, CapResourceAdd):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to create resources".format(
                        session.user.name)))

            if not self.isAuthorized(session.user, CapResourceAdd,
                                     request.toolId,
                                     request.resourceGroupURL,
                                     request.URL):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to create this resource".format(
                        session.user.name)))

            rg = branch.getResourceGroup(request.toolId, request.resourceGroupURL)

            res = Resource(name=request.name,
                           id=request.id,
                           URL=request.URL)
            branch.addResource(rg, res)

            depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=[
                depi_pb2.Update(updateType=depi_pb2.UpdateType.AddResource,
                                resource=Resource.toGrpc(rg))])
            for session in self.sessions.values():
                if session.branch.name != branch.name:
                    continue
                if session.watchingDepi:
                    session.depiUpdates.put(depiUpdate)

            branch.saveBranchState()

            self.write_audit_log_entry(session.user.name, "AddResource",
                                       "toolId={};rgURL={};URL={};name={};id={}".format(
                                           request.toolId,
                                           request.resourceGroupURL,
                                           request.URL,
                                           request.name,
                                           request.id))
            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def LinkResources(self, request: depi_pb2.LinkResourcesRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if not self.hasCapability(session.user, CapLinkAdd):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to create links".format(
                        session.user.name)))

            if not self.isAuthorized(session.user, CapLinkAdd,
                                     request.link.fromRes.toolId,
                                    request.link.fromRes.resourceGroupURL,
                                    request.link.fromRes.URL,
                                     request.link.toRes.toolId,
                                     request.link.toRes.resourceGroupURL,
                                     request.link.toRes.URL):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to create this link".format(
                        session.user.name)))

            (fromRg, fromRes) = branch.getResource(ResourceRef.fromGrpc(request.link.fromRes))
            (toRg, toRes) = branch.getResource(ResourceRef.fromGrpc(request.link.toRes))

            link_with_resources = LinkWithResources(fromRg, fromRes, toRg, toRes)
            branch.addLink(link_with_resources)

            branch.saveBranchState()

            depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=[
                depi_pb2.Update(updateType=depi_pb2.UpdateType.AddLink,
                                link=link_with_resources.toGrpc())])
            for session in self.sessions.values():
                if session.branch.name != branch.name:
                    continue
                if session.watchingDepi:
                    session.depiUpdates.put(depiUpdate)

            self.write_audit_log_entry(session.user.name, "LinkResources",
                                       "fromToolId={};fromRgURL={};fromURL={};toToolId={};toRgURL={};URL={}".format(
                                           request.link.fromRes.toolId,
                                           request.link.fromRes.resourceGroupURL,
                                           request.link.fromRes.URL,
                                           request.link.toRes.toolId,
                                           request.link.toRes.resourceGroupURL,
                                           request.link.toRes.URL))
            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def UnlinkResources(self, request: depi_pb2.LinkResourcesRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if not self.hasCapability(session.user, CapLinkRemove):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to remove links".format(
                        session.user.name)))

            if not self.isAuthorized(session.user, CapLinkRemove,
                                     request.link.fromRes.toolId,
                                     request.link.fromRes.resourceGroupURL,
                                     request.link.fromRes.URL,
                                     request.link.toRes.toolId,
                                     request.link.toRes.resourceGroupURL,
                                     request.link.toRes.URL):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to remove this link".format(
                        session.user.name)))

            branch.removeLink(Link(ResourceRef.fromGrpc(request.link.fromRes),
                                   ResourceRef.fromGrpc(request.link.toRes)))

            branch.saveBranchState()

            depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=[
                depi_pb2.Update(updateType=depi_pb2.UpdateType.RemoveLink,
                                removeLink=request.link)])
            for session in self.sessions.values():
                if session.branch.name != branch.name:
                    continue
                if session.watchingDepi:
                    session.depiUpdates.put(depiUpdate)

            self.write_audit_log_entry(session.user.name, "UnlinkResources",
                                       "fromToolId={};fromRgURL={};fromURL={};toToolId={};toRgURL={};URL={}".format(
                                           request.link.fromRes.toolId,
                                           request.link.fromRes.resourceGroupURL,
                                           request.link.fromRes.URL,
                                           request.link.toRes.toolId,
                                           request.link.toRes.resourceGroupURL,
                                           request.link.toRes.URL))
            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def EditResourceGroup(self, request: depi_pb2.EditResourceGroupRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if not self.hasCapability(session.user, CapResGroupChange):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to change resource groups".format(
                        session.user.name)))

            if not self.isAuthorized(session.user, CapResGroupChange,
                                     request.resourceGroup.toolId,
                                     request.resourceGroup.URL):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to change this resource group".format(
                        session.user.name)))

            branch.editResourceGroup(ResourceGroup("", request.resourceGroup.toolId,
                                                   request.resourceGroup.URL, ""),
                                     ResourceGroup(request.resourceGroup.new_name, request.resourceGroup.new_toolId,
                                                   request.resourceGroup.new_URL, request.resourceGroup.new_version))


            branch.saveBranchState()

            depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=[
                depi_pb2.Update(updateType=depi_pb2.UpdateType.EditResourceGroup,
                                editResourceGroup=request.resourceGroup)
            ])
            for session in self.sessions.values():
                if session.branch.name != branch.name:
                    continue
                if session.watchingDepi:
                    session.depiUpdates.put(depiUpdate)

            self.write_audit_log_entry(session.user.name, "EditResourceGroup",
                                       "toolId={};URL={};newToolId={};newURL={};newName={};newVersion={}".format(
                                           request.resourceGroup.toolId,
                                           request.resourceGroup.URL,
                                           request.resourceGroup.new_toolId,
                                           request.resourceGroup.new_URL,
                                           request.resourceGroup.new_name,
                                           request.resourceGroup.new_version))
            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def RemoveResourceGroup(self, request: depi_pb2.RemoveResourceGroupRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if not self.hasCapability(session.user, CapResGroupRemove):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to remove resource groups".format(
                        session.user.name)))

            if not self.isAuthorized(session.user, CapResGroupRemove,
                                     request.resourceGroup.toolId,
                                     request.resourceGroup.URL):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to remove this resource group".format(
                        session.user.name)))

            branch.removeResourceGroup(request.resourceGroup.toolId, request.resourceGroup.URL)

            branch.saveBranchState()

            depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=[
                depi_pb2.Update(updateType=depi_pb2.UpdateType.RemoveResourceGroup,
                                removeResourceGroup=depi_pb2.ResourceGroupRef(toolId=request.resourceGroup.toolId,
                                                                              URL=request.resourceGroup.URL))
            ])
            for session in self.sessions.values():
                if session.branch.name != branch.name:
                    continue
                if session.watchingDepi:
                    session.depiUpdates.put(depiUpdate)

            self.write_audit_log_entry(session.user.name, "RemoveResourceGroup",
                                       "toolId={};URL={}".format(
                                           request.resourceGroup.toolId,
                                           request.resourceGroup.URL))
            return session.printGRPC(self.GetSuccessResponse())

        finally:
            self.updateLock.release()

    def UpdateResourceGroup(self, request: depi_pb2.UpdateResourceGroupRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if request.updateBranch is not None and request.updateBranch != "":
                if request.updateBranch != branch.name:
                    branch = self.db.getBranch(request.updateBranch)


            if not self.hasCapability(session.user, CapResGroupChange):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to change resource groups".format(
                        session.user.name)))

            if not self.hasCapability(session.user, CapResourceChange):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to change resources".format(
                        session.user.name)))

            if not self.isAuthorized(session.user, CapResGroupChange,
                                     request.resourceGroup.toolId,
                                     request.resourceGroup.URL):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to change this resource group".format(
                        session.user.name)))

            resourceGroupChange = ResourceGroupChange.fromGrpc(request.resourceGroup)
            allowedResources = []
            for URL in resourceGroupChange.resources:
                resource = resourceGroupChange.resources[URL]
                if resource.changeType == ChangeType.Added:
                    if self.isAuthorized(session.user, CapResourceAdd, resourceGroupChange.toolId,
                                         resourceGroupChange.URL, URL):
                        allowedResources.append(resource)
                    else:
                        logging.warning("User {} is not allowed to add resource {} {} {}".format(
                            session.user.name, resourceGroupChange.toolId, resourceGroupChange.URL, URL))
                elif (resource.changeType == ChangeType.Modified or resource.changeType == ChangeType.Renamed):
                    if self.isAuthorized(session.user, CapResourceChange, resourceGroupChange.toolId,
                                         resourceGroupChange.URL, URL):
                        allowedResources.append(resource)
                    else:
                        logging.warning("User {} is not allowed to change resource {} {} {}".format(
                            session.user.name, resourceGroupChange.toolId, resourceGroupChange.URL, URL))
                elif resource.changeType == ChangeType.Removed:
                    if self.isAuthorized(session.user, CapResourceRemove, resourceGroupChange.toolId,
                                         resourceGroupChange.URL, URL):
                        allowedResources.append(resource)
                    else:
                        logging.warning("User {} is not allowed to remove resource {} {} {}".format(
                            session.user.name, resourceGroupChange.toolId, resourceGroupChange.URL, URL))

            resourceGroupChange.resources = {}
            depiUpdates = []
            for res in allowedResources:
                resourceGroupChange.resources[res.URL] = res
                depiUpdates.append(depi_pb2.Update(updateType=res.getChangeAsUpdateType(),
                                                   resource=res.toResource().toGrpc(resourceGroupChange.toResourceGroup())))

            linkedResourceGroupsToUpdate = branch.updateResourceGroup(resourceGroupChange)
            branch.saveBranchState()

            if branch.name == "main":
                # Clean up blackboards with respect to changes
                for blackboardUser in self.blackboards:
                    blackboard = self.blackboards[blackboardUser]
                    updates = []

                    # look at each resource group in the background
                    for tool in blackboard.resources.values():
                        for rg in tool.values():

                            # If the resource group version changes, add a notification
                            if rg.toolId == resourceGroupChange.toolId and \
                                    rg.URL == resourceGroupChange.URL and \
                                    rg.version != resourceGroupChange.version:
                                updates.append(
                                    depi_pb2.Update(
                                        updateType=depi_pb2.UpdateType.ResourceGroupVersionChanged,
                                        versionChange=depi_pb2.ResourceGroupVersionChange(
                                            name=resourceGroupChange.name,
                                            URL=resourceGroupChange.URL,
                                            toolId=resourceGroupChange.toolId,
                                            version=rg.version,
                                            new_version=resourceGroupChange.version)))
                                rg.version = resourceGroupChange.version

                                # For each changed resource, see if it is in the blackboard, and if it is
                                # a rename or a removal
                                for resourceChange in resourceGroupChange.resources.values():
                                    if resourceChange.URL not in rg.resources:
                                        continue
                                    if resourceChange.changeType == int(depi_pb2.ChangeType.Removed):
                                        # For a removal, add an update and remove the resource from the blackboard
                                        updates.append(
                                            depi_pb2.Update(
                                                updateType=depi_pb2.UpdateType.RemoveResource,
                                                resource=rg.resources[resourceChange.URL].toGrpc(rg)))
                                        res = rg.resources.pop(resourceChange.URL)

                                        newChanged = set()
                                        for link in blackboard.changedLinks:
                                            if link.fromRes == res or link.toRes == res:
                                                updates.append(
                                                    depi_pb2.Update(
                                                        updateType=depi_pb2.UpdateType.RemoveLink,
                                                        link=link.toGrpc()))
                                                if link not in blackboard.deletedLinks:
                                                    blackboard.deletedLinks.add(link)
                                            else:
                                                newChanged.add(link)
                                            blackboard.changedLinks = newChanged


                                    elif resourceChange.changeType == int(depi_pb2.ChangeType.Renamed) or \
                                            (resourceChange.changeType == int(depi_pb2.ChangeType.Modified) and
                                             (resourceChange.URL != resourceChange.newURL)):

                                        for link in blackboard.changedLinks:
                                            fromRes = link.fromRes.toGrpc(link.fromResourceGroup)
                                            toRes = link.toRes.toGrpc(link.toResourceGroup)
                                            changed = False
                                            if link.fromResourceGroup.toolId == resourceGroupChange.toolId and \
                                                    link.fromResourceGroup.URL == resourceGroupChange.URL and \
                                                    link.fromRes.URL == resourceChange.URL:
                                                changed = True
                                            elif link.toResourceGroup.toolId == resourceGroupChange.toolId and \
                                                    link.toResourceGroup.URL == resourceGroupChange.URL and \
                                                    link.toRes.URL == resourceChange.URL:
                                                changed = True

                                            if changed:
                                                fromResNew = link.fromRes.toGrpc(link.fromResourceGroup)
                                                fromResNew.URL = resourceChange.newURL
                                                fromResNew.name = resourceChange.newName
                                                fromResNew.id = resourceChange.newId

                                                toResNew = link.toRes.toGrpc(link.toResourceGroup)
                                                toResNew.URL = resourceChange.newURL
                                                toResNew.name = resourceChange.newName
                                                toResNew.id = resourceChange.newId

                                                updates.append(
                                                    depi_pb2.Update(
                                                        updateType=depi_pb2.UpdateType.RenameLink,
                                                        renameLink=depi_pb2.ResourceLinkRename(
                                                            fromRes=fromRes,
                                                            fromResNew=fromResNew,
                                                            toRes=toRes,
                                                            toResNew=toResNew)))
                                        # for a rename, perform the rename of the blackboard resource
                                        # and send a notification
                                        res = rg.resources.pop(resourceChange.URL)
                                        rg.resources[resourceChange.newURL] = res
                                        res.URL = resourceChange.newURL
                                        res.name = resourceChange.newName
                                        res.id = resourceChange.newId

                                        updates.append(
                                            depi_pb2.Update(
                                                updateType=depi_pb2.UpdateType.RenameResource,
                                                rename=resourceChange.toGrpc()))

                    # send blackboard notifications
                    if len(updates) > 0:
                        for session in self.sessions.values():
                            if session.user.name == blackboardUser:
                                session.blackboardUpdates.put(
                                    depi_pb2.BlackboardUpdate(
                                        ok=True, msg="", updates=updates))

            # send notifications
            logging.debug("Sending resource update for {} resources".format(len(linkedResourceGroupsToUpdate)))
            logging.debug("Sending depi update for {} resources to {} listeners".format(len(depiUpdates), self.numDepiWatchers(branch.name)))
            for lk in linkedResourceGroupsToUpdate:
                upd = depi_pb2.ResourceUpdate(watchedResource=lk.toRes.toGrpc(), updatedResource=lk.fromRes.toGrpc())
                depiUpdates.append(depi_pb2.Update(updateType=depi_pb2.UpdateType.MarkLinkDirty, markLinkDirty=lk.toGrpc()))
                for session in self.sessions.values():
                    if session.branch.name != branch.name:
                        continue
                    if (lk.toRes.toolId, lk.toRes.resourceGroupURL) in session.watchedGroups and \
                            session.watchingResources:
                        session.resourceUpdates.put(upd)
            depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=depiUpdates)
            for session in self.sessions.values():
                if session.branch.name != branch.name:
                    continue
                if session.watchingDepi:
                    session.depiUpdates.put(depiUpdate)

            for URL in resourceGroupChange.resources:
                resource = resourceGroupChange.resources[URL]
                changeType = "add"
                if resource.changeType == ChangeType.Modified:
                    changeType = "modify"
                elif resource.changeType == ChangeType.Renamed:
                    changeType = "rename"
                elif resource.changeType == ChangeType.Removed:
                    changeType = "remove"

                self.write_audit_log_entry(session.user.name, "UpdateResourceGroupResource",
                                           "toolId={};rgURL={};URL={};changeType={}".format(
                                               request.resourceGroup.toolId,
                                               request.resourceGroup.URL,
                                               URL, changeType))
            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def AddResourcesToBlackboard(self, request: depi_pb2.AddResourcesToBlackboardRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        updates = []
        blackboard = self.blackboards[session.user.name]
        for res in request.resources:
            added = blackboard.addResource(ResourceGroup(res.resourceGroupName, res.toolId, res.resourceGroupURL,
                                                         res.resourceGroupVersion),
                                           Resource(res.name, res.id, res.URL))
            if added:
                update = depi_pb2.Update(updateType=depi_pb2.UpdateType.AddResource,
                                         resource=depi_pb2.Resource(
                                             toolId=res.toolId, resourceGroupURL=res.resourceGroupURL,
                                             resourceGroupName=res.resourceGroupName,
                                             resourceGroupVersion=res.resourceGroupVersion,
                                             URL=res.URL,
                                             name=res.name,
                                             id=res.id,
                                             deleted=res.deleted))
                updates.append(update)

        if len(updates) > 0:
            for sess in self.sessions.values():
                if sess.watchingBlackboard:
                    sess.blackboardUpdates.put(
                        depi_pb2.BlackboardUpdate(ok=True, msg="", updates=updates))

        return session.printGRPC(self.GetSuccessResponse())

    def RemoveResourcesFromBlackboard(self, request: depi_pb2.RemoveResourcesFromBlackboardRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        updates = []
        blackboard = self.blackboards[session.user.name]
        for ref in request.resourceRefs:
            expandedRes = blackboard.expandResource(ref.toolId, ref.resourceGroupURL, ref.URL)
            if blackboard.removeResource(ref):
                rg, res = expandedRes
                update = depi_pb2.Update(updateType=depi_pb2.UpdateType.RemoveResource,
                                         resource=res.toGrpc(rg))
                updates.append(update)

        if len(updates) > 0:
            for sess in self.sessions.values():
                if sess.watchingBlackboard:
                    sess.blackboardUpdates.put(depi_pb2.BlackboardUpdate(ok=True, msg="", updates=updates))

        return session.printGRPC(self.GetSuccessResponse())

    def lookupLinkResources(self, blackboard: Blackboard, links: list[Link]) -> tuple[
        list[LinkWithResources], str | None]:
        result = []
        for link in links:
            fromPair = blackboard.expandResource(link.fromRes.toolId,
                                                 link.fromRes.resourceGroupURL,
                                                 link.fromRes.URL)
            if fromPair is None:
                return [], "Invalid from resource",

            fromRg, fromRes = fromPair

            toPair = blackboard.expandResource(link.toRes.toolId,
                                               link.toRes.resourceGroupURL,
                                               link.toRes.URL)
            if toPair is None:
                return [], "Invalid to resource"

            toRg, toRes = toPair
            result.append(LinkWithResources(fromRg, fromRes, toRg, toRes))
        return result, None

    def LinkBlackboardResources(self, request: depi_pb2.LinkBlackboardResourcesRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        blackboard = self.blackboards[session.user.name]

        reqLinks = [Link.fromGrpcRef(link) for link in request.links]

        start = datetime.datetime.now()

        links, resp = self.lookupLinkResources(blackboard, reqLinks)

        end = datetime.datetime.now()

        if resp is not None:
            return session.printGRPC(self.GetFailureResponse(resp))

        print("It took {} seconds to look up {} link resources".format(
            (end - start).total_seconds(), len(links)))

        start = datetime.datetime.now()
        updates = blackboard.linkResources(links)

        end = datetime.datetime.now()

        print("It took {} seconds to link {} resources".format(
            (end - start).total_seconds(), len(links)))

        if len(updates) > 0:
            for sess in self.sessions.values():
                if sess.watchingBlackboard:
                    sess.blackboardUpdates.put(depi_pb2.BlackboardUpdate(ok=True, msg="", updates=updates))

        return session.printGRPC(self.GetSuccessResponse())

    def UnlinkBlackboardResources(self, request: depi_pb2.UnlinkBlackboardResourcesRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        blackboard = self.blackboards[session.user.name]

        reqLinks = [Link.fromGrpcRef(link) for link in request.links]
        links, resp = self.lookupLinkResources(blackboard, reqLinks)
        if resp != None:
            return session.printGRPC(self.GetFailureResponse(resp))

        updates = blackboard.unlinkResources(links)

        if len(updates) > 0:
            for sess in self.sessions.values():
                if sess.watchingBlackboard:
                    sess.blackboardUpdates.put(depi_pb2.BlackboardUpdate(ok=True, msg="", updates=updates))

        return session.printGRPC(self.GetSuccessResponse())

    @staticmethod
    def GetResourcesAndLinks(links: list[LinkWithResources]) -> \
            tuple[set[tuple[ResourceGroup, Resource]], list[depi_pb2.ResourceLink]]:
        rrSet = set()
        for lk in links:
            if not lk.deleted:
                rrSet.add((lk.fromResourceGroup, lk.fromRes))
                rrSet.add((lk.toResourceGroup, lk.toRes))

        links = [lk.toGrpc() for lk in links]
        return rrSet, links

    def GetBlackboardResources(self, request: depi_pb2.GetBlackboardResourcesRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(depi_pb2.GetBlackboardResourcesResponse(
                ok=False, msg="Invalid session: {}".format(request.sessionId),
                resources=[],
                links=[]))

        blackboard = self.blackboards[session.user.name]

        (rrs, links) = DepiServer.GetResourcesAndLinks(list(blackboard.changedLinks))
        bbrrs = blackboard.getResources()
        for bbrr in bbrrs:
            rrs.add(bbrr)

        rrs = [rr.toGrpc(rg) for rg, rr in rrs]
        return session.printGRPC(
            depi_pb2.GetBlackboardResourcesResponse(
                ok=True, msg="", resources=rrs,
                links=links))

    def SaveBlackboard(self, request: depi_pb2.SaveBlackboardRequest, context):
        self.printGRPC(request)
        self.updateLock.acquire()
        try:
            session = self.get_session(request.sessionId)
            if session is None:
                return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

            if self.blackboardAlwaysMain:
                branch = self.db.getBranch("main")
            else:
                branch = session.branch

            blackboard = self.blackboards[session.user.name]

            rs = blackboard.getResources()
            if len(rs) > 0 and not self.hasCapability(session.user, CapResourceAdd):
                return session.printGRPC(
                    self.GetFailureResponse("User {} is not authorized to add resources".format(session.user.name)))

            checked_versions = set()
            for (rg, res) in rs:
                if (rg.toolId, rg.URL, rg.version) not in checked_versions:
                    rg_version = branch.getResourceGroupVersion(rg.toolId, rg.URL)
                    if rg_version != '' and rg_version != rg.version:
                        return session.printGRPC(
                            self.GetFailureResponse(
                                "Resource version in blackboard {} does not match resource version in Depi {}".format(
                                    rg.version, rg_version)))
                    checked_versions.add((rg.toolId, rg.URL, rg.version))

                toolConfig = config.getToolConfig(rg.toolId)
                if not res.URL.startswith(toolConfig.pathSeparator):
                    res.URL = toolConfig.pathSeparator + res.URL

                if not self.isAuthorized(session.user, CapResourceAdd, rg.toolId, rg.URL, res.URL):
                    return session.printGRPC(
                        self.GetFailureResponse("User {} is not authorized to add resources".format(session.user.name)))

            #                branch.addResource(rg, res)

            start = datetime.datetime.now()
            if len(rs) > 1000:
                for i in range(0, len(rs), 1000):
                    if (len(rs) - i < 1000):
                        branch.addResources(rs[i:len(rs)])
                    else:
                        branch.addResources(rs[i:i + 1000])
            else:
                branch.addResources(rs)

            end = datetime.datetime.now()
            logging.debug("It took {} seconds to save the blackboard resources".format((end - start).total_seconds()))

            #            for lk in blackboard.changedLinks:
            #                branch.addLink(lk)
            start = datetime.datetime.now()
            branch.addLinks(list(blackboard.changedLinks))
            end = datetime.datetime.now()

            resUpdates = [depi_pb2.Update(resource=res.toGrpc(rg)) for (rg,res) in rs]
            linkUpdates = [depi_pb2.Update(link=link.toGrpc()) for link in blackboard.changedLinks]

            branch.saveBranchState()
            self._clearBlackboard(session.user.name)

            logging.debug("Sending depi update for {} resources and {} links to {} listeners".format(len(resUpdates), len(linkUpdates), self.numDepiWatchers(None)))
            allUpdates = resUpdates + linkUpdates
            depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=allUpdates)
            for session in self.sessions.values():
                if session.watchingDepi:
                    session.depiUpdates.put(depiUpdate)

            logging.debug("It took {} seconds to save the blackboard links".format((end - start).total_seconds()))

            for (rg,res) in rs:
                self.write_audit_log_entry(session.user.name, "AddResource", "toolId={};rgURL={};URL={}".format(
                    rg.toolId, rg.URL, res.URL))

            for link in blackboard.changedLinks:
                self.write_audit_log_entry(session.user.name, "LinkResources", "fromToolId={};fromRgURL={};fromURL={};toToolId={};toRgURL={};toURL={}".format(
                    link.fromResourceGroup.toolId, link.fromResourceGroup.URL,
                    link.fromRes.URL, link.toResourceGroup.toolId,
                    link.toResourceGroup.URL, link.toRes.URL))

            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def _clearBlackboard(self, user):
        if user in self.blackboards:
            oldBlackboard = self.blackboards[user]
            updates = []
            for tool in oldBlackboard.resources.values():
                for rg in tool.values():
                    for res in rg.resources.values():
                        updates.append(depi_pb2.Update(updateType=depi_pb2.UpdateType.RemoveResource,
                                                       resource=res.toGrpc(rg)))
            for link in oldBlackboard.deletedLinks:
                updates.append(depi_pb2.Update(updateType=depi_pb2.UpdateType.AddLink,
                                               link=link.toGrpc()))

            for link in oldBlackboard.changedLinks:
                updates.append(depi_pb2.Update(updateType=depi_pb2.UpdateType.RemoveLink,
                                               link=link.toGrpc()))

            if len(updates) > 0:
                for sess in self.sessions.values():
                    if sess.watchingBlackboard:
                        sess.blackboardUpdates.put(
                            depi_pb2.BlackboardUpdate(ok=True, msg="", updates=updates))

        self.blackboards[user] = Blackboard()

    def ClearBlackboard(self, request: depi_pb2.ClearBlackboardRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self._clearBlackboard(session.user.name)

        return session.printGRPC(self.GetSuccessResponse())

    def GetDirtyLinks(self, request: depi_pb2.GetDirtyLinksRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(depi_pb2.GetDirtyLinksResponse(
                ok=False, msg="Invalid session {}".format(request.sessionId),
                resources=[],
                links=[]))

        branch = session.branch

        if not self.hasCapability(session.user, CapLinkRead):
            return session.printGRPC(
                depi_pb2.GetDirtyLinksResponse(
                    ok=False, msg="User {} cannot read links".format(session.user.name),
                    resources=[],
                    links=[]))

        logging.debug("Fetching dirty resources for {} {}".format(
            request.toolId, request.URL))
        resources = []
        links = []
        for link in branch.getDirtyLinks(ResourceGroup(toolId=request.toolId, URL=request.URL,name="",version=""), request.withInferred):
            if self.isAuthorized(session.user, CapLinkRead, link.fromResourceGroup.toolId,
                                 link.fromResourceGroup.URL, link.fromRes.URL,
                                 link.toResourceGroup.toolId, link.toResourceGroup.URL,
                                 link.toRes.URL):
                logging.debug("Link to {} is dirty".format(link.toRes.URL))
                resources.append((link.toResourceGroup, link.toRes))
                links.append(link)
            else:
                logging.warning("User {} is not authorized to read link {} {} {} -> {} {} {}".format(
                    session.user.name,
                    link.fromResourceGroup.toolId, link.fromResourceGroup.URL, link.fromRes.URL,
                    link.toResourceGroup.toolId, link.toResourceGroup.URL, link.toRes.URL))

        return session.printGRPC(
            depi_pb2.GetDirtyLinksResponse(
                ok=True, msg="", resources=[r.toGrpc(rg) for rg, r in resources],
                links=[lk.toGrpc() for lk in links]))

    def GetDirtyLinksAsStream(self, request: depi_pb2.GetDirtyLinksRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            yield self.printGRPC(depi_pb2.GetDirtyLinksAsStreamResponse(ok=False,
                                                   msg="Invalid session {}".format(
                                                       request.sessionId),
                                                   resource=depi_pb2.Resource(), link=depi_pb2.ResourceLink()))
            return

        branch = session.branch

        if not self.hasCapability(session.user, CapLinkRead):
            yield session.printGRPC(
                depi_pb2.GetDirtyLinksAsStreamResponse(ok=False,
                                               msg="User {} is not authorized to read links".format(session.user.name),
                                               resource=depi_pb2.Resource(), link=depi_pb2.ResourceLink()))
            return

        logging.debug("Fetching dirty resources for {} {}".format(
            request.toolId, request.URL))
        resources = []
        for link in branch.getDirtyLinksAsStream(ResourceGroup(toolId=request.toolId, URL=request.URL, name="", version=""), request.withInferred):
            if self.isAuthorized(session.user, CapLinkRead, link.fromResourceGroup.toolId,
                                 link.fromResourceGroup.URL, link.fromRes.URL,
                                 link.toResourceGroup.toolId, link.toResourceGroup.URL,
                                 link.toRes.URL):
                logging.debug("Link to {} is dirty".format(link.toRes.URL))
                resources.append((link.toResourceGroup, link.toRes))
                yield depi_pb2.GetDirtyLinksAsStreamResponse(ok=True, msg='',
                    resource=link.toRes.toGrpc(link.toResourceGroup),
                                                    link=link.toGrpc())
            else:
                logging.warning("User {} is not authorized to read link {} {} {} -> {} {} {}".format(
                    session.user.name,
                    link.fromResourceGroup.toolId, link.fromResourceGroup.URL, link.fromRes.URL,
                    link.toResourceGroup.toolId, link.toResourceGroup.URL, link.toRes.URL))

    def MarkLinksClean(self, request: depi_pb2.MarkLinksCleanRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if not self.hasCapability(session.user, CapLinkMarkClean):
                return session.printGRPC(self.GetFailureResponse(
                    "User {} is not authorized to mark links clean".format(session.user.name)))

            for link in request.links:
                if not self.isAuthorized(session.user, CapLinkMarkClean,
                                         link.fromRes.toolId, link.fromRes.resourceGroupURL,
                                         link.fromRes.URL, link.toRes.toolId, link.toRes.resourceGroupURL,
                                         link.toRes.URL):
                    return session.printGRPC(self.GetFailureResponse(
                        "User {} is not authorized to mark link {} {} {} -> {} {} {} clean".format(
                            session.user.name, link.fromRes.toolId, link.fromRes.resourceGroupURL,
                            link.fromRes.URL, link.toRes.toolId, link.toRes.resourceGroupURL,
                            link.toRes.URL)))

            links_to_clean = [Link.fromGrpcRef(l) for l in request.links]

            cleaned_links = branch.expandLinks(links_to_clean)

            branch.markLinksClean(links_to_clean, request.propagateCleanliness)

            branch.saveBranchState()

            updates = [depi_pb2.Update(updateType=depi_pb2.UpdateType.MarkLinkClean,
                                       markLinkClean=link.toGrpc()) for link in cleaned_links]

            if len(updates) > 0:
                logging.debug("Sending depi update for {} resources to {} listeners".format(len(updates), self.numDepiWatchers(branch.name)))
                depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=updates)
                for session in self.sessions.values():
                    # only send updates to sessions watching the same branch
                    if session.branch.name != branch.name:
                        continue
                    if session.watchingDepi:
                        session.depiUpdates.put(depiUpdate)

            for link in cleaned_links:
                self.write_audit_log_entry(session.user.name, "CleanedLink", "fromToolId={};fromRgURL={};fromURL={};toToolId={};toRgURL={};toURL={}".format(
                    link.fromResourceGroup.toolId, link.fromResourceGroup.URL,
                    link.fromRes.URL, link.toResourceGroup.toolId,
                    link.toResourceGroup.URL, link.toRes.URL))
            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def MarkInferredDirtinessClean(self, request: depi_pb2.MarkInferredDirtinessCleanRequest, context):
        self.printGRPC(request)
        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        self.updateLock.acquire()
        try:
            branch = session.branch

            if not self.hasCapability(session.user, CapLinkMarkClean):
                return session.printGRPC(self.GetFailureResponse(
                    "User {} is not authorized to mark links clean".format(session.user.name)))

            targetLink = Link.fromGrpcRef(request.link)

            if not self.isAuthorized(session.user, CapLinkMarkClean,
                                     targetLink.fromRes.toolId, targetLink.fromRes.resourceGroupURL,
                                     targetLink.fromRes.URL, targetLink.toRes.toolId,
                                     targetLink.toRes.resourceGroupURL, targetLink.toRes.URL):
                return session.printGRPC(self.GetFailureResponse(
                    "User {} is not authorized to mark link {} {} {} -> {} {} {} clean".format(
                        session.user.name, targetLink.fromRes.toolId, targetLink.fromRes.resourceGroupURL,
                        targetLink.fromRes.URL, targetLink.toRes.toolId, targetLink.toRes.resourceGroupURL,
                        targetLink.toRes.URL)))

            dirtinessSource = ResourceRef.fromGrpc(request.dirtinessSource)
            cleaned = branch.markInferredDirtinessClean(targetLink, dirtinessSource, request.propagateCleanliness)

            branch.saveBranchState()

            if len(cleaned) > 0:
                updates = [depi_pb2.Update(updateType=depi_pb2.UpdateType.MarkInferredLinkClean,
                                           markInferredLinkClean=depi_pb2.InferredLinkClean(
                                               link = link.toGrpc(), resource=res.toGrpc()))
                           for (link,res) in cleaned]

                logging.debug("Sending depi update for {} resources to {} listeners".format(len(updates), self.numDepiWatchers(branch.name)))
                depiUpdate = depi_pb2.DepiUpdate(ok=True, msg="", updates=updates)
                for session in self.sessions.values():
                    # only send updates to sessions watching the same branch
                    if session.branch.name != branch.name:
                        continue
                    if session.watchingDepi:
                        session.depiUpdates.put(depiUpdate)

            self.write_audit_log_entry(session.user.name, "CleanedInferredLink", "fromToolId={};fromRgURL={};fromURL={};toToolId={};toRgURL={};toURL={};sourceToolId={};sourceRgURL={};sourceURL={};proagate={}".format(
                targetLink.fromRes.toolId, targetLink.fromRes.resourceGroupURL,
                targetLink.fromRes.URL, targetLink.toRes.toolId,
                targetLink.toRes.resourceGroupURL, targetLink.toRes.URL,
                dirtinessSource.toolId, dirtinessSource.resourceGroupURL,
                dirtinessSource.URL, request.propagateCleanliness))
            return session.printGRPC(self.GetSuccessResponse())
        finally:
            self.updateLock.release()

    def DumpDatabase(self, request, context):
        self.printGRPC(request)
        self.updateLock.acquire()
        try:
            #            self.saveState()
            pass
        finally:
            self.updateLock.release()

    def GetResourceGroups(self, request: depi_pb2.GetResourceGroupsRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(
                depi_pb2.GetResourceGroupsResponse(
                    ok=False,
                    msg="Invalid session {}".format(request.sessionId)))

        if not self.hasCapability(session.user, CapResGroupRead):
            return session.printGRPC(
                depi_pb2.GetResourceGroupsResponse(
                    ok=False,
                    msg="User {} not authorized to read any resource groups".format(session.user.name),
                    resourceGroups=[]))

        branch = session.branch

        resourceGroups = [rg.toGrpc(False) for rg in branch.getResourceGroups()
                          if self.isAuthorized(session.user, CapResGroupRead, rg.toolId, rg.URL)]

        return session.printGRPC(
            depi_pb2.GetResourceGroupsResponse(
                ok=True, msg="", resourceGroups=resourceGroups))

    def GetResourceGroupsForTag(self, request: depi_pb2.GetResourceGroupsForTagRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(
                depi_pb2.GetResourceGroupsResponse(
                    ok=False,
                    msg="Invalid session {}".format(request.sessionId),
                    resourceGroups=[]))

        if not self.hasCapability(session.user, CapResGroupRead):
            return session.printGRPC(
                depi_pb2.GetResourceGroupsResponse(
                    ok=False,
                    msg="User {} not authorized to read any resource groups".format(session.user.name),
                    resourceGroups=[]))

        branch = self.db.getTag(request.tag)

        resourceGroups = [rg.toGrpc(False) for rg in branch.getResourceGroups()
                          if self.isAuthorized(session.user, CapResGroupRead, rg.toolId, rg.URL)]

        return session.printGRPC(
            depi_pb2.GetResourceGroupsResponse(
                ok=True, msg="", resourceGroups=resourceGroups))

    def GetResources(self, request: depi_pb2.GetResourcesRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(
                depi_pb2.GetResourcesResponse(ok=False, resources=[],
                                              msg="Invalid session {}".format(
                                                  request.sessionId)))

        branch = session.branch

        if not self.hasCapability(session.user, CapResourceRead):
            return self.printGRPC(
                depi_pb2.GetResourcesResponse(ok=False, resources=[],
                                              msg="User {} is not authorized to read resources".format(
                                                  session.user.name)))

        patterns = [ResourceRefPattern.fromGrpc(p) for p in request.patterns
                    if self.isAuthorized(session.user, CapResGroupRead, p.toolId, p.resourceGroupURL)]
        resources = [res.toGrpc(rg) for (rg, res) in branch.getResources(
            patterns, request.includeDeleted) if self.isAuthorized(session.user, CapResourceRead, rg.toolId, rg.URL, res.URL)]

        return session.printGRPC(
            depi_pb2.GetResourcesResponse(
                ok=True, msg="",
                resources=resources))

    def GetResourcesAsStream(self, request: depi_pb2.GetResourcesRequest, context):
        self.printGRPC(request)

        def generator(resources):
            for resource in resources:
                yield resource

        session = self.get_session(request.sessionId)
        if session is None:
            return generator([self.printGRPC(
                depi_pb2.GetResourcesAsStreamResponse(ok=False, resource=depi_pb2.Resource(),
                                              msg="Invalid session {}".format(request.sessionId)))])

        branch = session.branch

        if not self.hasCapability(session.user, CapResourceRead):
            return generator([self.printGRPC(
                depi_pb2.GetResourcesAsStreamResponse(ok=False, resource=depi_pb2.Resource(),
                                              msg="User {} is not authorized to read resources".format(
                                                  session.user.name)))])

        patterns = [ResourceRefPattern.fromGrpc(p) for p in request.patterns
                    if self.isAuthorized(session.user, CapResGroupRead, p.toolId, p.resourceGroupURL)]
        for (rg, res) in branch.getResourcesAsStream(patterns):
           if self.isAuthorized(session.user, CapResourceRead, rg.toolId, rg.URL, res.URL):
               yield depi_pb2.GetResourcesAsStreamResponse(ok=True, msg='', resource=res.toGrpc(rg))

    def GetLinks(self, request: depi_pb2.GetLinksRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(
                depi_pb2.GetResourcesResponse(ok=False, resources=[],
                                              msg="Invalid session {}".format(request.sessionId)))

        branch = session.branch

        if not self.hasCapability(session.user, CapLinkRead):
            return self.printGRPC(
                depi_pb2.GetResourcesResponse(ok=False, resources=[],
                                              msg="User {} is not authorized to read links".format(session.user.name)))

        patterns = [ResourceLinkPattern.fromGrpc(p) for p in request.patterns]

        links = [lk.toGrpc() for lk in branch.getLinks(patterns)
                 if self.isAuthorized(session.user, CapLinkRead, lk.fromResourceGroup.toolId,
                                      lk.fromResourceGroup.URL, lk.fromRes.URL,
                                      lk.toResourceGroup.toolId, lk.toResourceGroup.URL,
                                      lk.toRes.URL)]

        return session.printGRPC(
            depi_pb2.GetLinksResponse(
                ok=True, msg="", resourceLinks=links))

    def GetLinksAsStream(self, request: depi_pb2.GetLinksRequest, context):
        self.printGRPC(request)

        def generator(send_links):
            for link in send_links:
                yield link

        session = self.get_session(request.sessionId)
        if session is None:
            return generator([self.printGRPC(
                depi_pb2.GetLinksAsStreamResponse(ok=False, resourceLink=depi_pb2.ResourceLink(),
                                                      msg="Invalid session {}".format(request.sessionId)))])

        branch = session.branch

        if not self.hasCapability(session.user, CapLinkRead):
            return generator([self.printGRPC(
                depi_pb2.GetLinksAsStreamResponse(ok=False, resourceLink=depi_pb2.ResourceLink(),
                                                      msg="User {} is not authorized to read links".format(
                                                          session.user.name)))])

        patterns = [ResourceLinkPattern.fromGrpc(p) for p in request.patterns]

        links = [depi_pb2.GetLinksAsStreamResponse(ok=True, msg='', resourceLink=lk.toGrpc())
                 for lk in branch.getLinks(patterns)
                 if self.isAuthorized(session.user, CapLinkRead, lk.fromResourceGroup.toolId,
                                      lk.fromResourceGroup.URL, lk.fromRes.URL,
                                      lk.toResourceGroup.toolId, lk.toResourceGroup.URL,
                                      lk.toRes.URL)]

        return generator(links)

    def GetAllLinksAsStream(self, request: depi_pb2.GetAllLinksAsStreamRequest, context):
        self.printGRPC(request)

        def generator(send_links):
            for link in send_links:
                yield link

        session = self.get_session(request.sessionId)
        if session is None:
            return generator([self.printGRPC(
                depi_pb2.GetLinksAsStreamResponse(ok=False, resourceLink=depi_pb2.ResourceLink(),
                                                  msg="Invalid session {}".format(request.sessionId)))])

        branch = session.branch

        if not self.hasCapability(session.user, CapLinkRead):
            return generator([self.printGRPC(
                depi_pb2.GetLinksAsStreamResponse(ok=False, resourceLink=depi_pb2.ResourceLink(),
                                                  msg="User {} is not authorized to read links".format(
                                                      session.user.name)))])

        for lk in branch.getAllLinksAsStream():
             if self.isAuthorized(session.user, CapLinkRead, lk.fromResourceGroup.toolId,
                                  lk.fromResourceGroup.URL, lk.fromRes.URL,
                                  lk.toResourceGroup.toolId, lk.toResourceGroup.URL,
                                  lk.toRes.URL):
                yield depi_pb2.GetLinksAsStreamResponse(ok=True, msg='', resourceLink=lk.toGrpc())

    def GetDependencyGraph(self, request: depi_pb2.GetDependencyGraphRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(
                depi_pb2.GetDependencyGraphResponse(
                    ok=False, resource=None, links=[],
                    msg="Invalid session {}".format(request.sessionId)))

        branch = session.branch

        if not self.hasCapability(session.user, CapLinkRead):
            return session.printGRPC(
                depi_pb2.GetDependencyGraphResponse(
                    ok=False, resource=None, links=[],
                    msg="User {} is not authorized to read links".format(session.user.name)))

        resourceRef = ResourceRef.fromGrpc(request.resource)
        parentResource = branch.getResource(resourceRef)

        if parentResource is None:
            return self.GetFailureResponse("Parent resource not found")

        links = [l for l in branch.getDependencyGraph(
            resourceRef, request.dependenciesType == depi_pb2.DependenciesType.Dependencies, request.maxDepth)
                 if self.isAuthorized(session.user, CapLinkRead, l.fromResourceGroup.toolId,
                                      l.fromResourceGroup.URL, l.fromRes.URL, l.toResourceGroup.toolId,
                                      l.toResourceGroup.URL, l.toRes.URL)]

        rg, resource = parentResource
        return session.printGRPC(
            depi_pb2.GetDependencyGraphResponse(ok=True, msg="", resource=resource.toGrpc(rg),
                                                links=[l.toGrpc() for l in links]))

    def GetBranchList(self, request: depi_pb2.GetBranchListRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(
                depi_pb2.GetBranchListResponse(
                    ok=False, branches=[], tags=[],
                    msg="Invalid session {}".format(request.sessionId)))

        if not self.hasCapability(session.user, CapBranchList):
            return session.printGRPC(
                depi_pb2.GetBranchListResponse(
                    ok=False, branches=[], tags=[],
                    msg="User {} is not authorized to list branches".format(session.user.name)))

        branches = self.db.getBranchList()
        tags = self.db.getTagList()

        return session.printGRPC(
            depi_pb2.GetBranchListResponse(ok=True, msg="",
                                           branches=branches,
                                           tags=tags))

    def UpdateDepi(self, request: depi_pb2.UpdateDepiRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        branch = session.branch

        updates = []
        self.updateLock.acquire()
        try:
            for update in request.updates:
                if update.updateType == depi_pb2.UpdateType.AddResource:
                    rg = ResourceGroup.fromGrpcResource(update.resource)
                    res = Resource.fromGrpcResource(update.resource)
                    if self.isAuthorized(session.user, CapResourceAdd, rg.toolId, rg.URL, res.URL):
                        if branch.addResource(rg, res):
                            updates.append(update)
                    else:
                        logging.warning("User {} not authorized to add resource {} {} {}".format(
                            session.user.name, rg.toolId, rg.URL, res.URL))
                    self.write_audit_log_entry(session.user.name, "AddResource",
                                       "toolId={};rgURL={};URL={};name={};id={}".format(
                                           rg.toolId, rg.URL, res.URL, res.name, res.id))
                elif update.updateType == depi_pb2.UpdateType.RemoveResource:
                    rg = ResourceGroup.fromGrpcResource(update.resource)
                    res = Resource.fromGrpcResource(update.resource)
                    if self.isAuthorized(session.user, CapResourceRemove, rg.toolId, rg.URL, res.URL):
                        if branch.removeResourceRef(ResourceRef.fromGrpcResource(
                                update.resource)):
                            updates.append(update)
                    else:
                        logging.warning("User {} not authorized to remove resource {} {} {}".format(
                            session.user.name, rg.toolId, rg.URL, res.URL))
                    self.write_audit_log_entry(session.user.name, "RemoveResource",
                                               "toolId={};rgURL={};URL={};name={};id={}".format(
                                                   rg.toolId, rg.URL, res.URL, res.name, res.id))
                elif update.updateType == depi_pb2.UpdateType.AddLink:
                    if self.isAuthorized(session.user, CapLinkAdd, update.link.fromRes.toolId,
                                         update.link.fromRes.resourceGroupURL,
                                         update.link.fromRes.URL,
                                         update.link.toRes.toolId,
                                         update.link.toRes.resourceGroupURL,
                                         update.link.toRes.URL):
                        fromResourceGroup = ResourceGroup.fromGrpcResource(update.link.fromRes)
                        fromRes = Resource.fromGrpcResource(update.link.fromRes)
                        branch.addResource(fromResourceGroup, fromRes)

                        toResourceGroup = ResourceGroup.fromGrpcResource(update.link.toRes)
                        toRes = Resource.fromGrpcResource(update.link.toRes)
                        branch.addResource(toResourceGroup, toRes)

                        if branch.addLink(
                                LinkWithResources(fromResourceGroup, fromRes,
                                                  toResourceGroup, toRes, False, fromResourceGroup.version)):
                            updates.append(update)
                    else:
                        logging.warning("User {} not authorized to add link {} {} {} -> {} {} {}".format(
                            session.user.name,
                            update.link.fromRes.toolId,
                            update.link.fromRes.resourceGroupURL,
                            update.link.fromRes.URL,
                            update.link.toRes.toolId,
                            update.link.toRes.resourceGroupURL,
                            update.link.toRes.URL))
                    self.write_audit_log_entry(session.user.name, "LinkResources", "fromToolId={};fromRgURL={};fromURL={};toToolId={};toRgURL={};toURL={}".format(
                        update.link.fromRes.toolId, update.link.fromRes.resourceGroupURL,
                        update.link.fromRes.URL, update.link.toRes.toolId,
                        update.link.toRes.resourceGroupURL, update.link.toRes.URL))

                elif update.updateType == depi_pb2.UpdateType.RemoveLink:
                    if self.isAuthorized(session.user, CapLinkRemove, update.link.fromRes.toolId,
                                         update.link.fromRes.resourceGroupURL,
                                         update.link.fromRes.URL,
                                         update.link.toRes.toolId,
                                         update.link.toRes.resourceGroupURL,
                                         update.link.toRes.URL):
                        if branch.removeLink(
                                Link(ResourceRef.fromGrpcResource(update.link.fromRes),
                                     ResourceRef.fromGrpcResource(update.link.toRes))):
                            updates.append(update)
                    else:
                        logging.warning("User {} not authorized to remove link {} {} {} -> {} {} {}".format(
                            session.user.name,
                            update.link.fromRes.toolId,
                            update.link.fromRes.resourceGroupURL,
                            update.link.fromRes.URL,
                            update.link.toRes.toolId,
                            update.link.toRes.resourceGroupURL,
                            update.link.toRes.URL))

                    self.write_audit_log_entry(session.user.name, "UnlinkResources", "fromToolId={};fromRgURL={};fromURL={};toToolId={};toRgURL={};toURL={}".format(
                        update.link.fromRes.toolId, update.link.fromRes.resourceGroupURL,
                        update.link.fromRes.URL, update.link.toRes.toolId,
                        update.link.toRes.resourceGroupURL, update.link.toRes.URL))

            branch.saveBranchState()
            if len(updates) > 0:
                logging.debug("Sending depi update for {} resources to {} listeners".format(len(updates), self.numDepiWatchers(branch.name)))
                depiUpdate = depi_pb2.DepiUpdate(ok=True,msg="", updates=updates)
                for session in self.sessions.values():
                    # only send updates to sessions watching the same branch
                    if session.branch.name != branch.name:
                        continue
                    if session.watchingDepi:
                        session.depiUpdates.put(depiUpdate)

            return session.printGRPC(depi_pb2.GenericResponse(ok=True, msg=""))
        finally:
            self.updateLock.release()

    def CurrentBranch(self, request: depi_pb2.CurrentBranchRequest, context):
        self.printGRPC(request)

        session = self.get_session(request.sessionId)
        if session is None:
            return self.printGRPC(self.GetInvalidSessionResponse(request.sessionId))

        branch = session.branch
        return session.printGRPC(depi_pb2.CurrentBranchResponse(ok=True, msg="", branch=branch.name))

    def GetBidirectionalChanges(self, request: depi_pb2.GetBidirectionalChangesRequest, context):
        pass

    def Ping(self, request: depi_pb2.PingRequest, context):
        session = self.get_session(request.sessionId)
        if session is not None:
            return self.GetSuccessResponse()
        else:
            return self.GetInvalidSessionResponse(request.sessionId)

    def ApproveBidirectionalChange(self, request: depi_pb2.ApproveBidirectionalChangeRequest, context):
        pass

    def GetInvalidSessionResponse(self, sessionId):
        return depi_pb2.GenericResponse(ok=False, msg="Invalid session: {}".format(sessionId))

    def GetSuccessResponse(self):
        return depi_pb2.GenericResponse(ok=True, msg="")

    def GetFailureResponse(self, reason):
        return depi_pb2.GenericResponse(ok=False, msg=reason)


def log_level(level):
    level = level.lower()
    if level == "info":
        return logging.INFO
    elif level == "warning":
        return logging.WARNING
    elif level == "error":
        return logging.ERROR
    elif level == "critical":
        return logging.CRITICAL
    elif level == "debug":
        return logging.DEBUG
    else:
        print("Invalid logging level {}, using DEBUG".format(level))
        return logging.DEBUG


def get_config_value(config_dict, key, default):
    if key in config_dict:
        return config_dict[key]
    else:
        return default

def serve():
    parser = argparse.ArgumentParser(
        prog="depi_server",
        description="Dependency server")
    parser.add_argument("-config", "--config", dest="config_file", required=False)
    parser.add_argument("-config-default-mem", "--config-default-mem", dest="config_default_mem", action="store_true")
    parser.add_argument("-config-default-dolt", "--config-default-dolt", dest="config_default_dolt", action="store_true")

    args = parser.parse_args()

    server_root = os.path.dirname(__file__)

    config_filename = args.config_file
    if config_filename is None:
        if args.config_default_mem:
            config_filename = server_root+"/configs/depi_config_mem.json"
        elif args.config_default_dolt:
            config_filename = server_root+"/configs/depi_config_dolt.json"

    loadConfig(server_root, config_filename)

    logging.basicConfig(filename=config.loggingConfig.get("filename", "depi_server.log"),
                        level=log_level(config.loggingConfig.get("level", "debug")))
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    logging.debug("git path separator is {}".format(config.toolConfig["git"].pathSeparator))
    logging.debug("webgme path separator is {}".format(config.toolConfig["webgme"].pathSeparator))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=100))
    depi_pb2_grpc.add_DepiServicer_to_server(DepiServer(), server)


    insecure_port = get_config_value(config.serverConfig, "insecure_port", 0)
    if insecure_port != 0:
        server.add_insecure_port("[::]:"+str(insecure_port))

    secure_port = get_config_value(config.serverConfig, "secure_port", 0)
    if secure_port != 0:
        key_pem_filename = get_config_value(config.serverConfig, "key_pem", None)
        if key_pem_filename is None:
            logging.error("Both key_pem and cert_pem config values are requires for a secure server port")
            return
        with open(key_pem_filename, "rb") as file:
            key_pem = file.read()
        cert_pem_filename = get_config_value(config.serverConfig, "cert_pem", None)
        if cert_pem_filename is None:
            logging.error("Both key_pem and cert_pem config values are requires for a secure server port")
            return
        with open(cert_pem_filename, "rb") as file:
            cert_pem = file.read()
        creds = grpc.ssl_server_credentials(((key_pem, cert_pem),))
        server.add_secure_port("[::]:"+str(secure_port), creds)

    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
