import depi_pb2

global config


class Resource:
    def __init__(self, name: str, id: str, URL: str, deleted=False, changeType=depi_pb2.ChangeType.Added):
        self.name: str = name
        self.id: str = id
        self.URL: str = URL
        self.deleted: bool = deleted
        self.changeType: depi_pb2.ChangeType = changeType

    def __eq__(self, other) -> bool:
        return self.id == other.id and self.URL == other.URL

    def __hash__(self) -> int:
        return hash((hash(self.id), hash(self.URL)))

    def toGrpc(self, resourceGroup: "ResourceGroup") -> depi_pb2.Resource:
        return depi_pb2.Resource(
            toolId=resourceGroup.toolId, resourceGroupURL=resourceGroup.URL,
            resourceGroupName=resourceGroup.name, resourceGroupVersion=resourceGroup.version,
            name=self.name, URL=self.URL, id=self.id,
                                 deleted=self.deleted)

    def toGrpcChange(self) -> depi_pb2.ResourceChange:
        return depi_pb2.ResourceChange(name=self.name, URL=self.URL,
                                       id=self.id, changeType=self.changeType)

    @staticmethod
    def fromGrpcResource(resource: depi_pb2.Resource) -> "Resource":
        return Resource(name=resource.name, id=resource.id, URL=resource.URL)

    @staticmethod
    def fromGrpcResourceChange(resource: depi_pb2.ResourceChange) -> "Resource":
        return Resource(name=resource.name, id=resource.id, URL=resource.URL, deleted=False,
                        changeType=resource.changeType)

    def toJson(self) -> dict:
        return {"name": self.name, "id": self.id, "URL": self.URL,
                "deleted": self.deleted}

    @staticmethod
    def fromJson(record: dict) -> "Resource":
        return Resource(name=record["name"], id=record["id"], URL=record["URL"], deleted=record["deleted"])


class ChangeType:
    Added = 0
    Modified = 1
    Renamed = 2
    Removed = 3


class ResourceChange:
    def __init__(self, name: str, id: str, URL: str, newName: str, newId: str,
                 newURL: str, deleted=False, changeType: int = 0):
        self.name: str = name
        self.id: str = id
        self.URL: str = URL
        self.newName: str = newName
        self.newId: str = newId
        self.newURL: str = newURL
        self.deleted: bool = deleted
        self.changeType: int = changeType

    def getChangeAsUpdateType(self):
        if self.changeType == 0:
            return depi_pb2.UpdateType.AddResource
        elif self.changeType == 1:
            return depi_pb2.UpdateType.ChangeResource
        elif self.changeType == 2:
            return depi_pb2.UpdateType.RenameResource
        elif self.changeType == 3:
            return depi_pb2.UpdateType.RemoveResource

    @staticmethod
    def fromGrpc(resource: depi_pb2.ResourceChange) -> "ResourceChange":
        return ResourceChange(name=resource.name, id=resource.id, URL=resource.URL,
                              newName=resource.new_name, newId=resource.new_id,
                              newURL=resource.new_URL, changeType=int(resource.changeType))

    def toGrpc(self) -> depi_pb2.ResourceChange:
        ct = depi_pb2.ChangeType.Added
        for name, val in depi_pb2.ChangeType.items():
            if val == self.changeType:
                ct = depi_pb2.ChangeType.Value(name)
        return depi_pb2.ResourceChange(
            name=self.name,
            id=self.id,
            URL=self.URL,
            changeType=ct,
            new_name=self.newName,
            new_id=self.newId,
            new_URL=self.newURL)

    def toResource(self) -> Resource:
        return Resource(name=self.name, id=self.id, URL=self.URL, deleted=self.deleted)

class ResourceGroup:
    def __init__(self, name: str, toolId: str, URL: str, version: str, resources: dict[str,Resource] | None = None):
        self.name: str = name
        self.toolId: str = toolId
        self.URL: str = URL
        self.version: str = version
        if resources is None:
            self.resources: dict[str, Resource] = {}
        else:
            self.resources: dict[str, Resource] = resources

    def __eq__(self, other) -> bool:
        return self.name == other.name and self.URL == other.URL

    def __hash__(self) -> int:
        return hash((hash(self.name), hash(self.URL)))

    def getResource(self, url: str) -> Resource:
        return self.resources.get(url)

    def addResource(self, res: Resource) -> bool:
        if res.URL not in self.resources:
            self.resources[res.URL] = res
            return True
        else:
            return False

    def removeResource(self, url: str) -> bool:
        if url in self.resources:
            del self.resources[url]
            return True
        else:
            return False

    def getResources(self) -> list[Resource]:
        return list(self.resources.values())

    def toGrpc(self, includeResources: bool) -> depi_pb2.ResourceGroup:
        if includeResources:
            grpcResources = [r.toGrpc(self) for r in self.resources.values()]
        else:
            grpcResources = []
        return depi_pb2.ResourceGroup(name=self.name, toolId=self.toolId,
                                      URL=self.URL, version=self.version,
                                      resources=grpcResources)

    @staticmethod
    def fromGrpcResource(res: depi_pb2.Resource) -> "ResourceGroup":
        return ResourceGroup(name=res.resourceGroupName, toolId=res.toolId,
                             URL=res.resourceGroupURL,
                             version=res.resourceGroupVersion)

    @staticmethod
    def fromGrpcResourceGroup(rg: depi_pb2.ResourceGroup) -> "ResourceGroup":
        resources: dict[str, Resource] = {}
        for r in rg.resources:
            resources[r.URL] = Resource.fromGrpcResource(r)
        return ResourceGroup(name=rg.name, toolId=rg.toolId, URL=rg.URL,
                             version=rg.version, resources=resources)

    @staticmethod
    def fromGrpcResourceGroupChange(rg: depi_pb2.ResourceGroupChange) -> "ResourceGroup":
        resources: dict[str, Resource] = {}
        for r in rg.resources.values():
            resources[r.URL] = Resource.fromGrpcResourceChange(r)
        return ResourceGroup(name=rg.name, toolId=rg.toolId, URL=rg.URL,
                             version=rg.version, resources=resources)

    def toJson(self) -> dict:
        return {"name": self.name, "toolId": self.toolId,
                "URL": self.URL, "version": self.version,
                "resources": [r.toJson() for r in self.resources.values()]}

    @staticmethod
    def fromJson(record: dict) -> "ResourceGroup":
        resMap: dict[str, Resource] = {}
        for r in record["resources"]:
            res = Resource.fromJson(r)
            resMap[res.URL] = res

        return ResourceGroup(name=record["name"], toolId=record["toolId"],
                             URL=record["URL"], version=record["version"],
                             resources=resMap)


class ResourceGroupChange:
    def __init__(self, name: str, toolId: str, URL: str, version: str, resources: dict[str,ResourceChange] | None = None):
        self.name: str = name
        self.toolId: str = toolId
        self.URL: str = URL
        self.version: str = version
        if resources is None:
            self.resources: dict[str, ResourceChange] = {}
        else:
            self.resources: dict[str, ResourceChange] = resources

    def __eq__(self, other) -> bool:
        return self.name == other.name and self.URL == other.URL

    def __hash__(self) -> int:
        return hash((hash(self.name), hash(self.URL)))

    def getResource(self, url: str) -> ResourceChange:
        return self.resources.get(url)

    def getResources(self) -> list[ResourceChange]:
        return list(self.resources.values())

    def toResourceGroup(self) -> ResourceGroup:
        return ResourceGroup(name=self.name, toolId=self.toolId, URL=self.URL, version=self.version)

    @staticmethod
    def fromGrpc(resourceGroup: depi_pb2.ResourceGroupChange) -> "ResourceGroupChange":
        resources: dict[str, ResourceChange] = {}
        for res in resourceGroup.resources:
            resources[res.URL] = ResourceChange.fromGrpc(res)

        return ResourceGroupChange(name=resourceGroup.name, toolId=resourceGroup.toolId,
                                   URL=resourceGroup.URL,
                                   version=resourceGroup.version,
                                   resources=resources)

    @staticmethod
    def fromGrpcResourceGroup(rg: depi_pb2.ResourceGroup) -> "ResourceGroup":
        resources: dict[str, Resource] = {}
        for r in rg.resources:
            resources[r.URL] = Resource.fromGrpcResource(r)
        return ResourceGroup(name=rg.name, toolId=rg.toolId, URL=rg.URL,
                             version=rg.version, resources=resources)

    @staticmethod
    def fromGrpcResourceGroupChange(rg: depi_pb2.ResourceGroupChange) -> "ResourceGroup":
        resources: dict[str, Resource] = {}
        for r in rg.resources:
            resources[r.URL] = Resource.fromGrpcResourceChange(r)
        return ResourceGroup(name=rg.name, toolId=rg.toolId, URL=rg.URL,
                             version=rg.version, resources=resources)


class ResourceRef:
    def __init__(self, toolId, resourceGroupURL, url):
        self.toolId: str = toolId
        self.resourceGroupURL: str = resourceGroupURL
        self.URL: str = url

    def __eq__(self, other) -> bool:
        return self.toolId == other.toolId and \
               self.resourceGroupURL == other.resourceGroupURL and \
               self.URL == other.URL

    def __hash__(self) -> int:
        return hash((hash(self.toolId), 
                     hash(self.resourceGroupURL), 
                     hash(self.URL)))

    def copy(self) -> "ResourceRef":
        return ResourceRef(self.toolId, self.resourceGroupURL, self.URL)

    @staticmethod
    def fromResourceGroupAndRes(rg: ResourceGroup, r: Resource) -> "ResourceRef":
        return ResourceRef(toolId=rg.toolId, resourceGroupURL=rg.URL,  url=r.URL)

    def toGrpc(self) -> depi_pb2.ResourceRef:
        return depi_pb2.ResourceRef(
            toolId=self.toolId,
            resourceGroupURL=self.resourceGroupURL,
            URL=self.URL)

    @staticmethod
    def fromGrpc(rr: depi_pb2.ResourceRef) -> "ResourceRef":
        return ResourceRef(toolId=rr.toolId, resourceGroupURL=rr.resourceGroupURL, url=rr.URL)

    @staticmethod
    def fromGrpcResource(res: depi_pb2.Resource) -> "ResourceRef":
        return ResourceRef(toolId=res.toolId, resourceGroupURL=res.resourceGroupURL, url=res.URL)

    def toJson(self) -> dict:
        return {"toolId": self.toolId,
                "resourceGroupURL": self.resourceGroupURL,
                "URL": self.URL}

    @staticmethod
    def fromJson(record: dict) -> "ResourceRef":
        return ResourceRef(toolId=record["toolId"], resourceGroupURL=record["resourceGroupURL"],
                           url=record["URL"])


class Link:
    def __init__(self, fromRes: ResourceRef, toRes: ResourceRef, dirty=False,
                 inferredDirtiness : set[tuple[ResourceRef,str]]|None = None):
        self.fromRes: ResourceRef = fromRes
        self.toRes: ResourceRef = toRes
        self.dirty: bool = dirty
        self.deleted: bool = False
        self.lastCleanVersion: str = ""
        if inferredDirtiness is None:
            self.inferredDirtiness: set[tuple[ResourceRef, str]] = set()
        else:
            self.inferredDirtiness: set[tuple[ResourceRef,str]] = inferredDirtiness

    def __eq__(self, other) -> bool:
        return self.fromRes == other.fromRes and self.toRes == other.toRes

    def __hash__(self) -> int:
        return hash((hash(self.fromRes), hash(self.toRes)))

    def copy(self):
        inferred = [(rr.copy(), lastClean) for (rr, lastClean) in self.inferredDirtiness]
        link = Link(self.fromRes.copy(), self.toRes.copy(), self.dirty, inferred)
        link.deleted = self.deleted
        return link

    def compareFromResURL(self, resURL: str) -> bool:
        if self.fromRes.URL == resURL:
            return True
        sep = config.toolConfig[self.fromRes.toolId].pathSeparator
        if self.fromRes.URL.endswith(sep):
            print("Does {} start with {} ?".format(resURL, self.fromRes.URL))
            return resURL.startswith(self.fromRes.URL)
        else:
            print("Does {} start with {} ?".format(resURL, self.fromRes.URL+sep))
            return resURL.startswith(self.fromRes.URL+sep)

    def hasFromLink(self, rg: ResourceGroup, res: Resource) -> bool:
        return self.fromRes.resourceGroupURL == rg.URL and \
            self.fromRes.toolId == rg.toolId and \
            self.fromRes.URL == res.URL

    def hasFromLinkExt(self, rg: ResourceGroup, res: Resource, pathSeparator) -> bool:
        resURL = res.URL
        if not resURL.startswith(pathSeparator):
            resURL = pathSeparator+resURL

        return self.fromRes.resourceGroupURL == rg.URL and \
            self.fromRes.toolId == rg.toolId and \
            (self.fromRes.URL == res.URL or \
             resURL.startswith(self.fromRes.URL))

    def hasFromLinkRef(self, rr: ResourceRef) -> bool:
        return self.fromRes.resourceGroupURL == rr.resourceGroupURL and \
               self.fromRes.toolId == rr.toolId and \
               self.fromRes.URL == rr.URL

    def hasToLink(self, resGrp: ResourceGroup, res: Resource) -> bool:
        return self.toRes.resourceGroupURL == resGrp.URL and \
               self.toRes.toolId == resGrp.toolId and \
               self.toRes.URL == res.URL

    def hasToLinkRef(self, rr: ResourceRef) -> bool:
        return self.toRes.resourceGroupURL == rr.resourceGroupURL and \
               self.toRes.toolId == rr.toolId and \
               self.toRes.URL == rr.URL

    def toGrpc(self) -> depi_pb2.ResourceLinkRef:
        return depi_pb2.ResourceLinkRef(fromRes=self.fromRes.toGrpc(),
                                        toRes=self.toRes.toGrpc())

    def toJson(self) -> dict:
        return {"fromRes": self.fromRes.toJson(),
                "toRes": self.toRes.toJson(),
                "dirty": self.dirty,
                "deleted": self.deleted,
                "lastCleanVersion": self.lastCleanVersion,
                "inferredDirtiness": [
                    {"res": idRes.toJson(),
                     "lastCleanVersion": lastClean} for (idRes, lastClean) in self.inferredDirtiness]}

    @staticmethod
    def fromGrpc(link: depi_pb2.ResourceLink) -> "Link":
        return Link(ResourceRef.fromGrpcResource(link.fromRes),
                    ResourceRef.fromGrpcResource(link.toRes),
                    link.dirty,
                    [(ResourceRef.fromGrpcResource(inf.resource), inf.lastCleanVersion)
                     for inf in link.inferredDirtiness])

    @staticmethod
    def fromGrpcRef(link: depi_pb2.ResourceLinkRef) -> "Link":
        return Link(ResourceRef.fromGrpc(link.fromRes),
                    ResourceRef.fromGrpc(link.toRes))

    @staticmethod
    def fromJson(record: dict) -> "Link":
        inferredDirtiness = []
        if "inferredDirtiness" in record:
            inferredDirtiness = record["inferredDirtiness"]
        link = Link(ResourceRef.fromJson(record["fromRes"]),
                    ResourceRef.fromJson(record["toRes"]),
                    record["dirty"],
                    set([(ResourceRef.fromJson(rec["res"]), rec["lastCleanVersion"]) for rec in inferredDirtiness]))
        link.deleted = record["deleted"]
        if "lastCleanVersion" in record:
            link.lastCleanVersion = record["lastCleanVersion"]
        return link


class LinkWithResources:
    def __init__(self, fromRg: ResourceGroup, fromRes: Resource,
                 toRg: ResourceGroup, toRes: Resource, dirty=False, lastCleanVersion="",
                 inferredDirtiness: list[tuple[ResourceGroup, Resource, str]] | None = None):
        self.fromResourceGroup: ResourceGroup = fromRg
        self.fromRes: Resource = fromRes
        self.toResourceGroup: ResourceGroup = toRg
        self.toRes: Resource = toRes
        self.dirty: bool = dirty
        self.deleted: bool = False
        self.lastCleanVersion: str = lastCleanVersion
        if inferredDirtiness is None:
            self.inferredDirtiness: list[tuple[ResourceGroup, Resource, str]] = []
        else:
            self.inferredDirtiness: list[tuple[ResourceGroup, Resource, str]] = inferredDirtiness

    def __eq__(self, other) -> bool:
        return self.fromResourceGroup == other.fromResourceGroup and \
               self.fromRes == other.fromRes and self.toRes == other.toRes

    def __hash__(self) -> int:
        return hash((hash(self.fromResourceGroup), hash(self.fromRes), hash(self.toResourceGroup), hash(self.toRes)))

    def compareFromResURL(self, resURL: str) -> bool:
        if self.fromRes.URL == resURL:
            return True
        sep = config.toolConfig[self.fromResourceGroup.toolId].pathSeparator
        if self.fromRes.URL.endswith(sep):
            print("Does {} start with {} ?".format(resURL, self.fromRes.URL))
            return resURL.startswith(self.fromRes.URL)
        else:
            print("Does {} start with {} ?".format(resURL, self.fromRes.URL+sep))
            return resURL.startswith(self.fromRes.URL+sep)

    def hasFromLinkExt(self, resGrp: ResourceGroup, res: Resource) -> bool:
        print("Comparing extended {} {} {} {} to {} {} {} {}".format(
            resGrp.URL, resGrp.toolId, res.URL, res.id,
            self.fromResourceGroup.URL, self.fromResourceGroup.toolId,
            self.fromRes.URL, self.fromRes.id))

        return self.fromResourceGroup.URL == resGrp.URL and \
            self.fromResourceGroup.toolId == resGrp.toolId and \
            self.compareFromResURL(res.URL)

    def hasFromLink(self, resGrp: ResourceGroup, res: Resource) -> bool:
        print("Comparing {} {} {} {} to {} {} {} {}".format(
            resGrp.URL, resGrp.toolId, res.URL, res.id,
            self.fromResourceGroup.URL, self.fromResourceGroup.toolId,
            self.fromRes.URL, self.fromRes.id))

        return self.fromResourceGroup.URL == resGrp.URL and \
            self.fromResourceGroup.toolId == resGrp.toolId and \
            self.fromRes.id == res.id and \
            self.fromRes.URL == res.URL

    def hasFromLinkRef(self, rr: ResourceRef) -> bool:
        return self.fromResourceGroup.URL == rr.resourceGroupURL and \
            self.fromResourceGroup.toolId == rr.toolId and \
            self.fromRes.URL == rr.URL

    def hasToLink(self, resGrp: ResourceGroup, res: Resource) -> bool:
        return self.toResourceGroup.URL == resGrp.URL and \
            self.toResourceGroup.toolId == resGrp.toolId and \
            self.toRes.URL == res.URL

    def hasToLinkRef(self, rr: ResourceRef) -> bool:
        return self.toResourceGroup.URL == rr.resourceGroupURL and \
            self.toResourceGroup.toolId == rr.toolId and \
            self.toRes.URL == rr.URL

    def toLink(self) -> Link:
        fromRef = ResourceRef(toolId=self.fromResourceGroup.toolId,
                              resourceGroupURL=self.fromResourceGroup.URL,
                              url=self.fromRes.URL)

        toRef = ResourceRef(toolId=self.toResourceGroup.toolId,
                            resourceGroupURL=self.toResourceGroup.URL,
                            url=self.toRes.URL)
        infRes = [(ResourceRef.fromResourceGroupAndRes(rg, res), lastClean)
                  for (rg, res, lastClean) in self.inferredDirtiness]
        return Link(fromRef, toRef, self.dirty, set(infRes))

    def toGrpc(self) -> depi_pb2.ResourceLink:
        return depi_pb2.ResourceLink(fromRes=self.fromRes.toGrpc(self.fromResourceGroup),
                                     toRes=self.toRes.toGrpc(self.toResourceGroup),
                                     deleted=self.deleted,
                                     dirty=self.dirty,
                                     lastCleanVersion=self.lastCleanVersion,
                                     inferredDirtiness=[depi_pb2.InferredDirtiness(resource=res.toGrpc(resGrp),
                                                                                   lastCleanVersion=lastClean)
                                                        for (resGrp, res, lastClean) in self.inferredDirtiness])

class ResourceRefPattern:
    def __init__(self, toolId: str, resourceGroupURL: str, URLPattern: str):
        self.toolId: str = toolId
        self.resourceGroupURL: str = resourceGroupURL
        self.URLPattern: str = URLPattern

    @staticmethod
    def fromGrpc(pattern: depi_pb2.ResourceRefPattern) -> "ResourceRefPattern":
        return ResourceRefPattern(pattern.toolId, pattern.resourceGroupURL, pattern.URLPattern)


class ResourceLinkPattern:
    def __init__(self, fromRes: ResourceRefPattern, toRes: ResourceRefPattern):
        self.fromRes: ResourceRefPattern = fromRes
        self.toRes: ResourceRefPattern = toRes

    @staticmethod
    def fromGrpc(pattern: depi_pb2.ResourceLinkPattern) -> "ResourceLinkPattern":
        return ResourceLinkPattern(ResourceRefPattern.fromGrpc(pattern.fromRes),
                                   ResourceRefPattern.fromGrpc(pattern.toRes))
