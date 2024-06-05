from depi_server.model.depi_model import Resource, ResourceRef, ResourceGroup, Link, LinkWithResources, ResourceRefPattern, \
    ResourceLinkPattern, ResourceGroupChange

class DepiDB:
    def __init__(self, config):
        self.config = config

    def getBranch(self, name: str):
        return DepiBranch()

    def getTag(self, name: str):
        return DepiBranch()

    def branchExists(self, name: str) -> bool:
        return False

    def createBranch(self, name: str, fromBranch: str):
        oldBranch = self.getBranch(fromBranch)
        oldBranch.createBranch(name)

    def createBranchFromTag(self, name: str, fromTag: str):
        pass

    def createTag(self, name: str, fromBranch: str):
        oldBranch = self.getBranch(fromBranch)
        oldBranch.createTag(name)

    def loadAllState(self):
        pass

    def getBranchList(self):
        return []

    def getTagList(self):
        return []

class DepiBranch:
    def __init__(self, name):
        self.name = name
        return

    def createBranch(self, name: str) -> "DepiBranch":
        pass

    def createTag(self, name: str) -> "DepiBranch":
        pass

    def markResourcesClean(self, resourceRefs: list[ResourceRef], propagateCleanliness: bool):
        pass

    def markLinksClean(self, links: list[Link], propagateCleanliness: bool):
        pass

    def markInferredDirtinessClean(self, link: Link, dirtinessSource: ResourceRef, propagateCleanliness: bool) -> list[(Link,ResourceRef)]:
        pass

    def addResource(self, rg: ResourceGroup, rr: Resource|None):
        pass

    def addResources(self, resources: list[tuple[ResourceGroup, Resource]]):
        pass

    def addLink(self, newLink: LinkWithResources) -> bool:
        return False

    def addLinks(self, links: list[LinkWithResources]) -> bool:
        return False

    def removeResourceRef(self, rr: ResourceRef) -> bool:
        return False

    def getResourceGroup(self, toolId: str, URL: str) -> ResourceGroup | None:
        return None

    def getResource(self, rr: ResourceRef) -> tuple[ResourceGroup, Resource] | None:
        return None

    def getResourceById(self, toolId: str, resourceGroupURL: str, resId: str) -> tuple[ResourceGroup, Resource] | None:
        return None

    def getDependencyGraph(self, rr: ResourceRef, upstream: bool, maxDepth: int) -> list[LinkWithResources]:
        return []

    def removeLink(self, delLink: Link) -> bool:
        return False

    def getResourceGroupVersion(self, toolId: str, URL: str) -> str:
        return ""

    def getResourceGroups(self) -> list[ResourceGroup]:
        return []

    def getResourceByRef(self, rr: ResourceRef) -> Resource | None:
        return None

    def isResourceDeleted(self, rr: ResourceRef) -> bool:
        return False

    def validateResourceRef(self, rr: ResourceRef) -> ResourceRef:
        return rr

    def getResources(self, resPatterns: list[ResourceRefPattern], includeDeleted: bool) -> list[(ResourceGroup,Resource)]:
        return []

    def getResourcesAsStream(self, resPatterns: list[ResourceRefPattern]):
        return []

    def getLinks(self, linkPatterns: list[ResourceLinkPattern]) -> list[LinkWithResources]:
        return []

    def getLinksAsStream(self, linkPatterns: list[ResourceLinkPattern]):
        return []

    def expandLinks(self, linkPatterns: list[Link]) -> list[LinkWithResources]:
        return []

    def getAllLinks(self) -> list[LinkWithResources]:
        return []

    def getAllLinksAsStream(self):
        return []

    def getDirtyLinks(self, resourceGroup: ResourceGroup, withInferred: bool) -> list[LinkWithResources]:
        return []

    def getDirtyLinksAsStream(self, resourceGroup: ResourceGroup, withInferred: bool):
        return []

    def updateResourceGroup(self, resourceGroupChange: ResourceGroupChange) -> list[Link]:
        pass

    def editResourceGroup(self, oldResourceGroup: ResourceGroup, newResourceGroup: ResourceGroup):
        pass

    def removeResourceGroup(self, toolId: str, URL: str):
        pass

    def saveBranchState(self):
        pass

