import redis
from depi_db import DepiDB
from redis.commands.graph import Graph, Edge, Node, Path
from depi import Version, Group, Endpoint, Link

class RedisDB(DepiDB):
    def __init__(self, db_name):
        self.r = redis.Redis()
        self.db = Graph(self.r, db_name)

    def load_version(self, project, version):
        query = "match (v:version {project:$project,name:$version}) return v.name"
        params = { "project": project.name, "version": version}

        v_info = None
        result = self.db.query(query, params)
        for record in result.result_set:
            if len(record) == 0:
                return None
            return self.load_full_version(project, record[0])
        return None
            
    def load_version_by_tag(self, project, tag):
        query = "match (t:tag {project:$project,name:$name})-[:tag_version]->(v:version) return v.version"
        params = { "project": project.name, "name": tag}

        v_info = None
        result = self.db.query(query, params)
        for record in result.result_set:
            if len(record) == 0:
                return None
            return self.load_full_version(project, record[0])
        return None

    def load_full_version(self, project, version):
        # load groups and endpoints
        query = "match (v:version {project:$project,name:$version})-[:version_group]->(g:group) return g.name, g.app_id, g.path, g.version"
        params = { "project": project.name, "version": version}
        groups = {}
        result = self.db.query(query, params)
        for record in result.result_set:
            print("Processing group record")
            if len(record) == 0:
                continue
            if record[0] not in groups:
                group = Group(record[0], record[1], record[2], record[3])
                groups[record[0]] = group
        
        query = "match (v:version {project:$project,name:$version})-[:version_group]->(g:group)-[:group_endpoint]->(e:endpoint) return g.name, e.name"
        params = { "project": project.name, "version": version}
        result = self.db.query(query, params)
        for record in result.result_set:
            if len(record) == 0:
                continue
            group = groups[record[0]]
            group.endpoints.append(record[1])
        
        # load links
        query = "match (v:version {project:$project,name:$version})-[l:link_endpoint]->(e:endpoint) return l.name, e.group, e.name"
        params = { "project": project.name, "version": version}

        result = self.db.query(query, params)
        links = {}
        for record in result.result_set:
            if len(record) == 0:
                continue
            if record[0] not in links:
                link = Link(record[0], [])
                links[record[0]] = link
            else:
                link = links[record[0]]
            link.endpoints.append(Endpoint(groups[record[1]], record[2]))

        # load tags
        query = "match (t:tag {project:$project})-[:tag_version]->(v:version {project:$project,version:$version}) return t.tag"
        params = { "project": project.name, "version": version}
        result = self.db.query(query, params)
        tags = []
        for record in result.result_set:
            if len(record) == 0:
                continue
            tags.append(record[0])

        return Version(self, project, version, groups, tags, links)
        
    def get_versions(self, name):
        query = "match (v:version {project:$project}) return v.version"
        params = { "project": name}

        result = self.db.query(query, params)
        versions = []
        for record in result.result_set:
            if len(record) == 0:
                continue
            versions.append(record[0])
        return versions
        
    def get_tags(self, name):
        query = "match (t:tag {project:$project}) return t.tag"
        params = { "project": name}

        result = self.db.query(query, params)
        tags = []
        for record in result.result_set:
            if len(record) == 0:
                continue
            tags.append(record[0])
        return tags
        
    def save_version(self, version, version_number):
        version.version = version_number

        query = "merge (p:project {project:$project})"
        params = {"project": version.parent.name}
        self.db.query(query, params)

        query = "match (p:project {project:$project}) merge (v:version {project:$project,name:$version}) merge (p)-[:project_version]->(v)"
        params = {"project": version.parent.name,
            "version": version.version}
        self.db.query(query, params)

        query = "match (t:tag {project:$project,tag:$tag})-[tv:tag_version]->(v:version {project:$project,name:$version}) delete tv, delete t"
        for t in version.deleted_tags:
            params = {"project":version.parent.name,
                "version": version.version,
                "tag": t}
            self.db.query(query, params)

        query = "merge (t:tag {project:$project,tag:$tag}) match (v:version {project:$project,name:$version}) merge (t)-[tv:tag_version]->(v)"
        for t in version.tags:
            params = {"project":version.parent.name,
                "version": version.version,
                "tag": t}
            self.db.query(query, params)

        for gname in version.groups:
            g = version.groups[gname]
            if not g.is_changed:
                continue
            query = "match (v:version {project:$project,name:$version}) merge (g:group {name:$group_name,app_id:$app_id,path:$path,version:$group_version}) merge (v)-[:version_group]->(g)"
            params = {"project":version.parent.name,
                "version": version.version,
                "group_name": g.name,
                "app_id": g.app_id,
                "path": g.path,
                "group_version": g.version}
            self.db.query(query, params)
            for de in g.deleted_endpoints:
                query = "match (v:version {project:$project,name:$version})-[:version_group]->(g:group {name:$group_name})-[:group_endpoint]->(e:endpoint {name:$endpoint_name,project:$project,group:$group_name,group_version:$group_version,deleted:false}) set e.deleted=true"
                params = { "project":version.parent.name,
                    "version": version.version,
                    "group_name": g.name,
                    "group_version": g.version,
                    "endpoint_name": de }
                self.db.query(query, params)

            for e in g.endpoints:
                query = "match (v:version {project:$project,name:$version})-[:version_group]->(g:group {name:$group_name}) merge (g)-[:group_endpoint]->(e:endpoint {project:$project,version:$version,group:$group_name,group_version:$group_version,name:$endpoint_name,deleted:false})"
                params = { "project":version.parent.name,
                    "version": version.version,
                    "group_name": g.name,
                    "group_version": g.version,
                    "endpoint_name": e }
                self.db.query(query, params)
        for lname in version.links:
            l = version.links[lname]
            if l.is_deleted:
                query = "match (v:version {project:$project,name:$version}) match (e:endpoint project:$project, group:$group_name, name:$endpoint_name, project:$project,group:$group,group_version:group_version,deleted:false) match (v)-[vl:link_endpoint {name:$link_name,deleted:false}]->(e) set vl.deleted=true"
                params = { "project": version.parent.name,
                    "version": version.version,
                    "link_name": l.name,
                    "group_name": e.group.name,
                    "group_version": e.group.version,
                    "endpoint_name": e.endpoint_name}
                self.db.query(query, params)
            else:
                query = "match (v:version {project:$project,name:$version}) match (e:endpoint {project:$project, group:$group_name, group_version:$group_version, name:$endpoint_name, deleted:false}) merge (v)-[vl:link_endpoint {name:$link_name,delete:false}]->(e)"
                for e in l.endpoints:
                    params = { "project": version.parent.name,
                        "version": version.version,
                        "link_name": l.name,
                        "group_name": e.group.name,
                        "group_version": e.group.version,
                        "endpoint_name": e.endpoint_name}
                    self.db.query(query, params)

    def clean(self):
        cleaners = [ "match (e:endpoint) delete e",
            "match (vl:link_endpoint) delete vl",
            "match (g:group) delete g",
            "match (t:tag) delete t",
            "match (v:version) delete v",
            "match (p:project) delete p"]
        for c in cleaners:
            self.db.query(c, {})

#    def get_links_by_app(self, version, target_app):
#        raise NotImplementedError("get_links_by_app method is not implemented")
#
#    def get_links_by_endpoint(self, version, group, endpoint):
#        raise NotImplementedError("get_links_by_app method is not implemented")
#
#    def get_group(self, version, name, app_id):
#        raise NotImplementedError("get_group method is not implemented")
