import grpc
from server.src.server import depi_pb2_grpc
import depi_pb2
import logging

def make_rr(toolId, rgn, rgu, rgv, name, URL):
    return depi_pb2.ResourceRef(toolId=toolId,
                                resourceGroupName=rgn,
                                resourceGroupURL=rgu,
                                resourceGroupVersion=rgv,
                                name=name,
                                URL=URL)

def make_resource_group(rrs, newVersion):
    return depi_pb2.ResourceGroupChange(name=rrs[0].resourceGroupName,
                                  toolId=rrs[0].toolId,
                                  URL=rrs[0].resourceGroupURL,
                                  version=newVersion,
                                  resources = [depi_pb2.ResourceChange(name=rr.name, URL=rr.URL, changeType=1) for rr in rrs])

def run():
    with grpc.insecure_channel("localhost:5150") as channel:
        stub = depi_pb2_grpc.DepiStub(channel)
        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="foo", project="testproj", toolId="git"))
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))
        response = stub.Login(depi_pb2.LoginRequest(user="bar", password="foo", project="testproj", toolId="git"))
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))
        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="quux"))
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))

        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="git"))
        git_session = response.sessionId
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))

        grr1 = make_rr("git", "gitgroup1", "/git1", "1.0.0",
                                   "stooge1", "/stooges/moe")
        grr2 = make_rr("git", "gitgroup1", "/git1", "1.0.0",
                                   "stooge2", "/stooges/larry")
        grr3 = make_rr("git", "gitgroup1", "/git1", "1.0.0",
                                   "stooge3", "/stooges/curly")

        response = stub.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=git_session,
                resourceRefs = [grr1, grr2, grr3]))
        if not response.ok:
            print("Error adding resources to blackboard: {}".format(response.msg))
            return

        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="webgme"))
        webgme_session = response.sessionId

        wrr1 = make_rr("webgme", "webgmegroup1", "/A", "1.0.0",
                                   "c1", "/A/a")
        wrr2 = make_rr("webgme", "webgmegroup1", "/A", "1.0.0",
                                   "c2", "/A/b")
        wrr3 = make_rr("webgme", "webgmegroup2", "/D", "1.0.0",
                                   "c3", "/D/q")

        response = stub.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=webgme_session,
                resourceRefs = [wrr1, wrr2, wrr3]))
        if not response.ok:
            print("Error adding resources to blackboard: {}".format(response.msg))
            return

        response = stub.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=git_session,
                links=[depi_pb2.ResourceLink(fromRes=wrr3,toRes=grr1)]))
        if not response.ok:
            print("Error linking blackboard resources: {}".format(response.msg))
            return

        response = stub.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=git_session,
                links=[depi_pb2.ResourceLink(fromRes=wrr2,toRes=grr1)]))
        if not response.ok:
            print("Error linking blackboard resources: {}".format(response.msg))
            return

        response = stub.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=git_session,
                links=[depi_pb2.ResourceLink(fromRes=wrr1,toRes=grr3)]))
        if not response.ok:
            print("Error linking blackboard resources: {}".format(response.msg))
            return

        response = stub.SaveBlackboard(depi_pb2.SaveBlackboardRequest(sessionId=git_session))
        if not response.ok:
            print("Error saving blackboard")
            return

        wrr3 = make_rr("webgme", "webgmegroup2", "/D", "1.0.0",
                                   "c3", "/D/q")
        response = stub.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(sessionId=git_session,
                                                resourceGroup=make_resource_group([wrr2, wrr3], "1.0.1")))
        if not response.ok:
            print("Error updating resource group: {}".format(response.msg))
            return

if __name__ == "__main__":
    logging.basicConfig()
    run()
