from depi_server.model.depi_model import Resource, ResourceRef, ResourceGroup, Link, LinkWithResources, ResourceGroupChange, ChangeType, \
    ResourceRefPattern, ResourceLinkPattern
from depi_server.db.depi_db import DepiDB, DepiBranch
import MySQLdb
import MySQLdb.cursors
import re
import logging
from threading import Lock

global config


class DoltDB(DepiDB):
    def __init__(self, config):
        super().__init__(config)
        self.db = self._createDBConnection()
        self.pool_lock = Lock()
        self.connections: list[MySQLdb.Connection] = []
        self.database = self.config.dbConfig.get("database", "depi")
        for i in range(0, self.config.dbConfig.get("pool_size", 10)):
            self.connections.append(self._createDBConnection())

        mainBranch = DoltBranch("main", config, self, False)
        self.branches = {"main": mainBranch}

    def shutdown(self):
        for conn in self.connections:
            conn.close()

    def _createDBConnection(self) -> MySQLdb.Connection:
        return MySQLdb.connect(host=self.config.dbConfig.get("host", "127.0.0.1"),
                               port=self.config.dbConfig.get("port", 3306),
                               user=self.config.dbConfig.get("user", "depi"),
                               password=self.config.dbConfig.get("password", "depi"),
                               database=self.config.dbConfig.get("database", "depi"),
                               cursorclass=MySQLdb.cursors.DictCursor)

    def getDBConnection(self):
        self.pool_lock.acquire()
        try:
            if len(self.connections) == 0:
                return self._createDBConnection()
            conn = self.connections.pop()
            try:
                cursor = conn.cursor()
                cursor.execute("select database();")
                cursor.fetchall()
                cursor.close()
                return conn
            except Exception:
                return self._createDBConnection()

        finally:
            self.pool_lock.release()

    def releaseDBConnection(self, conn: MySQLdb.Connection):
        self.pool_lock.acquire()
        try:
            self.connections.append(conn)
        finally:
            self.pool_lock.release()

    def isTag(self, name: str) -> tuple[bool, str]:
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            cursor.execute("select tag_name from dolt_tags where tag_name like %s", (name+"|%",))
            rows = cursor.fetchall()
            if len(rows) > 0:
                return True, rows[0]["tag_name"]
            else:
                return False, ""
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def getBranch(self, name: str) -> "DoltBranch":
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            (isTag, _tagName) = self.isTag(name)
            if isTag:
                raise Exception("Cannot check out a tag")
            else:
                cursor.execute("CALL DOLT_CHECKOUT(%s)", (name, ))
                cursor.fetchall()
                return DoltBranch(name, self.config, self, False)
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def getTag(self, name: str) -> "DoltBranch":
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            (isTag, _tagName) = self.isTag(name)
            if not isTag:
                raise Exception("Cannot checkout a branch as a tag")
            else:
                cursor.execute("USE %s/%s)", (self.database, name))
                cursor.fetchall()
                return DoltBranch(name, self.config, self, True)
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def getBranchConn(self, name: str) -> MySQLdb.Connection:
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            (isTag, _tagName) = self.isTag(name)
            if isTag:
                raise Exception("Cannot check out a tag")
            else:
                cursor.execute("CALL DOLT_CHECKOUT(%s)", (name, ))
                cursor.fetchall()
            return conn
        finally:
            cursor.close()

    def getTagConn(self, name: str) -> MySQLdb.Connection:
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            (isTag, _tagName) = self.isTag(name)
            if isTag:
                raise Exception("Cannot check out a tag")
            else:
                cursor.execute("USE %s/%s", (self.database, name))
                cursor.fetchall()
            return conn
        finally:
            cursor.close()

    def getBranchList(self) -> list[str]:
        conn = self.getDBConnection()
        cursor = conn.cursor()
        branches = []
        try:
            cursor.execute("select name from dolt_branches")
            for row in cursor.fetchall():
                branches.append(row["name"])
            return branches
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def getTagList(self) -> list[str]:
        conn = self.getDBConnection()
        cursor = conn.cursor()
        tags = []
        try:
            cursor.execute("select tag_name from dolt_tags")
            for row in cursor.fetchall():
                tags.append(row["tag_name"].split("|")[0])
            return tags
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def branchExists(self, name: str) -> bool:
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            cursor.execute("select name from dolt_branches where name=%s",
                           (name,))
            rows = cursor.fetchall()
            return len(rows) > 0
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def tagExists(self, name: str) -> bool:
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            cursor.execute("select tag_name from dolt_tags where tag_name like %s",
                           (name+"|%",))
            rows = cursor.fetchall()
            return len(rows) > 0
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def createBranch(self, name: str, fromBranch: str):
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            cursor.execute("call DOLT_BRANCH(%s, %s)", (name, fromBranch))
            cursor.fetchall()
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def createTag(self, name: str, fromBranch: str):
        conn = self.getDBConnection()
        cursor = conn.cursor()
        try:
            cursor.execute("call DOLT_TAG(%s, 'HEAD')", (name, ));
            cursor.fetchall()
        finally:
            cursor.close()
            self.releaseDBConnection(conn)

    def loadAllState(self):
        pass


class DoltBranch(DepiBranch):
    def __init__(self, name: str, config, parent: DoltDB, is_tag: bool):
        super().__init__(name)
        self.parent = parent
        self.config = config
        self.is_tag = is_tag
        self.db = None

    def get_connection(self):
        if self.db is not None:
            return self.db

        self.db = self.parent.getBranchConn(self.name)
        return self.db

    def get_read_connection(self):
        return self.parent.getBranchConn(self.name)

    def commit(self):
        if self.db is None:
            return

        cursor = self.db.cursor()
        try:
            # TODO Add name & e-mail to Depi user configuration
            cursor.execute("CALL DOLT_COMMIT('-a', '--skip-empty', '-m', %s, '--author', %s)",
                ("committed", "Mark Wutka <mark.wutka@vanderbilt.edu>"))
            cursor.fetchall()
        finally:
            cursor.close()
            self.parent.releaseDBConnection(self.db)
            self.db = None

    def abort(self):
        if self.db is None:
            return

        cursor = self.db.cursor()
        try:
            # TODO Add name & e-mail to Depi user configuration
            cursor.execute("CALL DOLT_REVERT('HEAD')");
            cursor.fetchall()
        finally:
            cursor.close()
            self.parent.releaseDBConnection(self.db)
            self.db = None

    def saveBranchState(self):
        self.commit()

    def markResourcesClean(self, resourceRefs: list[ResourceRef]):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:

            for rr in resourceRefs:
                cursor.execute("update link set dirty=false where to_tool_id=%s and to_rg_url=%s and to_url=%s",
                    (rr.toolId, rr.resourceGroupURL, rr.URL))
                cursor.fetchall()
            self.commit()
        except Exception as exc:
            self.abort()
            raise exc


    def markLinksClean(self, links: list[Link], propagateCleanliness: bool):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for l in links:
                cursor.execute(
                    "update link set dirty=false where from_tool_id=%s and "+
                    "from_rg_url=%s and from_url=%s and to_tool_id=%s and "+
                    "to_rg_url=%s and to_url=%s",
                    (l.fromRes.toolId, l.fromRes.resourceGroupURL, l.fromRes.URL,
                     l.toRes.toolId, l.toRes.resourceGroupURL, l.toRes.URL))
                cursor.fetchall()
                if propagateCleanliness:
                    self.markInferredDirtinessClean(l, l.fromRes, propagateCleanliness, cursor)
                self.cleanDeleted(cursor)
            self.commit()
        except Exception as exc:
            self.abort()
            raise exc

    def markInferredDirtinessClean(self, link: Link, dirtinessSource: ResourceRef, propagateCleanliness: bool,
                                   cursor=None) -> list[(Link,ResourceRef)]:
        closeCursor = False
        if cursor is None:
            conn = self.get_connection()
            cursor = conn.cursor()
            closeCursor = True

        links_cleaned = []
        try:
            cursor.execute("""
            delete from inferred_dirtiness where from_tool_id=%s and from_rg_url=%s and
            from_url=%s and to_tool_id=%s and to_rg_url=%s and to_url=%s and
            source_tool_id=%s and source_rg_url=%s and source_url=%s""",
                           (link.fromRes.toolId, link.fromRes.resourceGroupURL,
                            link.fromRes.URL, link.toRes.toolId, link.toRes.resourceGroupURL,
                            link.toRes.URL, dirtinessSource.toolId, dirtinessSource.resourceGroupURL,
                            dirtinessSource.URL))
            cursor.fetchall()
            links_cleaned.append((link, dirtinessSource))

            if not propagateCleanliness:
                if closeCursor:
                    cursor.close()
                    self.commit()
                return links_cleaned

            workQueue = [(link.fromRes.toolId, link.fromRes.resourceGroupURL, link.fromRes.URL,
                          link.toRes.toolId, link.toRes.resourceGroupURL, link.toRes.URL)]
            processed = {(link.fromRes.toolId, link.fromRes.resourceGroupURL, link.fromRes.URL,
                          link.toRes.toolId, link.toRes.resourceGroupURL, link.toRes.URL)}

            while len(workQueue) > 0:
                currLink = workQueue.pop()
                processed.add(currLink)
                (from_tool_id, from_rg_url, from_url,
                 to_tool_id, to_rg_url, to_url) = currLink

                cursor.execute("""
                select to_tool_id, to_rg_url, to_url from link where
                from_tool_id=%s and from_rg_url=%s and from_url=%s""",
                               (to_tool_id, to_rg_url, to_url))

                while True:
                    row = cursor.fetchone()
                    if row is None:
                        break

                    nextLink = (to_tool_id, to_rg_url, to_url,
                                row["to_tool_id"], row["to_rg_url"], row["to_url"])
                    if nextLink not in processed:
                        workQueue.append(nextLink)
                cursor.execute("""
                    delete from inferred_dirtiness where from_tool_id=%s and from_rg_url=%s and
                    from_url=%s and to_tool_id=%s and to_rg_url=%s and to_url=%s and
                    source_tool_id=%s and source_rg_url=%s and source_url=%s""",
                           (from_tool_id, from_rg_url, from_url,
                            to_tool_id, to_rg_url, to_url,
                            dirtinessSource.toolId, dirtinessSource.resourceGroupURL,
                            dirtinessSource.URL))
                links_cleaned.append((Link(ResourceRef(from_tool_id, from_rg_url, from_url),
                                           ResourceRef(to_tool_id, to_rg_url, to_url)), dirtinessSource))
                cursor.fetchall()
            if closeCursor:
                cursor.close()
                self.commit()
            return links_cleaned

        except Exception as e:
            self.abort()
            raise e

    def _addResourceExt(self, rg: ResourceGroup, rr: Resource, cursor: MySQLdb.cursors.DictCursor | None):
        closeCursor = True
        if cursor is not None:
            closeCursor = False
        else:
            conn = self.get_connection()
            cursor = conn.cursor()

        try:
            cursor.execute("insert into resource_group (tool_id, url, name, version) values (%s,%s,%s,%s) on duplicate key update url=url",
                      (rg.toolId, rg.URL, rg.name, rg.version))
            if rr is not None:
                cursor.execute("insert into resource (tool_id, rg_url, url, name, id, deleted) values (%s,%s,%s,%s,%s,false) on duplicate key update name=%s, deleted=false",
                      (rg.toolId, rg.URL, rr.URL, rr.name, rr.id, rr.name))
            if closeCursor:
                cursor.close()
                self.commit()
            return cursor.rowcount != 0
        except Exception as e:
            self.abort()
            raise e

    def addResource(self, rg: ResourceGroup, rr: Resource):
        return self._addResourceExt(rg, rr, None)

    def _addResourcesExt(self, resources: list[tuple[ResourceGroup, Resource]], cursor: MySQLdb.cursors.DictCursor | None):
        closeCursor = True
        if cursor is not None:
            closeCursor = False
        else:
            conn = self.get_connection()
            cursor = conn.cursor()

        resource_groups = set()
        resources_insert = []
        for rg, res in resources:
            resource_groups.add(rg)
            resources_insert.append((rg.toolId, rg.URL, res.URL, res.name, res.id))

        resource_groups_insert = [(rg.toolId, rg.URL, rg.name, rg.version) for rg in resource_groups]
        try:
            cursor.executemany("insert ignore into resource_group (tool_id, url, name, version) values (%s,%s,%s,%s)",
                               resource_groups_insert)
            cursor.executemany(
                "insert ignore into resource (tool_id, rg_url, url, name, id, deleted) values (%s,%s,%s,%s,%s,false)",
                resources_insert)

            if closeCursor:
                cursor.close()
                self.commit()
            return cursor.rowcount != 0
        except Exception as e:
            self.abort()
            raise e

    def addResources(self, resources: list[tuple[ResourceGroup, Resource|None]]):
        self._addResourcesExt(resources, None)

    def addLink(self, newLink: LinkWithResources) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self._addResourceExt(newLink.fromResourceGroup, newLink.fromRes, cursor)
            self._addResourceExt(newLink.toResourceGroup, newLink.toRes, cursor)
            cursor.execute("insert into link (from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url, dirty, deleted, last_clean_version) values (%s,%s,%s,%s,%s,%s,false,false,%s) on duplicate key update deleted=false",
                           (newLink.fromResourceGroup.toolId, newLink.fromResourceGroup.URL, newLink.fromRes.URL,
                            newLink.toResourceGroup.toolId, newLink.toResourceGroup.URL, newLink.toRes.URL,
                            newLink.lastCleanVersion))
            self.commit()
            return cursor.rowcount != 0
        except Exception as e:
            self.abort()
            raise e

    def addLinks(self, newLinks: list[LinkWithResources]) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            res_to_insert = set()
            links_to_insert = []
            for link in newLinks:
                res_to_insert.add((link.fromResourceGroup, link.fromRes))
                res_to_insert.add((link.toResourceGroup, link.toRes))
                links_to_insert.append(
                    (link.fromResourceGroup.toolId, link.fromResourceGroup.URL, link.fromRes.URL,
                     link.toResourceGroup.toolId, link.toResourceGroup.URL, link.toRes.URL,
                     link.lastCleanVersion))

            self._addResourcesExt(list(res_to_insert), cursor)

            cursor.executemany("insert into link (from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url, dirty, deleted, last_clean_version) values (%s,%s,%s,%s,%s,%s,false,false,%s) on duplicate key update deleted=false",
                               links_to_insert)
            self.commit()
            return cursor.rowcount != 0
        except Exception as e:
            self.abort()
            raise e

    def removeResourceRef(self, rr: ResourceRef) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:

            # TODO - Verify that we actually want to mark the link as deleted
            cursor.execute("update link set deleted=true where (from_tool_id=%s and from_rg_url=%s and from_url=%s) "+
                           "or (to_tool_id=%s and to_rg_url=%s and to_url=%s)",
                           (rr.toolId, rr.resourceGroupURL, rr.URL,
                            rr.toolId, rr.resourceGroupURL, rr.URL))
            cursor.fetchall()

            cursor.execute("delete from inferred_link where (from_tool_id=%s and from_rg_url=%s and from_url=%s) "+
                           "or (to_tool_id=%s and to_rg_url=%s and to_url=%s)"+
                           "or (source_tool_id=%s and source_rg_url=%s and source_url=%s)",
                           (rr.toolId, rr.resourceGroupURL, rr.URL,
                             rr.toolId, rr.resourceGroupURL, rr.URL,
                             rr.toolId, rr.resourceGroupURL, rr.URL))
            cursor.fetchall()

            cursor.execute("update resource set deleted=true where tool_id=%s and rg_url=%s and url=%s",
                           (rr.toolId, rr.resourceGroupURL, rr.URL))
            return cursor.rowcount > 0
        finally:
            cursor.close()

    def getResource(self, rr: ResourceRef) -> tuple[ResourceGroup, Resource] | None:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:

            cursor.execute("select rg.name as rg_name, rg.version as rg_version, r.name as name, id as id from resource r, resource_group rg where r.tool_id=%s and r.rg_url=%s and r.url=%s and r.deleted=false and r.tool_id=rg.tool_id and r.rg_url=rg.url",
                           (rr.toolId, rr.resourceGroupURL, rr.URL))

            rows = cursor.fetchall()
            if len(rows) > 0:
                rg_name = rows[0]["rg_name"]
                rg_version = rows[0]["rg_version"]
                name = rows[0]["name"]
                id = rows[0]["id"]
                return ResourceGroup(toolId=rr.toolId, name=rg_name, URL=rr.resourceGroupURL, version=rg_version), \
                       Resource(name=name, id=id, URL=rr.URL)
            else:
                return None
        finally:
            self.parent.releaseDBConnection(conn)

    def removeLink(self, delLink: Link) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("update link set deleted=true where from_tool_id=%s and from_rg_url=%s and from_url=%s and to_tool_id=%s and to_rg_url=%s and to_url=%s and deleted=false",
                           (delLink.fromRes.toolId, delLink.fromRes.resourceGroupURL, delLink.fromRes.URL,
                            delLink.toRes.toolId, delLink.toRes.resourceGroupURL, delLink.toRes.URL))

            rows = cursor.fetchall()

            cursor.execute("delete inferred_link where (from_tool_id=%s and from_rg_url=%s and from_url=%s) "+
                           "and (to_tool_id=%s and to_rg_url=%s and to_url=%s)",
                           (delLink.fromRes.toolId, delLink.fromRes.resourceGroupURL, delLink.fromRes.URL,
                            delLink.toRes.toolId, delLink.toRes.resourceGroupURL, delLink.toRes.URL))

            self.commit()
            return cursor.rowcount > 0
        except Exception as e:
            self.abort()
            raise e

    def getResourceGroupVersion(self, toolId: str, URL: str) -> str:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("select version from resource_group where tool_id=%s and url=%s",
                (toolId, URL))

            rows = cursor.fetchall()

            if len(rows) > 0:
                return rows[0]["version"]
            else:
                return ""
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def getResourceGroup(self, toolId: str, URL: str) -> ResourceGroup|None:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("select name, version from resource_group where tool_id=%s and url=%s",
                           (toolId, URL))

            rows = cursor.fetchall()

            if len(rows) > 0:
                return ResourceGroup(toolId=toolId, URL=URL, name=rows[0]["name"], version=rows[0]["version"])
            else:
                return None
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def getResourceGroups(self) -> list[ResourceGroup]:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("select tool_id, url, name, version from resource_group")

            rows = cursor.fetchall()

            resourceGroups = []

            for row in rows:
                resourceGroups.append(ResourceGroup(row["name"], row["tool_id"], row["url"], row["version"]))

            return resourceGroups
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def editResourceGroup(self, oldResourceGroup: ResourceGroup, newResourceGroup: ResourceGroup):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("update resource_group set tool_id=%s, url=%s, name=%s, version=%s where tool_id=%s and url=%s",
                           (newResourceGroup.toolId, newResourceGroup.URL, newResourceGroup.name,
                            newResourceGroup.version, oldResourceGroup.toolId, oldResourceGroup.URL))
        except Exception as e:
            self.abort()
            raise e
        finally:
            self.commit()

    def removeResourceGroup(self, toolId: str, URL: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("delete from link where (from_tool_id=%s and from_rg_url=%s) or (to_tool_id=%s and to_rg_url=%s)",
                           (toolId, URL, toolId, URL))
            cursor.execute("delete from resource where tool_id=%s and rg_url=%s",
                           (toolId, URL))
            cursor.execute("delete from resource_group where tool_id=%s and url=%s",
                           (toolId, URL))
        except Exception as e:
            self.abort()
            raise e
        finally:
            self.commit()

    def getResourceByRef(self, rr: ResourceRef) -> Resource | None:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("select name, id, deleted from resource where tool_id=%s and rg_url=%s and url=%s",
                (rr.toolId, rr.resourceGroupURL, rr.URL))

            rows = cursor.fetchall()
            if len(rows) > 0:
                name = rows[0]["name"]
                id = rows[0]["id"]
                deleted = rows[0]["deleted"]
                return Resource(name, id, rr.URL, deleted)
            else:
                return None
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def isResourceDeleted(self, rr: ResourceRef) -> bool:
        res = self.getResourceByRef(rr)
        return res.deleted

    def validateResourceRef(self, rr: ResourceRef) -> ResourceRef:
        res = self.getResourceByRef(rr)
        if res is None:
            return rr
        rr.deleted = res.deleted
        return rr

    def getResources(self, resPatterns: list[ResourceRefPattern], includeDeleted: bool) -> list[(ResourceGroup, Resource)]:
        tools = {}
        patterns = []
        for pattern in resPatterns:
            tool = {}
            if pattern.toolId not in tools:
                tools[pattern.toolId] = tool
            else:
                tool = tools[pattern.toolId]

            if pattern.resourceGroupURL not in tool:
                rg = []
                tool[pattern.resourceGroupURL] = rg
            else:
                rg = tool[pattern.resourceGroupURL]
                rg.append(pattern.resourceGroupURL)

            patterns.append({"toolId": pattern.toolId, "rgURL": pattern.resourceGroupURL, "re": re.compile(pattern.URLPattern)})

        resources = []

        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            for tool in tools:
                for rg_url in tools[tool]:
                    if includeDeleted:
                        cursor.execute("select r.url as url, r.name as name, r.id as id, rg.name as rg_name, rg.version as version, r.deleted as deleted from resource r, resource_group rg where rg.tool_id=%s and rg.url=%s and r.tool_id=rg.tool_id and rg.url=r.rg_url ",
                                   (tool, rg_url))
                    else:
                        cursor.execute("select r.url as url, r.name as name, r.id as id, rg.name as rg_name, rg.version as version, r.deleted as deleted from resource r, resource_group rg where rg.tool_id=%s and rg.url=%s and r.tool_id=rg.tool_id and rg.url=r.rg_url and deleted=false",
                                   (tool, rg_url))

                    while True:
                        row = cursor.fetchone()
                        if row is None:
                            break
                        url = row["url"]
                        for pattern in patterns:
                            if pattern["toolId"] != tool or pattern["rgURL"] != rg_url:
                                continue
                            m = pattern["re"].match(url)
                            if m is not None:
                                rg = ResourceGroup(toolId=tool, URL=rg_url,
                                                   name=row["rg_name"], version="version")
                                res = Resource(name=row["name"], URL=row["url"], id=row["id"], deleted=row["deleted"])
                                resources.append((rg, res))
                                break
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)
        return resources

    def getResourcesAsStream(self, resPatterns: list[ResourceRefPattern]):
        tools = {}
        patterns = []
        for pattern in resPatterns:
            tool = {}
            if pattern.toolId not in tools:
                tools[pattern.toolId] = tool
            else:
                tool = tools[pattern.toolId]

            if pattern.resourceGroupURL not in tool:
                rg = []
                tool[pattern.resourceGroupURL] = rg
            else:
                rg = tool[pattern.resourceGroupURL]
                rg.append(pattern.resourceGroupURL)

            patterns.append({"toolId": pattern.toolId, "rgURL": pattern.resourceGroupURL, "re": re.compile(pattern.URLPattern)})

        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            for tool in tools:
                for rg_url in tools[tool]:
                    cursor.execute("select r.url as url, r.name as name, r.id as id, rg.name as rg_name, rg.version as version from resource r, resource_group rg where rg.tool_id=%s and rg.url=%s and r.tool_id=rg.tool_id and rg.url=r.rg_url and deleted=false",
                                   (tool, rg_url))

                    while True:
                        row = cursor.fetchone()
                        if row is None:
                            break
                        url = row["url"]
                        for pattern in patterns:
                            if pattern["toolId"] != tool or pattern["rgURL"] != rg_url:
                                continue
                            m = pattern["re"].match(url)
                            if m is not None:
                                rg = ResourceGroup(toolId=tool, URL=rg_url,
                                                   name=row["rg_name"], version="version")
                                res = Resource(name=row["name"], URL=row["url"], id=row["id"], deleted=False)
                                yield rg, res
                                break
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def getInferredLinks(self, from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url):
        conn = self.get_read_connection()
        cursor = conn.cursor()
        links = []
        try:
            cursor.execute("select infd.source_tool_id as source_tool_id, infd.source_rg_url as source_rg_url, "+
                           " infd.source_url as source_url, "+
                           " infd.source_last_clean_version as source_last_clean_version, "+
                           " rg.name as rg_name, rg.version as rg_version, "+
                           " res.name as name, res.id as id "+
                           " from inferred_dirtiness infd, resource res, resource_group rg "+
                           " where infd.from_tool_id=%s and infd.from_rg_url=%s and "+
                           " infd.from_url=%s and infd.to_tool_id=%s and infd.to_rg_url=%s and infd.to_url=%s and "+
                           " res.tool_id=infd.source_tool_id and res.rg_url=infd.source_rg_url and "+
                           " res.url=infd.source_url and rg.tool_id=source_tool_id and rg.url=source_rg_url",
                           (from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url))
            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                source_tool_id = row["source_tool_id"]
                source_rg_url = row["source_rg_url"]
                source_url = row["source_url"]
                res_name = row["name"]
                res_id = row["id"]
                rg_name = row["rg_name"]
                rg_version = row["rg_version"]
                last_clean_version = row["source_last_clean_version"]

                links.append((ResourceGroup(name=rg_name, toolId=source_tool_id, URL=source_rg_url,
                                            version=rg_version),
                              Resource(name=res_name, id=res_id, URL=source_url),
                              last_clean_version))
            return links
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def getLinks(self, linkPatterns: list[ResourceLinkPattern]) -> list[LinkWithResources]:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        links = []

        try:
            for pattern in linkPatterns:
                fromRegex = re.compile(pattern.fromRes.URLPattern)
                toRegex = re.compile(pattern.toRes.URLPattern)

                cursor.execute(
                    "select l.from_url as from_url, l.to_url as to_url, l.dirty as dirty, "+
                    " l.last_clean_version as last_clean_version, "+
                    " fr.name as from_name, fr.id as from_id, "+
                    " tr.name as to_name, tr.id as to_id, "+
                    " frg.name as from_rg_name, frg.version as from_version, "+
                    " trg.name as to_rg_name, trg.version as to_version "+
                    " from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
                    "where from_tool_id=%s and from_rg_url=%s and to_tool_id=%s and "+
                    "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
                    "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
                    "  to_rg_url=%s and l.deleted=false and l.from_tool_id=fr.tool_id and "+
                    "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
                    "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
                    (pattern.fromRes.toolId, pattern.fromRes.resourceGroupURL,
                     pattern.toRes.toolId, pattern.toRes.resourceGroupURL))

                fetched = set()
                while True:
                    row = cursor.fetchone()
                    if row is None:
                        break

                    key = (pattern.fromRes.toolId, pattern.fromRes.resourceGroupURL, row["from_url"],
                        pattern.toRes.toolId, pattern.toRes.resourceGroupURL, row["to_url"])
                    if key in fetched:
                        continue
                    fetched.add(key)

                    m = fromRegex.match(row["from_url"])
                    if m is not None:
                        m = toRegex.match(row["to_url"])
                        if m is not None:
                            inferred = self.getInferredLinks(pattern.fromRes.toolId, pattern.fromRes.resourceGroupURL,
                                                             row["from_url"], pattern.toRes.toolId,
                                                             pattern.toRes.resourceGroupURL, row["to_url"])
                            links.append(LinkWithResources(
                                ResourceGroup(toolId=pattern.fromRes.toolId,URL=pattern.fromRes.resourceGroupURL,
                                              name=row["from_rg_name"], version=row["from_version"]),
                                Resource(name=row["from_name"], URL=row["from_url"], id=row["from_id"]),
                                ResourceGroup(toolId=pattern.toRes.toolId,URL=pattern.toRes.resourceGroupURL,
                                              name=row["to_rg_name"], version=row["to_version"]),
                                Resource(name=row["to_name"], URL=row["to_url"], id=row["to_id"]),
                                dirty=row["dirty"] == 1, inferredDirtiness=inferred))
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)
        return links

    def getLinksAsStream(self, linkPatterns: list[ResourceLinkPattern]):
        conn = self.get_read_connection()
        cursor = conn.cursor()

        try:
            for pattern in linkPatterns:
                fromRegex = re.compile(pattern.fromRes.URLPattern)
                toRegex = re.compile(pattern.toRes.URLPattern)

                cursor.execute(
                    "select l.from_url as from_url, l.to_url as to_url, l.dirty as dirty, "+
                    " l.last_clean_version as last_clean_version, "+
                    " fr.name as from_name, fr.id as from_id, "+
                    " tr.name as to_name, tr.id as to_id, "+
                    " frg.name as from_rg_name, frg.version as from_version, "+
                    " trg.name as to_rg_name, trg.version as to_version "+
                    " from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
                    "where from_tool_id=%s and from_rg_url=%s and to_tool_id=%s and "+
                    "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
                    "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
                    "  to_rg_url=%s and l.deleted=false and l.from_tool_id=fr.tool_id and "+
                    "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
                    "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
                    (pattern.fromRes.toolId, pattern.fromRes.resourceGroupURL,
                     pattern.toRes.toolId, pattern.toRes.resourceGroupURL))

                fetched = set()
                while True:
                    row = cursor.fetchone()
                    if row is None:
                        break

                    key = (pattern.fromRes.toolId, pattern.fromRes.resourceGroupURL, row["from_url"],
                           pattern.toRes.toolId, pattern.toRes.resourceGroupURL, row["to_url"])
                    if key in fetched:
                        continue
                    fetched.add(key)

                    m = fromRegex.match(row["from_url"])
                    if m is not None:
                        m = toRegex.match(row["to_url"])
                        if m is not None:
                            inferred = self.getInferredLinks(pattern.fromRes.toolId, pattern.fromRes.resourceGroupURL,
                                                             row["from_url"], pattern.toRes.toolId,
                                                             pattern.toRes.resourceGroupURL, row["to_url"])
                            yield LinkWithResources(
                                ResourceGroup(toolId=pattern.fromRes.toolId,URL=pattern.fromRes.resourceGroupURL,
                                              name=row["from_rg_name"], version=row["from_version"]),
                                Resource(name=row["from_name"], URL=row["from_url"], id=row["from_id"]),
                                ResourceGroup(toolId=pattern.toRes.toolId,URL=pattern.toRes.resourceGroupURL,
                                              name=row["to_rg_name"], version=row["to_version"]),
                                Resource(name=row["to_name"], URL=row["to_url"], id=row["to_id"]),
                                dirty=row["dirty"] == 1, inferredDirtiness=inferred)
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def getDirtyLinks(self, resourceGroup: ResourceGroup, withInferred: bool) -> list[LinkWithResources]:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        links = []

        try:
            if not withInferred:
                cursor.execute(
                    "select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, " +
                    " l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
                    " l.to_url as to_url, l.dirty as dirty, "+
                    " l.last_clean_version as last_clean_version, "+
                    " fr.name as from_name, fr.id as from_id, "+
                    " tr.name as to_name, tr.id as to_id, "+
                    " frg.name as from_rg_name, frg.version as from_version, "+
                    " trg.name as to_rg_name, trg.version as to_version "+
                    " from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
                    "where to_tool_id=%s and to_rg_url=%s and "+
                    "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
                    "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
                    "  l.deleted=false and l.from_tool_id=fr.tool_id and "+
                    "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and "+
                    "  l.dirty=true and "
                    "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
                    (resourceGroup.toolId, resourceGroup.URL))
            else:
                cursor.execute(
                    "select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, " +
                    " l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
                    " l.to_url as to_url, l.dirty as dirty, "+
                    " l.last_clean_version as last_clean_version, "+
                    " fr.name as from_name, fr.id as from_id, "+
                    " tr.name as to_name, tr.id as to_id, "+
                    " frg.name as from_rg_name, frg.version as from_version, "+
                    " trg.name as to_rg_name, trg.version as to_version "+
                    " from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
                    "where to_tool_id=%s and to_rg_url=%s and "+
                    "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
                    "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
                    "  l.deleted=false and l.from_tool_id=fr.tool_id and "+
                    "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
                    "  (l.dirty=true or "
                    "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url and "+
                    "  exists(select infd.from_tool_id from inferred_dirtiness infd where "+
                    "  infd.from_tool_id=l.from_tool_id and infd.from_rg_url=l.from_rg_url and "+
                    "  infd.from_url=l.from_url and infd.to_tool_id=l.to_tool_id and "+
                    "  infd.to_rg_url=l.to_rg_url and infd.to_url=l.to_url))",
                    (resourceGroup.toolId, resourceGroup.URL))

            while True:
                row = cursor.fetchone()
                if row is None:
                    break

                inferred = self.getInferredLinks(row["from_tool_id"], row["from_rg_url"],
                                                 row["from_url"], row["to_tool_id"],
                                                 row["to_rg_url"], row["to_url"])
                links.append(LinkWithResources(
                    ResourceGroup(toolId=row["from_tool_id"], URL=row["from_rg_url"],
                                  name=row["from_rg_name"], version=row["from_version"]),
                    Resource(name=row["from_name"], URL=row["from_url"], id=row["from_id"]),
                    ResourceGroup(toolId=row["to_tool_id"],URL=row["to_rg_url"],
                                  name=row["to_rg_name"], version=row["to_version"]),
                    Resource(name=row["to_name"], URL=row["to_url"], id=row["to_id"]),
                    dirty=row["dirty"] == 1, inferredDirtiness=inferred))
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)
        return links

    def getDirtyLinksAsStream(self, resourceGroup: ResourceGroup, withInferred: bool):
        conn = self.get_read_connection()
        cursor = conn.cursor()

        try:
            if not withInferred:
                cursor.execute(
                    "select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, " +
                    " l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, " +
                    " l.to_url as to_url, l.dirty as dirty, " +
                    " l.last_clean_version as last_clean_version, " +
                    " fr.name as from_name, fr.id as from_id, " +
                    " tr.name as to_name, tr.id as to_id, " +
                    " frg.name as from_rg_name, frg.version as from_version, " +
                    " trg.name as to_rg_name, trg.version as to_version " +
                    " from link l, resource_group frg, resource_group trg, resource fr, resource tr " +
                    "where to_tool_id=%s and to_rg_url=%s and " +
                    "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and " +
                    "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and " +
                    "  l.deleted=false and l.from_tool_id=fr.tool_id and " +
                    "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and " +
                    "  l.dirty=true and "
                    "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
                    (resourceGroup.toolId, resourceGroup.URL))
            else:
                cursor.execute(
                    "select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, " +
                    " l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, " +
                    " l.to_url as to_url, l.dirty as dirty, " +
                    " l.last_clean_version as last_clean_version, " +
                    " fr.name as from_name, fr.id as from_id, " +
                    " tr.name as to_name, tr.id as to_id, " +
                    " frg.name as from_rg_name, frg.version as from_version, " +
                    " trg.name as to_rg_name, trg.version as to_version " +
                    " from link l, resource_group frg, resource_group trg, resource fr, resource tr " +
                    "where to_tool_id=%s and to_rg_url=%s and " +
                    "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and " +
                    "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and " +
                    "  l.deleted=false and l.from_tool_id=fr.tool_id and " +
                    "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and" +
                    "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url and " +
                    "  exists(select infd.from_tool_id from inferred_dirtiness infd where " +
                    "  infd.from_tool_id=l.from_tool_id and infd.from_rg_url=l.from_rg_url and " +
                    "  infd.from_url=l.from_url and infd.to_tool_id=l.to_tool_id and " +
                    "  infd.to_rg_url=l.to_rg_url and infd.to_url=l.to_url)",
                    (resourceGroup.toolId, resourceGroup.URL))

            while True:
                row = cursor.fetchone()
                if row is None:
                    break

                inferred = self.getInferredLinks(row["from_tool_id"], row["from_rg_url"],
                                                 row["from_url"], row["to_tool_id"],
                                                 row["to_rg_url"], row["to_url"])
                yield LinkWithResources(
                    ResourceGroup(toolId=row["from_tool_id"], URL=row["from_rg_url"],
                                  name=row["from_rg_name"], version=row["from_version"]),
                    Resource(name=row["from_name"], URL=row["from_url"], id=row["from_id"]),
                    ResourceGroup(toolId=row["to_tool_id"],URL=row["to_rg_url"],
                                  name=row["to_rg_name"], version=row["to_version"]),
                    Resource(name=row["to_name"], URL=row["to_url"], id=row["to_id"]),
                    dirty=row["dirty"] == 1, inferredDirtiness=inferred)
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def getLinksToResource(self, res: ResourceRef) -> list[LinkWithResources]:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        links = []

        try:
            cursor.execute(
                "select l.from_url as from_url, l.to_url as to_url, l.dirty as dirty, "+
                " l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, "+
                " l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
                " l.last_clean_version as last_clean_version, "+
                " fr.name as from_name, fr.id as from_id, "+
                " tr.name as to_name, tr.id as to_id, "+
                " frg.name as from_rg_name, frg.version as from_version, "+
                " trg.name as to_rg_name, trg.version as to_version "+
                " from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
                "where to_tool_id=%s and to_rg_url=%s and to_url=%s and "+
                "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
                "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
                "  l.deleted=false and l.from_tool_id=fr.tool_id and "+
                "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
                "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
                (res.toolId, res.resourceGroupURL, res.URL))

            fetched = set()
            while True:
                row = cursor.fetchone()
                if row is None:
                    break

                key = (row["from_tool_id"], row["from_rg_url"], row["from_url"],
                       row["to_tool_id"], row["to_rg_url"], row["to_url"])
                if key in fetched:
                    continue
                fetched.add(key)

                inferred = self.getInferredLinks(row["from_tool_id"], row["from_rg_url"],
                                                 row["from_url"], row["to_tool_id"],
                                                 row["to_rg_url"], row["to_url"])
                links.append(LinkWithResources(
                    ResourceGroup(toolId=row["from_tool_id"],URL=row["from_rg_url"],
                                  name=row["from_rg_name"], version=row["from_version"]),
                    Resource(name=row["from_name"], URL=row["from_url"], id=row["from_id"]),
                    ResourceGroup(toolId=row["to_tool_id"],URL=row["to_rg_url"],
                                  name=row["to_rg_name"], version=row["to_version"]),
                    Resource(name=row["to_name"], URL=row["to_url"], id=row["to_id"]),
                    dirty=row["dirty"] == 1, inferredDirtiness=inferred))
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)
        return links

    def getLinksFromResource(self, res: ResourceRef) -> list[LinkWithResources]:
        conn = self.get_read_connection()
        cursor = conn.cursor()
        links = []

        try:
            cursor.execute(
                "select l.from_url as from_url, l.to_url as to_url, l.dirty as dirty, "+
                " l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, "+
                " l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
                " l.last_clean_version as last_clean_version, "+
                " fr.name as from_name, fr.id as from_id, "+
                " tr.name as to_name, tr.id as to_id, "+
                " frg.name as from_rg_name, frg.version as from_version, "+
                " trg.name as to_rg_name, trg.version as to_version "+
                " from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
                "where from_tool_id=%s and from_rg_url=%s and from_url=%s and "+
                "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
                "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
                "  l.deleted=false and l.from_tool_id=fr.tool_id and "+
                "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
                "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
                (res.toolId, res.resourceGroupURL, res.URL))

            fetched = set()
            while True:
                row = cursor.fetchone()
                if row is None:
                    break

                key = (row["from_tool_id"], row["from_rg_url"], row["from_url"],
                       row["to_tool_id"], row["to_rg_url"], row["to_url"])
                if key in fetched:
                    continue
                fetched.add(key)

                inferred = self.getInferredLinks(row["from_tool_id"], row["from_rg_url"],
                                                 row["from_url"], row["to_tool_id"],
                                                 row["to_rg_url"], row["to_url"])
                links.append(LinkWithResources(
                    ResourceGroup(toolId=row["from_tool_id"],URL=row["from_rg_url"],
                                  name=row["from_rg_name"], version=row["from_version"]),
                    Resource(name=row["from_name"], URL=row["from_url"], id=row["from_id"]),
                    ResourceGroup(toolId=row["to_tool_id"],URL=row["to_rg_url"],
                                  name=row["to_rg_name"], version=row["to_version"]),
                    Resource(name=row["to_name"], URL=row["to_url"], id=row["to_id"]),
                    dirty=row["dirty"] == 1, inferredDirtiness=inferred))
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)
        return links

    def expandLinks(self, linksToExpand: list[Link]) -> list[LinkWithResources]:
        links = []

        links_to_fetch = []
        for link in linksToExpand:
            links_to_fetch.append((link.fromRes.toolId, link.fromRes.resourceGroupURL, link.fromRes.URL,
             link.toRes.toolId, link.toRes.resourceGroupURL, link.toRes.URL))

        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            cursor.executemany(
                "select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url," +
                " l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url," +
                " l.to_url as to_url, l.dirty as dirty, "+
                " l.last_clean_version as last_clean_version, "+
                " fr.name as from_name, fr.id as from_id, "+
                " tr.name as to_name, tr.id as to_id, "+
                " frg.name as from_rg_name, frg.version as from_version, "+
                " trg.name as to_rg_name, trg.version as to_version "+
                " from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
                "where from_tool_id=%s and from_rg_url=%s and from_url=%s and to_tool_id=%s and "+
                "  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
                "  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
                "  to_rg_url=%s and to_url=%s and l.deleted=false and l.from_tool_id=fr.tool_id and "+
                "  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
                "  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
                links_to_fetch)

            while True:
                row = cursor.fetchone()
                if row is None:
                    break

                inferred = self.getInferredLinks(row["from_tool_id"], row["from_rg_url"],
                                                 row["from_url"], row["to_tool_id"],
                                                 row["to_rg_url"], row["to_url"])
                links.append(LinkWithResources(
                    ResourceGroup(toolId=row["from_tool_id"], URL=row["from_rg_url"],
                                  name=row["from_rg_name"], version=row["from_version"]),
                    Resource(name=row["from_name"], URL=row["from_url"], id=row["from_id"]),
                    ResourceGroup(toolId=row["to_tool_id"], URL=row["to_rg_url"],
                                  name=row["to_rg_name"], version=row["to_version"]),
                    Resource(name=row["to_name"], URL=row["to_url"], id=row["to_id"]),
                    dirty=row["dirty"] == 1, inferredDirtiness=inferred))

        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)
        return links

    def getAllLinks(self, includeDeleted=False) -> list[LinkWithResources]:
        links = []
        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            if includeDeleted:
                deletedPart = ""
            else:
                deletedPart = " and l.deleted=False"

            cursor.execute(
                "select rg1.tool_id as from_tool_id, rg1.name as from_rg_name, rg1.url as from_rg_url, "+
                "   rg1.version as from_rg_version, r1.name as from_name, "+
                "   r1.id as from_id, r1.url as from_url, r1.deleted as from_deleted, "+
                "   rg2.tool_id as to_tool_id, rg2.name as to_rg_name, rg2.url as to_rg_url, "+
                "   rg2.version as to_rg_version, r2.name as to_name, r2.id as to_id, r2.url as to_url, "+
                "   r2.deleted as to_deleted, l.dirty as dirty, l.last_clean_version as last_clean_version, "+
                "   l.deleted as deleted "
                "   from link l, resource_group rg1, resource_group rg2, "+
                "   resource r1, resource r2  "+
                " where l.from_tool_id = rg1.tool_id and l.from_rg_url=rg1.url "+
                "   and l.from_tool_id=r1.tool_id and l.from_rg_url=r1.rg_url "+
                "   and l.from_url=r1.url and l.to_tool_id=rg2.tool_id "+
                deletedPart +
                "   and l.to_rg_url=rg2.url and l.to_tool_id=r2.tool_id "+
                "   and l.to_rg_url=r2.rg_url and l.to_url=r2.url ")

            fetched = set()
            while True:
                row = cursor.fetchone()
                if row is None:
                    break

                key = (row["from_tool_id"], row["from_rg_url"], row["from_url"],
                       row["to_tool_id"], row["to_rg_url"], row["to_url"])
                if key in fetched:
                    continue
                fetched.add(key)

                from_rg = ResourceGroup(toolId=row["from_tool_id"], URL=row["from_rg_url"], name=row["from_rg_name"],
                                        version=row["from_rg_version"])
                from_res = Resource(name=row["from_name"], id=row["from_id"], URL=row["from_url"],
                                    deleted=row["from_deleted"] == 1)
                to_rg = ResourceGroup(toolId=row["to_tool_id"], URL=row["to_rg_url"], name=row["to_rg_name"],
                                      version=row["to_rg_version"])
                to_res = Resource(name=row["to_name"], id=row["to_id"], URL=row["to_url"],
                                  deleted=row["to_deleted"] == 1)

                inferred = self.getInferredLinks(from_rg.toolId, from_rg.URL, from_res.URL,
                                                 to_rg.toolId, to_rg.URL, to_res.URL)
                link = LinkWithResources(from_rg, from_res, to_rg, to_res, lastCleanVersion=row["last_clean_version"],
                                         dirty=row["dirty"] == 1,
                                         inferredDirtiness=inferred)
                link.deleted = row["deleted"] == 1
                links.append(link)
            return links
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def getAllLinksAsStream(self, includeDeleted=False):
        conn = self.get_read_connection()
        cursor = conn.cursor()
        try:
            if includeDeleted:
                deletedPart = ""
            else:
                deletedPart = " and l.deleted=False"

            cursor.execute(
                "select rg1.tool_id as from_tool_id, rg1.name as from_rg_name, rg1.url as from_rg_url, "+
                "   rg1.version as from_rg_version, r1.name as from_name, "+
                "   r1.id as from_id, r1.url as from_url, r1.deleted as from_deleted, "+
                "   rg2.tool_id as to_tool_id, rg2.name as to_rg_name, rg2.url as to_rg_url, "+
                "   rg2.version as to_rg_version, r2.name as to_name, r2.id as to_id, r2.url as to_url, "+
                "   r2.deleted as to_deleted, l.dirty as dirty, l.last_clean_version as last_clean_version, "+
                "   l.deleted as deleted "
                "   from link l, resource_group rg1, resource_group rg2, "+
                "   resource r1, resource r2  "+
                " where l.from_tool_id = rg1.tool_id and l.from_rg_url=rg1.url "+
                "   and l.from_tool_id=r1.tool_id and l.from_rg_url=r1.rg_url "+
                "   and l.from_url=r1.url and l.to_tool_id=rg2.tool_id "+
                deletedPart +
                "   and l.to_rg_url=rg2.url and l.to_tool_id=r2.tool_id "+
                "   and l.to_rg_url=r2.rg_url and l.to_url=r2.url ")

            fetched = set()
            while True:
                row = cursor.fetchone()
                if row is None:
                    break

                key = (row["from_tool_id"], row["from_rg_url"], row["from_url"],
                       row["to_tool_id"], row["to_rg_url"], row["to_url"])
                if key in fetched:
                    continue
                fetched.add(key)

                from_rg = ResourceGroup(toolId=row["from_tool_id"], URL=row["from_rg_url"], name=row["from_rg_name"],
                                        version=row["from_rg_version"])
                from_res = Resource(name=row["from_name"], id=row["from_id"], URL=row["from_url"],
                                    deleted=row["from_deleted"] == 1)
                to_rg = ResourceGroup(toolId=row["to_tool_id"], URL=row["to_rg_url"], name=row["to_rg_name"],
                                      version=row["to_rg_version"])
                to_res = Resource(name=row["to_name"], id=row["to_id"], URL=row["to_url"],
                                  deleted=row["to_deleted"] == 1)

                inferred = self.getInferredLinks(from_rg.toolId, from_rg.URL, from_res.URL,
                                                 to_rg.toolId, to_rg.URL, to_res.URL)
                link = LinkWithResources(from_rg, from_res, to_rg, to_res, lastCleanVersion=row["last_clean_version"],
                                         dirty=row["dirty"] == 1,
                                         inferredDirtiness=inferred)
                link.deleted = row["deleted"] == 1
                yield link
        finally:
            cursor.close()
            self.parent.releaseDBConnection(conn)

    def makePathMatch(self, toolId: str, url: str, field_name) -> tuple[str, list[str]] :
        pathSep = self.config.getToolConfig(toolId).pathSeparator
        parts = url.split(pathSep)
        partsAcc = ""
        paramsPos = []
        params = []
        for i in range(0, len(parts)):
            p=parts[i]
            if len(p) == 0:
                continue
            paramsPos.append(field_name+"=%s")
            partsAcc = partsAcc + pathSep + p
            if i < len(parts)-1:
                params.append(partsAcc + pathSep)
            else:
                params.append(partsAcc)
        return '('+" or ".join(paramsPos)+')', params

    def addInferredDirtiness(self, starting_to, source_tool_id, source_rg_url, source_url, last_clean_version,
                             cursor):
        working_set = set()
        working_set.add(starting_to)
        processed_set = set()

        while len(working_set) > 0:
            next_set = working_set.pop()
            processed_set.add(next_set)
            (next_tool_id, next_rg_url, next_url) = next_set

            cursor.execute("select to_tool_id, to_rg_url, to_url from link where "+
                           " from_tool_id=%s and from_rg_url=%s and from_url=%s",
                           (next_tool_id, next_rg_url, next_url))
            inserts = []
            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                to_tool_id = row["to_tool_id"]
                to_rg_url = row["to_rg_url"]
                to_url = row["to_url"]

                next_to = (to_tool_id, to_rg_url, to_url)
                if not next_to in processed_set:
                    working_set.add(next_to)

                inserts.append((next_tool_id, next_rg_url, next_url, to_tool_id, to_rg_url, to_url,
                 source_tool_id, source_rg_url, source_url, last_clean_version))

            cursor2 = self.db.cursor()
            try:
                cursor.executemany("insert into inferred_dirtiness (from_tool_id, from_rg_url, from_url, "+
                               " to_tool_id, to_rg_url, to_url, source_tool_id, source_rg_url, source_url,"+
                               " source_last_clean_version) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "+
                               " on duplicate key update from_tool_id=from_tool_id", inserts)
                cursor.fetchall()
            finally:
                cursor2.close()

    def updateResourceGroup(self, resourceGroupChange: ResourceGroupChange) -> list[Link]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("select version as last_clean_version from resource_group where "+
                           " tool_id=%s and url=%s", (resourceGroupChange.toolId,
                                                      resourceGroupChange.URL))
            row = cursor.fetchone()
            if row is None:
                # probably just return because this update is for a resource group that
                # depi doesn't know about
                return []
            last_clean_version = row["last_clean_version"]

            cursor.execute(
                "update resource_group set version=%s where tool_id=%s and url=%s",
                (resourceGroupChange.version, resourceGroupChange.toolId,
                 resourceGroupChange.URL))
            cursor.fetchall()

            linkedResourceGroupsToUpdate = set()

            for resChange in resourceGroupChange.resources.values():
                if resChange.changeType == ChangeType.Added or \
                        resChange.changeType == ChangeType.Modified:
                    logging.debug("Processing add/modify change for resource {}".format(
                        resChange.URL))

                    (pathMatchStr, pathParams) = self.makePathMatch(resourceGroupChange.toolId, resChange.URL, "from_url")
                    sqlParamList = [resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL] + pathParams
                    sqlParams = tuple(sqlParamList)

                    cursor.execute(
                        "select from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url  "+
                        "    from link "+
                        "where "+
                        "   from_tool_id=%s and from_rg_url=%s and dirty=false and (from_url = %s or " +
                            pathMatchStr+")", sqlParams)

                    rows = cursor.fetchall()
                    processed = set()
                    for row in rows:
                        link = Link(ResourceRef(toolId=row["from_tool_id"], resourceGroupURL=row["from_rg_url"],
                                                url=row["from_url"]),
                                    ResourceRef(toolId=row["to_tool_id"], resourceGroupURL=row["to_rg_url"],
                                                url=row["to_url"]))
                        if link in processed:
                            continue
                        processed.add(link)
                        linkedResourceGroupsToUpdate.add(link)
                        self.addInferredDirtiness((link.toRes.toolId, link.toRes.resourceGroupURL, link.toRes.URL),
                                                  resourceGroupChange.toolId, resourceGroupChange.URL,
                                                  resChange.URL, last_clean_version, cursor)
                    if len(processed) > 0:
                        cursor.executemany("""
                            update link set dirty=true where 
                                from_tool_id=%s and from_rg_url=%s and from_url=%s and dirty=false""",
                                       [(link.fromRes.toolId, link.fromRes.resourceGroupURL,
                                        link.fromRes.URL) for link in processed])
                        cursor.fetchall()

                if resChange.changeType == ChangeType.Renamed or \
                   (resChange.changeType == ChangeType.Modified and
                    (resChange.URL != resChange.newURL or
                     resChange.name != resChange.newName or
                     resChange.id != resChange.newId)):
                    logging.debug("Processing rename change for resource {}".format(
                        resChange.URL))

                    (pathMatchStr, pathParams) = self.makePathMatch(resourceGroupChange.toolId, resChange.URL, "from_url")
                    (resPathMatchStr, resPathParams) = self.makePathMatch(resourceGroupChange.toolId, resChange.URL, "res.url")
                    sqlParamList = [resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL] + pathParams + resPathParams
                    sqlParams = tuple(sqlParamList)

                    cursor.execute("""select l.from_tool_id as from_tool_id,
                        l.from_rg_url as from_rg_url, l.from_url as from_url,
                        l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url,
                        l.to_url as to_url from link l, resource res where l.dirty=false and 
                        l.from_tool_id=%s and l.from_rg_url=%s and (l.from_url = %s or """+
                        pathMatchStr+
                                   """) and
                        res.tool_id = l.from_tool_id and res.rg_url = l.from_rg_url and
                        (res.url = l.from_url or """+resPathMatchStr+")",
                                   sqlParams)
                    rows = cursor.fetchall()
                    link_and_old = []
                    for row in rows:
                        link = Link(ResourceRef(toolId=row["from_tool_id"], resourceGroupURL=row["from_rg_url"],
                                                url=resChange.newURL),
                                    ResourceRef(toolId=row["to_tool_id"], resourceGroupURL=row["to_rg_url"],
                                                url=row["to_url"]))
                        link_old_url = row["from_url"]
                        linkedResourceGroupsToUpdate.add(link)
                        self.addInferredDirtiness((link.toRes.toolId, link.toRes.resourceGroupURL, link.toRes.URL),
                                                  resourceGroupChange.toolId, resourceGroupChange.URL,
                                                  resChange.URL, last_clean_version, cursor)
                        link_and_old.append((link, link_old_url))

                    cursor.execute("""
                        update link set from_url=%s where 
                            from_tool_id=%s and from_rg_url=%s and from_url = %s""",
                                       (resChange.newURL, resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL))
                    cursor.fetchall()

                    cursor.execute("""
                        update link set to_url=%s where 
                            to_tool_id=%s and to_rg_url=%s and to_url = %s""",
                                   (resChange.newURL, resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL))
                    cursor.fetchall()

                    cursor.execute("""
                        update resource set id=%s, name=%s, url=%s where 
                            tool_id=%s and rg_url=%s and url = %s""",
                                   (resChange.newId, resChange.newName, resChange.newURL,
                                    resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL))
                    cursor.fetchall()

                elif resChange.changeType == ChangeType.Removed:
                    logging.debug("Processing remove change for resource {}".format(
                        resChange.URL))

                    (pathMatchStr, pathParams) = self.makePathMatch(resourceGroupChange.toolId, resChange.URL, "from_url")
                    (resPathMatchStr, resPathParams) = self.makePathMatch(resourceGroupChange.toolId, resChange.URL, "res.url")
                    sqlParamList = [resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL] + pathParams + resPathParams
                    sqlParams = tuple(sqlParamList)

                    cursor.execute("""select l.from_tool_id as from_tool_id,
                        l.from_rg_url as from_rg_url, l.from_url as from_url,
                        l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url,
                        l.to_url as to_url from link l, resource res where l.dirty=false and 
                        l.from_tool_id=%s and l.from_rg_url=%s and (l.from_url = %s or """+
                                   pathMatchStr+
                                   """) and
                        res.tool_id = l.from_tool_id and res.rg_url = l.from_rg_url and
                        (res.url = l.from_url or """+resPathMatchStr+")",
                                   sqlParams)
                    rows = cursor.fetchall()
                    link_and_old = []
                    for row in rows:
                        link = Link(ResourceRef(toolId=row["from_tool_id"], resourceGroupURL=row["from_rg_url"],
                                                url=resChange.newURL),
                                    ResourceRef(toolId=row["to_tool_id"], resourceGroupURL=row["to_rg_url"],
                                                url=row["to_url"]))
                        link_old_url = row["from_url"]
                        linkedResourceGroupsToUpdate.add(link)
                        link_and_old.append((link, link_old_url))
                        self.addInferredDirtiness((link.toRes.toolId, link.toRes.resourceGroupURL, link.toRes.URL),
                                                  resourceGroupChange.toolId, resourceGroupChange.URL,
                                                  resChange.newURL, last_clean_version, cursor)

                    cursor.execute("""
                        update link set deleted=true, dirty=true where 
                            from_tool_id=%s and from_rg_url=%s and dirty=false and from_url = %s""",
                                   (resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL))
                    cursor.fetchall()

                    cursor.execute("""
                        delete from link where 
                            to_tool_id=%s and to_rg_url=%s and to_url = %s""",
                                   (resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL))
                    cursor.fetchall()

                    cursor.execute("""
                        update resource set deleted=true where 
                            tool_id=%s and rg_url=%s and url = %s""",
                                   (resourceGroupChange.toolId, resourceGroupChange.URL, resChange.URL))
                    cursor.fetchall()

                    for (link, link_old_url) in link_and_old:
                        cursor.execute("""
                            update link set dirty=true where 
                                from_tool_id=%s and from_rg_url=%s and dirty=false and from_url = %s""",
                                       (link.fromRes.toolId, link.fromRes.resourceGroupURL,
                                        link_old_url))
                        cursor.fetchall()


            logging.debug("Updating resource group ")
            # TODO: figure out how to merge old with new

            cursor.close()
            self.saveBranchState()
            return list(linkedResourceGroupsToUpdate)

        except Exception as e:
            self.abort()
            raise e

    def cleanDeleted(self, cursor):
        cursor.execute("""
            delete from link where deleted=true and dirty=false
        """)

        cursor.execute("""
            select r.tool_id as tool_id, r.rg_url as rg_url, r.url as url from resource r
            where r.deleted=true and not exists (select l.from_url from link l where l.from_tool_id=r.tool_id and
                l.from_rg_url=r.rg_url and l.from_url=r.url)
        """)
        resources_to_delete = []
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            resources_to_delete.append((row["tool_id"], row["rg_url"], row["url"]))

        cursor.executemany("""
            delete from resource where tool_id=%s and rg_url=%s and url=%s
        """, resources_to_delete)


    def getDependencyGraph(self, rr: ResourceRef, upstream: bool, maxDepth: int) -> list[LinkWithResources]:
        processedLinks = set()

        if upstream:
            workLinks = [(l, 1) for l in self.getLinksToResource(rr)]
        else:
            workLinks = [(l, 1) for l in self.getLinksFromResource(rr)]

        links = []

        while len(workLinks) > 0:
            newWorkLinks = []
            for (link, depth) in workLinks:
                if link not in processedLinks and (maxDepth <= 0 or depth <= maxDepth):
                    processedLinks.add(link)
                    links.append(link)
                    if maxDepth <= 0 or depth < maxDepth:
                        if upstream:
                            searchRes = ResourceRef.fromResourceGroupAndRes(link.fromResourceGroup, link.fromRes)
                        else:
                            searchRes = ResourceRef.fromResourceGroupAndRes(link.toResourceGroup, link.toRes)
                        if upstream:
                            dependencies = self.getLinksToResource(searchRes)
                        else:
                            dependencies = self.getLinksFromResource(searchRes)

                        for depLink in dependencies:
                            if depLink not in processedLinks:
                                newWorkLinks.append((depLink, depth+1))
            workLinks = newWorkLinks

        return links



