import threading

import grpc
from server.src.server import depi_pb2_grpc
import depi_pb2
import logging
import argparse

def rr_sort(rr):
    return [rr.resourceGroupName, rr.resourceGroupURL, rr.name, rr.URL]

def rl_sort(rl):
    return [rl.fromRes.toolId, rl.fromRes.resourceGroupName, rl.fromRes.resourceGroupURL,
        rl.fromRes.name, rl.fromRes.URL,
        rl.toRes.toolId, rl.toRes.resourceGroupName, rl.toRes.resourceGroupURL,
        rl.toRes.name, rl.toRes.URL]

class BlackboardClient:
    def __init__(self, stub, user, password, project):
        self.project = project
        self.stub = stub
        self.currResources = []
        self.currLinks = []
        self.watching = False

        response = stub.Login(depi_pb2.LoginRequest(user=user, password=password, project=project, toolId="blackboard"))
        if not response.ok:
            raise Exception(response.msg)

        self.depi_session_id = response.sessionId

    def do_res(self, args):
        resp = self.stub.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(
                sessionId=self.depi_session_id))
        
        rrs = resp.resources
        allRes = False
        if args == "-a":
            rrs = resp.depiResources
            allRes = True
        else:
            self.currResources = []

        tools = {}
        
        for rr in rrs:
            if rr.toolId not in tools:
                tools[rr.toolId] = []
            tools[rr.toolId].append(rr)

        for toolId in tools:
            if not allRes:
                print("Tool {}:".format(toolId))
                tools[toolId].sort(key=rr_sort)
                for item in tools[toolId]:
                    self.currResources.append(item)
                    print("{}: {} {} {} {} {}".format(
                        len(self.currResources),
                        item.resourceGroupName, item.resourceGroupURL,
                        item.name, item.id, item.URL))
            else:
                print("Tool {}:".format(toolId))
                tools[toolId].sort(key=rr_sort)
                for item in tools[toolId]:
                    print("{} {} {} {} {}".format(
                        item.resourceGroupName, item.resourceGroupURL,
                        item.name, item.id, item.URL))
            
    def do_links(self, args):
        resp = self.stub.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(
                sessionId=self.depi_session_id))
        
        allLinks = False
        rls = resp.links
        if args == "-a":
            allLinks = True
            rls = resp.depiLinks
        else:
            self.currLinks = []

        rls.sort(key=rl_sort)
        for rl in rls:
            if not allLinks:
                self.currLinks.append(rl)
                print("{}: {} {} {} {} {} {} -> {} {} {} {} {} {}".format(
                    len(self.currLinks),
                    rl.fromRes.toolId, rl.fromRes.resourceGroupName,
                    rl.fromRes.resourceGroupURL, rl.fromRes.name,
                    rl.fromRes.id, rl.fromRes.URL,
                    rl.toRes.toolId, rl.toRes.resourceGroupName,
                    rl.toRes.resourceGroupURL, rl.toRes.name,
                    rl.toRes.id, rl.toRes.URL))
            else:
                print("{} {} {} {} {} {} -> {} {} {} {} {} {}".format(
                    rl.fromRes.toolId, rl.fromRes.resourceGroupName,
                    rl.fromRes.resourceGroupURL, rl.fromRes.name,
                    rl.fromRes.id, rl.fromRes.URL,
                    rl.toRes.toolId, rl.toRes.resourceGroupName,
                    rl.toRes.resourceGroupURL, rl.toRes.name,
                    rl.toRes.id, rl.toRes.URL))
    def do_link(self, parts):
        parts = parts.split(" ", -1)
        parts_pos = 0
        gotFrom = False
        fromRes = None
        gotTo = False
        toRes = None
        
        while parts_pos < len(parts):
            try:
                idx = int(parts[parts_pos])
                parts_pos += 1
                idx -= 1
                if idx < len(self.currResources):
                    if not gotFrom:
                        fromRes = depi_pb2.ResourceRef(
                            toolId=self.currResources[idx].toolId,
                            resourceGroupURL=self.currResources[idx].resourceGroupURL,
                            URL=self.currResources[idx].URL)
                        gotFrom = True
                    elif not gotTo:
                        toRes = depi_pb2.ResourceRef(
                            toolId=self.currResources[idx].toolId,
                            resourceGroupURL=self.currResources[idx].resourceGroupURL,
                            URL=self.currResources[idx].URL)
                        gotTo = True
                        break
                    else:
                        break
                else:
                    print("Invalid resource index {}".format(idx))
                    return
            except ValueError as e:
                if parts_pos + 3 > len(parts):
                    print("Resource requires tool id, group url, resource url")
                    return
                if not gotFrom:
                    print("Creating from")
                    fromRes = depi_pb2.ResourceRef(
                        toolId=parts[parts_pos],
                        resourceGroupURL=parts[parts_pos+1],
                        URL=parts[parts_pos+2])
                    gotFrom = True
                elif not gotTo:
                    print("Creating to")
                    toRes = depi_pb2.ResourceRef(
                        toolId=parts[parts_pos],
                        resourceGroupURL=parts[parts_pos+1],
                        URL=parts[parts_pos+2])
                    gotTo = True
                    break
                else:
                    print("Unexpected resource data on command line")
                    return
                parts_pos += 3
        if fromRes is None:
            print("No from resource specified")
            return
        if toRes is None:
            print("No to resource specified")
            return

        print("Sending link {} -> {}".format(fromRes, toRes))
        resp = self.stub.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=self.depi_session_id,
                links=[depi_pb2.ResourceLinkRef(fromRes=fromRes,toRes=toRes)]))
        if not resp.ok:
            print(resp.msg)

    def do_unlink(self, parts):
        parts = parts.split(" ", -1)

        if len(parts) == 1:
            try:
                idx = int(parts[0])
                idx -= 1
                if idx < len(self.currLinks):
                    link = self.currLinks[idx]
                    short_link = depi_pb2.ResourceLinkRef(
                        fromRes=depi_pb2.ResourceRef(
                            toolId=link.fromRes.toolId,
                            resourceGroupURL=link.fromRes.resourceGroupURL,
                            URL=link.fromRes.URL),
                        toRes=depi_pb2.ResourceRef(
                            toolId=link.toRes.toolId,
                            resourceGroupURL=link.toRes.resourceGroupURL,
                            URL=link.toRes.URL))

                    resp = self.stub.UnlinkBlackboardResources(
                        depi_pb2.UnlinkBlackboardResourcesRequest(
                        sessionId = self.depi_session_id,
                        links=[short_link]))
                    if not resp.ok:
                        print(resp.msg)
                    return
            except ValueError:
                print("Invalid link number")

        parts_pos = 0
        gotFrom = False
        fromRes = None
        gotTo = False
        toRes = None
        
        while parts_pos < len(parts):
            try:
                idx = int(parts[parts_pos])
                parts_pos += 1
                idx -= 1
                if idx < len(self.currResources):
                    if not gotFrom:
                        fromRes = depi_pb2.ResourceRef(
                            toolId=self.currResources[idx].toolId,
                            resourceGroupURL=self.currResources[idx].resourceGroupURL,
                            URL=self.currResources[idx].URL)
                        gotFrom = True
                    elif not gotTo:
                        toRes = depi_pb2.ResourceRef(
                            toolId=self.currResources[idx].toolId,
                            resourceGroupURL=self.currResources[idx].resourceGroupURL,
                            URL=self.currResources[idx].URL)
                        gotTo = True
                        break
                    else:
                        break
                else:
                    print("Invalid resource index {}".format(idx))
                    return
            except ValueError as e:
                if parts_pos + 3 > len(parts):
                    print("Resource requires tool id, group url, resource url")
                    return
                if not gotFrom:
                    fromRes = depi_pb2.ResourceRef(
                        toolId=parts[parts_pos],
                        resourceGroupURL=parts[parts_pos+1],
                        URL=parts[parts_pos+2])
                    gotFrom=True
                elif not gotTo:
                    toRes = depi_pb2.ResourceRef(
                        toolId=parts[parts_pos],
                        resourceGroupURL=parts[parts_pos+1],
                        URL=parts[parts_pos+2])
                    gotTo=True
                    break
                else:
                    print("Unexpected resource data on command line")
                    return
                parts_pos += 3
        if fromRes is None:
            print("No from resource specified")
            return
        if toRes is None:
            print("No to resource specified")
            return

        resp = self.stub.UnlinkBlackboardResources(
            depi_pb2.UnlinkBlackboardResourcesRequest(
                sessionId=self.depi_session_id,
                links=[depi_pb2.ResourceLinkRef(fromRes=fromRes,toRes=toRes)]))
        if not resp.ok:
            print(resp.msg)

    def do_save(self, args):
        resp = self.stub.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(
                sessionId=self.depi_session_id))
        if not resp.ok:
            print(resp.msg)
        
    def do_clear(self, args):
        resp = self.stub.ClearBlackboard(
            depi_pb2.ClearBlackboardRequest(
                sessionId=self.depi_session_id))
        if not resp.ok:
            print(resp.msg)

    def do_watch(self, args):
        if self.watching:
            print("Already watching blackboard events")
            return
        self.watching = True
        t = threading.Thread(target=BlackboardClient.run_watch, args=(self,))
        t.start()

    def run_watch(self):
        watcher = self.stub.WatchBlackboard(
                    depi_pb2.WatchBlackboardRequest(
                    sessionId=self.depi_session_id))
        for evt in watcher:
            for update in evt.updates:
                if update.updateType == depi_pb2.UpdateType.AddResource:
                    print("Blackboard added resource {} {} {}\n".format(
                        update.resource.toolId, update.resource.resourceGroupURL,
                        update.resource.URL))
                elif update.updateType == depi_pb2.UpdateType.RemoveResource:
                    print("Blackboard removed resource {} {} {}\n".format(
                        update.resource.toolId, update.resource.resourceGroupURL,
                        update.resource.URL))
                elif update.updateType == depi_pb2.UpdateType.AddLink:
                    print("Blackboard added link {} {} {} -> {} {} {}\n".format(
                        update.link.fromRes.toolId, update.link.fromRes.resourceGroupURL,
                        update.link.fromRes.URL, update.link.toRes.toolId,
                        update.link.toRes.resourceGroupURL, update.link.toRes.URL))
                elif update.updateType == depi_pb2.UpdateType.RemoveLink:
                    print("Blackboard removed link {} {} {} -> {} {} {}\n".format(
                        update.link.fromRes.toolId, update.link.fromRes.resourceGroupURL,
                        update.link.fromRes.URL, update.link.toRes.toolId,
                        update.link.toRes.resourceGroupURL, update.link.toRes.URL))

def run():
    parser = argparse.ArgumentParser(
        prog="Depi Git",
        description="Synchronizes a Git repo with the Depi",
        epilog="")

    parser.add_argument("--depi", dest="depi_url", default="localhost:5150", help="The hostname:port of the depi")
    parser.add_argument("--user", dest="user", default="mark", help="The Depi user name")
    parser.add_argument("--password", dest="password", default="foo", help="The Depi password")
    parser.add_argument("--project", dest="project", default="testproj", help="The Depi project")

    args = parser.parse_args()

    with grpc.insecure_channel(args.depi_url) as channel:
        stub = depi_pb2_grpc.DepiStub(channel)

        client = BlackboardClient(stub, args.user, args.password, args.project)

        while True:
            line = input("Blackboard> ")
            parts = line.split(" ", 1)
            cmd = parts[0]
            rest = ""
            if len(parts) > 1:
                rest = parts[1]
            
            if cmd == "res":
                client.do_res(rest)
            elif cmd == "links":
                client.do_links(rest)
            elif cmd == "link":
                client.do_link(rest)
            elif cmd == "unlink":
                client.do_unlink(rest)
            elif cmd == "save":
                client.do_save(rest)
            elif cmd == "clear":
                client.do_clear(rest)
            elif cmd == "watch":
                client.do_watch(rest)
            elif cmd == "help":
                print("Available commands:")
                print("res [-a]    display available resources (-a = all known resources)")
                print("links [-a]    display links in this session (-a = all known links)")
            else:
                print("Invalid command, type 'help' for help")
            
if __name__ == "__main__":
    logging.basicConfig()
    run()
