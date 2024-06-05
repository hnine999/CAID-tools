import os
import re
import json
from depi_server.model.depi_model import Resource, ResourceGroup, Link, LinkWithResources, ResourceRef, ResourceGroupChange, ChangeType, \
    ResourceLinkPattern, ResourceRefPattern
from depi_server.db.depi_db import DepiDB, DepiBranch
import logging

class MemJsonDB(DepiDB):
    def __init__(self, config):
        super().__init__(config)
        self.stateDir: str = config.dbConfig["stateDir"]

        self.branches: dict[str, "MemBranch"] = {"main": MemBranch(self, "main")}
        self.tags: dict[str, "MemBranch"] = {}

        self.loadAllState()

    def getBranch(self, name: str) -> "MemBranch":
        if name in self.branches:
            return self.branches[name]

    def getTag(self, name: str) -> "MemBranch":
        if name in self.tags:
            return self.tags[name]

    def branchExists(self, name: str) -> bool:
        if name in self.branches:
            return True
        else:
            return False

    def tagExists(self, name: str) -> bool:
        if name in self.tags:
            return True
        else:
            return False

    def createBranch(self, name: str, fromBranch: str):
        if self.branchExists(name):
            raise RuntimeError("Branch {} already exists".format(name))

        if not self.branchExists(fromBranch):
            raise RuntimeError("Branch {} does not exist".format(fromBranch))

        newBranch = self.getBranch(fromBranch).copy(name)
        self.branches[name] = newBranch
        newBranch.saveBranchState()

        return newBranch

    def createBranchFromTag(self, name: str, fromTag: str):
        if self.branchExists(name):
            raise RuntimeError("Branch {} already exists".format(name))

        if not self.tagExists(fromTag):
            raise RuntimeError("Tag {} does not exist".format(fromTag))

        newBranch = self.getTag(fromTag).copy(name)
        self.branches[name] = newBranch
        newBranch.saveBranchState()

        return newBranch

    def createTag(self, name: str, fromBranch: str):
        if self.tagExists(name):
            raise RuntimeError("Tag {} already exists".format(name))

        if not self.branchExists(fromBranch):
            raise RuntimeError("Branch {} does not exist".format(fromBranch))

        newBranch = self.branches[fromBranch].copy(name)
        newBranch.isTag = True
        self.tags[name] = newBranch

        tagsDir = self.stateDir+"/tags"
        if not os.path.exists(tagsDir):
            os.mkdir(tagsDir)
        out_file = open(tagsDir+"/"+name, "w")

        json.dump({ "branch": fromBranch, "version": self.branches[fromBranch].lastVersion}, out_file)
        out_file.close()

    def loadAllState(self):
        if os.path.exists(self.stateDir) and not os.path.isdir(self.stateDir):
            os.remove(self.stateDir)
        if not os.path.exists(self.stateDir):
            os.makedirs(self.stateDir)
            self.branches = {"main": MemBranch(self, "main", 0)}
            self.branches["main"].saveBranchState()

        for branch in os.listdir(self.stateDir):
            if branch == "tags":
                continue
            latestVer = 0
            branchDir = self.stateDir + "/" + branch
            if os.path.isdir(branchDir):
                for file in os.listdir(branchDir):
                    try:
                        ver = int(file)
                        if ver > latestVer:
                            latestVer = ver
                    except Exception:
                        pass
            else:
                logging.debug("Extraneous file in .state: {}".format(branch))

            if latestVer > 0:
                in_file = open(branchDir + "/" + str(latestVer), "r")
                self.branches[branch] = MemBranch.fromJson(self, json.load(in_file))
                logging.debug("Loaded branch links: {}".format(self.branches[branch].links))
                in_file.close()
            else:
                self.branches[branch] = MemBranch(self, branch, 0)

        if os.path.exists(self.stateDir+"/tags"):
            for tag in os.listdir(self.stateDir+"/tags"):
                in_file = open(self.stateDir+"/tags/"+tag)
                tagJson = json.load(in_file)
                in_file.close()
                branch_name = tagJson["branch"]
                branch_version = tagJson["version"]
                in_file = open(self.stateDir+"/"+branch_name+"/"+str(branch_version))
                tagBranch = MemBranch.fromJson(self, json.load(in_file))
                tagBranch.isTag = True
                self.tags[tag] = tagBranch
                in_file.close()

    def getBranchList(self):
        return list(self.branches.keys())

    def getTagList(self):
        return list(self.tags.keys())

class MemBranch(DepiBranch):
    def __init__(self, db: MemJsonDB, name: str, lastVersion=0, parentName="", parentVersion=0,
                 links: set[Link] | None = None, tools: dict[str, dict[str, ResourceGroup]] | None = None):
        super().__init__(name)
        self.db: MemJsonDB = db
        self.isTag = False
        self.lastVersion: int = lastVersion
        self.parentName: str = parentName
        self.parentVersion: int = parentVersion
        if links is None:
            self.links: set[Link] = set()
        else:
            self.links: set[Link] = links
        if tools is None:
            self.tools: dict[str, dict[str, ResourceGroup]] = {}
        else:
            self.tools: dict[str, dict[str, ResourceGroup]] = tools

    def linkResMatches(self, pathSeparator, linkURL, resURL):
        if linkURL.endswith(pathSeparator):
            return resURL.startswith(linkURL)
        else:
            return resURL.startswith(linkURL+pathSeparator)

    def linkToLinkWithResources(self, link):
        print("Fetching resource {} {} {}".format(link.fromRes.toolId, link.fromRes.resourceGroupURL, link.fromRes.URL))
        fromRg, fromRes = self.getResource(link.fromRes, True)
        print("Fetching resource {} {} {}".format(link.toRes.toolId, link.toRes.resourceGroupURL, link.toRes.URL))
        toRg, toRes = self.getResource(link.toRes, True)
        inferred: list[tuple[ResourceGroup,Resource,str]] = []
        for (rr, lastClean) in link.inferredDirtiness:
            (rg, res) = self.getResource(rr, True)
            inferred.append((rg, res, lastClean))
        result = LinkWithResources(fromRg, fromRes, toRg, toRes, link.dirty, link.lastCleanVersion, inferred)
        result.deleted = link.deleted
        return result


    def copy(self, newName: str) -> "MemBranch":
        newCopy = MemBranch(self.db, newName, 0, self.name, self.lastVersion)
        newTools = {}
        for (toolId, tool) in self.tools.items():
            newTool = {}
            for (rgURL, rg) in tool.items():
                newResources = {}
                for r in rg.resources.values():
                    newRes = Resource(name=r.name, id=r.id, URL=r.URL, deleted=r.deleted)
                    newResources[newRes.URL] = newRes
                newRg = ResourceGroup(name=rg.name, toolId=rg.toolId, version=rg.version, URL=rg.URL,
                                      resources=newResources)
                newTool[rgURL] = newRg
            newTools[toolId] = newTool

        newCopy.tools = newTools

        newLinks = set([l.copy() for l in self.links])
        newCopy.links = newLinks

        return newCopy

    def saveBranchState(self):
        if self.isTag:
            raise Exception("Cannot save a tag")
        branchDir = self.db.stateDir + "/" + self.name
        if not os.path.exists(branchDir):
            os.makedirs(branchDir)

        self.lastVersion += 1
        branchJS = self.toJson()
        out_file = open(branchDir+"/"+str(self.lastVersion), "w")
        json.dump(branchJS, out_file, indent=2)
        out_file.close()

    def markLinkDirty(self, link: Link, currentVersion: str):
        if not link.dirty:
            link.lastCleanVersion = currentVersion

        link.dirty = True
        linksUpdated: set[ResourceRef] = set()

        linksToProcess: set[ResourceRef] = set()
        linksToProcess.add(link.toRes)

        linkMap = {}
        for currLink in self.links:
            if currLink.fromRes not in linkMap:
                linkMap[currLink.fromRes] = [currLink]
            else:
                linkMap[currLink.fromRes].append(currLink)

        while len(linksToProcess) > 0:
            infLink = linksToProcess.pop()
            linksUpdated.add(infLink)
            if infLink in linkMap:
                for currLink in linkMap[infLink]:
                    if currLink != link:
                        found = False
                        for (res, lastClean) in currLink.inferredDirtiness:
                            if res == link.fromRes:
                                found = True
                                break
                        if not found:
                            currLink.inferredDirtiness.add((link.fromRes, currentVersion))
                            if currLink.toRes not in linksUpdated:
                                linksToProcess.add(currLink.toRes)

    def updateResourceGroup(self, resourceGroupChange: ResourceGroupChange) -> list[Link]:
        tool = self.tools.get(resourceGroupChange.toolId)
        if tool is None:
            tool = {}
            self.tools[resourceGroupChange.toolId] = tool

        toolConfig = self.db.config.getToolConfig(resourceGroupChange.toolId)
        pathSeparator = toolConfig.pathSeparator

        key = resourceGroupChange.URL
        resourceGroup = tool.get(key)

        linkedResourceGroupsToUpdate = set()

        if resourceGroup is None:
            logging.debug("Adding resource group (this should never happen?)")
            resourceGroup = ResourceGroup.fromGrpcResourceGroupChange(
                resourceGroupChange)
            tool[key] = resourceGroup
        else:
            originalVersion = resourceGroup.version
            resourceGroup.version = resourceGroupChange.version
            for resourceChange in resourceGroupChange.resources.values():
                if resourceChange.changeType == ChangeType.Added or \
                   resourceChange.changeType == ChangeType.Modified:
                    logging.debug("Processing add/modify change for resource {}".format(
                        resourceChange.URL))
                    for link in self.links:
                        if link.hasFromLinkExt(resourceGroup, resourceChange.toResource(), pathSeparator):
                            logging.debug("Link from {} {} {} -> {} {} {} is dirty".format(
                                link.fromRes.toolId,
                                link.fromRes.resourceGroupURL,
                                link.fromRes.URL, link.toRes.toolId,
                                link.toRes.resourceGroupURL,
                                link.toRes.URL))
                            self.markLinkDirty(link, originalVersion)
                            linkedResourceGroupsToUpdate.add(link)
                if resourceChange.changeType == ChangeType.Renamed or \
                   (resourceChange.changeType == ChangeType.Modified and
                    (resourceChange.URL != resourceChange.newURL or
                     resourceChange.name != resourceChange.newName or
                     resourceChange.id != resourceChange.newId)):
                    logging.debug("Processing rename change for resource {}".format(
                        resourceChange.URL))
                    for link in self.links:
                        resource = resourceChange.toResource()
                        if link.hasFromLinkExt(resourceGroup, resource, pathSeparator):
                            fromRgRes = self.getResource(link.fromRes)
                            if fromRgRes is not None and fromRgRes[1].URL == resourceChange.URL:
                                del resourceGroup.resources[fromRgRes[1].URL]
                                fromRgRes[1].name = resourceChange.newName
                                fromRgRes[1].URL = resourceChange.newURL
                                fromRgRes[1].id = resourceChange.newId
                                resourceGroup.resources[fromRgRes[1].URL] = fromRgRes[1]
                                link.fromRes.URL = resourceChange.newURL
                                linkedResourceGroupsToUpdate.add(link)
                        elif link.hasToLink(resourceGroup, resource):
                            toRgRes = self.getResource(link.toRes)
                            del resourceGroup.resources[toRgRes[1].URL]
                            toRgRes[1].name = resourceChange.newName
                            toRgRes[1].URL = resourceChange.newURL
                            toRgRes[1].id = resourceChange.newId
                            resourceGroup.resources[toRgRes[1].URL] = toRgRes[1]
                            link.toRes.URL = resourceChange.newURL
                        for inferred in link.inferredDirtiness:
                            if inferred[0].toolId == resourceGroupChange.toolId and \
                               inferred[0].resourceGroupURL == resourceGroupChange.URL and \
                               inferred[0].URL == resourceChange.URL:
                                inferred[0].URL = resourceChange.newURL
                    if resourceChange.URL in resourceGroup.resources:
                        res = resourceGroup.resources[resourceChange.URL]
                        del resourceGroup.resources[resourceChange.URL]
                        res.URL = resourceChange.newURL
                        resourceGroup.resources[resourceChange.newURL] = res
                elif resourceChange.changeType == ChangeType.Removed:
                    logging.debug("Processing delete for resource {}".format(
                        resourceChange.URL))
                    links_to_remove = []
                    remove_resource = True
                    for link in self.links:
                        resource = resourceChange.toResource()
                        if link.hasFromLinkExt(resourceGroup, resource, pathSeparator):
                            self.markLinkDirty(link, originalVersion)
                            fromRgRes = self.getResource(link.fromRes, True)
                            if fromRgRes is not None and fromRgRes[1].URL == resourceChange.URL:
                                fromRgRes[1].deleted = True
                                link.deleted = True
                                remove_resource = False
                            linkedResourceGroupsToUpdate.add(link)
                        elif link.hasToLink(resourceGroup, resource):
                            toRgRes = self.getResource(link.toRes)
                            if toRgRes is not None:
                                toRgRes[1].deleted = True
                            links_to_remove.append(link)
                        newInferred = set()
                        for (infRes, lastClean) in link.inferredDirtiness:
                            if infRes.toolId == resourceGroup.toolId and \
                               infRes.resourceGroupURL == resourceGroup.URL and \
                               infRes.URL == resource.URL:
                                continue
                            newInferred.add((infRes, lastClean))
                        link.inferredDirtiness = newInferred
                    for link in links_to_remove:
                        self.links.remove(link)
                        if remove_resource:
                            resourceGroup.resources.pop(resourceChange.URL)

            logging.debug("Updating resource group ")
            # TODO: figure out how to merge old with new


        return list(linkedResourceGroupsToUpdate)

    def markResourcesClean(self, resourceRefs: list[ResourceRef], propagateCleanliness: bool):
        for rr in resourceRefs:
            for link in self.links:
                if link.hasToLinkRef(rr):
                    link.dirty = False
                    link.lastCleanVersion = ""
                    try:
                        link.inferredDirtiness.remove(rr)
                    except ValueError:
                        pass

    def markLinksClean(self, cleanLinks: list[Link], propagateCleanliness: bool):
        for cl in cleanLinks:
            links_to_delete = []
            for link in self.links:
                if link.hasFromLinkRef(cl.fromRes) and \
                   link.hasToLinkRef(cl.toRes):
                    link.dirty = False
                    link.lastCleanVersion = ""
                    if link.deleted:
                        links_to_delete.append(link)
            for link in links_to_delete:
                self.links.remove(link)
                resInfo = self.getResource(link.fromRes, includeDeleted=True)
                if resInfo is None:
                    continue

                (rg, res) = resInfo
                delete_res = res.deleted
                for lk2 in self.links:
                    if lk2.fromRes == link.fromRes and not lk2.deleted:
                        delete_res = False
                if delete_res:
                    rg.resources.pop(res.URL)
                    for lk2 in self.links:
                        inf_to_remove = []
                        for (rr,lastClean) in lk2.inferredDirtiness:
                            if rr.toolId == rg.toolId and rr.resourceGroupURL == rg.URL and \
                               rr.URL == res.URL:
                                inf_to_remove.append((rr,lastClean))
                        for inf_rem in inf_to_remove:
                            lk2.inferredDirtiness.remove(inf_rem)

            if propagateCleanliness:
                self.markInferredDirtinessClean(cl, cl.fromRes, propagateCleanliness)

    def markInferredDirtinessClean(self, linkToClean: Link, dirtinessSource: ResourceRef,
                                   propagateCleanliness: bool) -> list[(Link,ResourceRef)]:
        targetLink = None
        for link in self.links:
            if link.hasFromLinkRef(linkToClean.fromRes) and \
               link.hasToLinkRef(linkToClean.toRes):
                targetLink = link
                break

        if targetLink is None:
            return []

        cleaned_links = []
        if not propagateCleanliness:
            updatedDirtiness = set()
            for (res, lastClean) in targetLink.inferredDirtiness:
                if res != dirtinessSource:
                    updatedDirtiness.add((res, lastClean))
                else:
                    cleaned_links.append((targetLink, res))
            targetLink.inferredDirtiness = updatedDirtiness
        else:
            workQueue = [targetLink]
            processedLinks = set()

            while len(workQueue) > 0:
                currLink = workQueue.pop()
                processedLinks.add(currLink)
                updatedDirtiness = set()
                for (res, lastClean) in currLink.inferredDirtiness:
                    if  res != dirtinessSource:
                        updatedDirtiness.add((res, lastClean))
                    else:
                        cleaned_links.append((currLink, res))
                currLink.inferredDirtiness = updatedDirtiness

                for link in self.links:
                    if link.fromRes == currLink.toRes and \
                       link not in processedLinks:
                        workQueue.append(link)

        return cleaned_links

    def addResource(self, rg: ResourceGroup, rr: Resource|None) -> bool:
        tool = self.tools.get(rg.toolId)
        if tool is None:
            tool: dict[str, ResourceGroup] = {}
            self.tools[rg.toolId] = tool

        key = rg.URL
        resourceGroup = tool.get(key)
        if resourceGroup is None:
            tool[key] = rg
            resourceGroup = rg
        if rr is not None and rr.URL not in resourceGroup.resources:
            resourceGroup.resources[rr.URL] = Resource(rr.name, rr.id, rr.URL)
            return True
        elif rr is not None:
            res = resourceGroup.resources[rr.URL]
            if res.deleted:
                res.deleted = False
                return True
            else:
                return False

    def addResources(self, resources: list[tuple[ResourceGroup, Resource|None]]):
        for (rg,res) in resources:
            self.addResource(rg, res)

    def addLink(self, newLinkRes: LinkWithResources) -> bool:
        self.addResource(newLinkRes.fromResourceGroup, newLinkRes.fromRes)
        self.addResource(newLinkRes.toResourceGroup, newLinkRes.toRes)
        fromRR = ResourceRef(toolId=newLinkRes.fromResourceGroup.toolId,
                             resourceGroupURL=newLinkRes.fromResourceGroup.URL,
                             url=newLinkRes.fromRes.URL)
        toRR = ResourceRef(toolId=newLinkRes.toResourceGroup.toolId,
                             resourceGroupURL=newLinkRes.toResourceGroup.URL,
                             url=newLinkRes.toRes.URL)
        infDirty = set([(ResourceRef.fromResourceGroupAndRes(rg, res), newLinkRes.lastCleanVersion)
                        for (rg, res) in newLinkRes.inferredDirtiness])
        newLink = Link(fromRR, toRR, newLinkRes.dirty, infDirty)
        if newLink in self.links:
            for link in self.links:
                if link == newLink:
                    if link.deleted:
                        link.deleted = False
                        return True
                    else:
                        return False

        self.links.add(newLink)
        return True

    def addLinks(self, newLinks: list[LinkWithResources]) -> bool:
        for link in newLinks:
            self.addLink(link)

    def removeResourceRef(self, rr: ResourceRef) -> bool:
        logging.debug("Removing resource ref {} {} {}".format(
            rr.toolId, rr.resourceGroupURL, rr.URL))
        tool = self.tools.get(rr.toolId)
        if tool is None:
            logging.debug("No such tool")
            return False

        key = rr.resourceGroupURL
        resourceGroup = tool.get(key)
        if resourceGroup is None:
            logging.debug("No such resource group")
            return False
        if rr.URL not in resourceGroup.resources:
            logging.debug("No such resource URL")
            return False
        else:
            res = resourceGroup.resources[rr.URL]
            if res.deleted:
                logging.debug("Already deleted")
                return False
            else:
                logging.debug("Deleting")
                res.deleted = True
                # TODO - Verify that we actually want to mark the link as deleted
                for link in self.links:
                    if link.hasFromLinkRef(rr) or link.hasToLinkRef(rr):
                        link.deleted = True
                return True


    def getResource(self, rr: ResourceRef, includeDeleted=False) -> tuple[ResourceGroup, Resource] | None:
        tool = self.tools.get(rr.toolId)
        if tool is None:
            return None

        key = rr.resourceGroupURL
        resourceGroup = tool.get(key)
        if resourceGroup is None:
            return None
        if rr.URL not in resourceGroup.resources:
            return None
        else:
            res = resourceGroup.resources[rr.URL]
            if res.deleted and not includeDeleted:
                return None
            else:
                return resourceGroup, res

    def getResourceById(self, toolId: str, resourceGroupURL: str, resId: str) -> tuple[ResourceGroup, Resource] | None:
        tool = self.tools.get(toolId)
        if tool is None:
            return None

        key = resourceGroupURL
        resourceGroup = tool.get(key)
        if resourceGroup is None:
            return None

        for res in resourceGroup.resources.values():
            if res.id == resId:
                return resourceGroup, res
        return None

    def getLinksWithResource(self, rr: ResourceRef, useTo: bool) -> list[Link]:
        links = []

        for link in self.links:
            if link.deleted:
                continue

            if (not useTo and link.fromRes == rr) or (useTo and link.toRes == rr):
                links.append(link)

        return links

    def getDependencyGraph(self, rr: ResourceRef, upstream: bool, maxDepth: int) -> list[LinkWithResources]:
        processedLinks = set()

        workLinks = [(l, 1) for l in self.getLinksWithResource(rr, upstream)]
        links = []

        while len(workLinks) > 0:
            newWorkLinks = []
            for (link, depth) in workLinks:
                if link not in processedLinks and (maxDepth <= 0 or depth <= maxDepth):
                    processedLinks.add(link)
                    links.append(link)
                    if upstream:
                        searchLink = link.fromRes
                    else:
                        searchLink = link.toRes
                    dependencies = self.getLinksWithResource(searchLink, upstream)
                    for depLink in dependencies:
                        if depLink not in processedLinks:
                            newWorkLinks.append((depLink, depth+1))
            workLinks = newWorkLinks

        return [self.linkToLinkWithResources(l) for l in links]

    def removeLink(self, delLink: Link) -> bool:
        logging.debug("Removing link: {}".format(delLink.toJson()))
        links_to_delete = []
        link_was_deleted = False
        for link in self.links:
            if link.fromRes.toolId == delLink.fromRes.toolId and \
               link.fromRes.resourceGroupURL == delLink.fromRes.resourceGroupURL and \
               link.fromRes.URL == delLink.fromRes.URL and \
               link.toRes.toolId == delLink.toRes.toolId and \
               link.toRes.resourceGroupURL == delLink.toRes.resourceGroupURL and \
               link.toRes.URL == delLink.toRes.URL:
                links_to_delete.append(link)
                link_was_deleted = True
                logging.debug("Found matching link")
        for link in links_to_delete:
            self.links.remove(link)

        logging.debug("No match at all")
        return link_was_deleted

    def editResourceGroup(self, oldResourceGroup: ResourceGroup, newResourceGroup: ResourceGroup):
        if oldResourceGroup.toolId in self.tools:
            if oldResourceGroup.URL in self.tools[oldResourceGroup.toolId]:
                rg = self.tools[oldResourceGroup.toolId][oldResourceGroup.URL]
                rg.version = newResourceGroup.version
                rg.toolId = newResourceGroup.toolId
                rg.URL = newResourceGroup.URL
                rg.name = newResourceGroup.name

                if oldResourceGroup.toolId != newResourceGroup.toolId or \
                   oldResourceGroup.URL != newResourceGroup.URL:
                    self.tools[oldResourceGroup.toolId].pop(oldResourceGroup.URL, None)
                    if newResourceGroup.toolId not in self.tools:
                        self.tools[newResourceGroup.toolId] = {}
                    self.tools[newResourceGroup.toolId][newResourceGroup.URL] = rg

    def removeResourceGroup(self, toolId: str, URL: str):
        if toolId in self.tools:
            if URL in self.tools[toolId]:
                self.tools[toolId].pop(URL)
            remove_links = []
            for link in self.links:
                if (link.fromRes.toolId == toolId and link.fromRes.resourceGroupURL == URL) or \
                   (link.toRes.toolId == toolId and link.toRes.resourceGroupURL == URL):
                    remove_links.append(link)
            for link in remove_links:
                self.links.remove(link)

    def getResourceGroupVersion(self, toolId: str, URL: str) -> str:
        if toolId in self.tools:
            if URL in self.tools[toolId]:
                return self.tools[toolId][URL].version
        return ""

    def getResourceGroup(self, toolId: str, URL: str) -> ResourceGroup|None:
        if toolId in self.tools:
            if URL in self.tools[toolId]:
                return self.tools[toolId][URL]
        return None

    def getResourceGroups(self) -> list[ResourceGroup]:
        resourceGroups = []
        for tool in self.tools.values():
            for rg in tool.values():
                resourceGroups.append(rg)
        return resourceGroups

    def getResourceByRef(self, rr: ResourceRef) -> Resource | None:
        tool = self.tools.get(rr.toolId)
        if tool is None:
            return None

        rg = tool.get(rr.resourceGroupURL)
        if rg is None:
            return None

        r = rg.getResource(rr.URL)
        return r

    def isResourceDeleted(self, rr: ResourceRef) -> bool:
        res = self.getResourceByRef(rr)
        return res.deleted

    def validateResourceRef(self, rr: ResourceRef) -> Resource | None:
        res = self.getResourceByRef(rr)
        if res is None:
            return None
        rr.deleted = res.deleted
        return None

    def getResources(self, resPatterns: list[ResourceRefPattern], includeDeleted: bool) -> list[(ResourceGroup, Resource)]:
        resources = []

        patterns = []
        for pattern in resPatterns:
            patterns.append({"pattern": pattern,
                             "regex": re.compile(pattern.URLPattern)})

        for toolId, tool in self.tools.items():
            found = False
            for pattern in patterns:
                if pattern["pattern"].toolId == toolId:
                    found = True
                    break

            if not found:
                continue

            for rg in tool.values():
                for pattern in patterns:
                    if pattern["pattern"].resourceGroupURL == rg.URL:
                        for res in rg.resources.values():
                            if (not includeDeleted) and res.deleted:
                                continue

                            m = pattern["regex"].match(res.URL)
                            if m is not None:
                                resources.append((rg,res))

        return resources

    def getResourcesAsStream(self, resPatterns: list[ResourceRefPattern]):
        patterns = []
        for pattern in resPatterns:
            patterns.append({"pattern": pattern,
                             "regex": re.compile(pattern.URLPattern)})

        for toolId, tool in self.tools.items():
            found = False
            for pattern in patterns:
                if pattern["pattern"].toolId == toolId:
                    found = True
                    break

            if not found:
                continue

            for rg in tool.values():
                for pattern in patterns:
                    if pattern["pattern"].resourceGroupURL == rg.URL:
                        for res in rg.resources.values():
                            if res.deleted:
                                continue

                            m = pattern["regex"].match(res.URL)
                            if m is not None:
                                yield rg, res

    def getLinks(self, linkPatterns: list[ResourceLinkPattern]) -> list[LinkWithResources]:
        links = []

        patterns = []
        for pattern in linkPatterns:
            fromRegex = re.compile(pattern.fromRes.URLPattern)
            toRegex = re.compile(pattern.toRes.URLPattern)
            patterns.append({"pattern": pattern, "fromRegex": fromRegex,
                            "toRegex": toRegex})

        for link in self.links:
            if link.deleted:
                continue
            for pattern in patterns:
                if link.fromRes.toolId != pattern["pattern"].fromRes.toolId or \
                        link.fromRes.resourceGroupURL != pattern["pattern"].fromRes.resourceGroupURL or \
                        link.toRes.toolId != pattern["pattern"].toRes.toolId or \
                        link.toRes.resourceGroupURL != pattern["pattern"].toRes.resourceGroupURL:
                    continue

                m = pattern["fromRegex"].match(link.fromRes.URL)
                if m is not None:
                    m = pattern["toRegex"].match(link.toRes.URL)
                    if m is not None:
                        links.append(self.linkToLinkWithResources(link))
        return links

    def getLinksAsStream(self, linkPatterns: list[ResourceLinkPattern]):
        patterns = []
        for pattern in linkPatterns:
            fromRegex = re.compile(pattern.fromRes.URLPattern)
            toRegex = re.compile(pattern.toRes.URLPattern)
            patterns.append({"pattern": pattern, "fromRegex": fromRegex,
                             "toRegex": toRegex})

        for link in self.links:
            if link.deleted:
                continue
            for pattern in patterns:
                if link.fromRes.toolId != pattern["pattern"].fromRes.toolId or \
                        link.fromRes.resourceGroupURL != pattern["pattern"].fromRes.resourceGroupURL or \
                        link.toRes.toolId != pattern["pattern"].toRes.toolId or \
                        link.toRes.resourceGroupURL != pattern["pattern"].toRes.resourceGroupURL:
                    continue

                m = pattern["fromRegex"].match(link.fromRes.URL)
                if m is not None:
                    m = pattern["toRegex"].match(link.toRes.URL)
                    if m is not None:
                        yield self.linkToLinkWithResources(link)

    def expandLinks(self, linksToExpand: list[Link]) -> list[LinkWithResources]:
        return [self.linkToLinkWithResources(link) for link in linksToExpand]

    def getAllLinks(self, includeDeleted=False) -> list[LinkWithResources]:
        links = []

        logging.debug("self.links = {}".format(self.links))
        for link in self.links:
            if link.deleted and not includeDeleted:
                continue
            links.append(self.linkToLinkWithResources(link))
        return links

    def getAllLinksAsStream(self, includeDeleted=False):
        logging.debug("self.links = {}".format(self.links))
        for link in self.links:
            if link.deleted and not includeDeleted:
                continue
            yield self.linkToLinkWithResources(link)

    def getDirtyLinks(self, resourceGroup: ResourceGroup, withInferred: bool) -> list[LinkWithResources]:
        links = []

        for link in self.links:
            if link.deleted:
                continue
            toRg, toRes = self.getResource(link.toRes)
            includeLink = False
            if (toRg.toolId == resourceGroup.toolId and toRg.URL == resourceGroup.URL and
                    (link.dirty or (withInferred and len(link.inferredDirtiness) > 0))):
                includeLink = True
#            elif withInferred:
#                for (infDirty, lastClean) in link.inferredDirtiness:
#                    if infDirty.toolId == resourceGroup.toolId and infDirty.resourceGroupURL == resourceGroup.URL:
#                        includeLink = True
#                        break

            if includeLink:
                links.append(self.linkToLinkWithResources(link))
        return links

    def getDirtyLinksAsStream(self, resourceGroup: ResourceGroup, withInferred: bool):
        for link in self.links:
            if link.deleted:
                continue
            toRg, toRes = self.getResource(link.toRes)
            includeLink = False
            if toRg.toolId == resourceGroup.toolId and toRg.URL == resourceGroup.URL:
                includeLink = True
            elif withInferred:
                for (infDirty, lastClean) in link.inferredDirtiness:
                    if infDirty.toolId == resourceGroup.toolId and infDirty.resourceGroupURL == resourceGroup.URL:
                        includeLink = True
                        break

            if includeLink:
                yield self.linkToLinkWithResources(link)

    @staticmethod
    def toolsToJson(tools):
        toolsJS = {}
        for tool in tools:
            toolRGJS = {}
            for rg_key in tools[tool]:
                toolRGJS[rg_key] = tools[tool][rg_key].toJson()
            toolsJS[tool] = toolRGJS
        return toolsJS

    def toJson(self):
        return {"name": self.name, "lastVersion": self.lastVersion,
                "parentName": self.parentName,
                "parentVersion": self.parentVersion,
                "links": [lk.toJson() for lk in self.links],
                "tools": MemBranch.toolsToJson(self.tools)}

    @staticmethod
    def toolsFromJson(tools):
        new_tools = {}
        for tool in tools:
            toolRGS = {}
            for rg_key in tools[tool]:
                toolRGS[rg_key] = ResourceGroup.fromJson(tools[tool][rg_key])
            new_tools[tool] = toolRGS
        return new_tools

    @staticmethod
    def fromJson(db: MemJsonDB, record: dict) -> "MemBranch":
        newBranch = MemBranch(db, record["name"], record["lastVersion"],
                         record["parentName"],
                         record["parentVersion"],
                         [],
                         MemBranch.toolsFromJson(record["tools"]))
        links = set()
        for lk in record["links"]:
            links.add(Link.fromJson(lk))
        newBranch.links = links
        return newBranch

