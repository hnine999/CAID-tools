import grpc
from server.src.server import depi_pb2_grpc
import depi_pb2
import logging


def showDepGraph(stub, session):
    rgResponse = stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=session))
    for rg in rgResponse.resourceGroups:
        response = stub.GetResources(
            depi_pb2.GetResourcesRequest(sessionId=session,
                                         patterns=[depi_pb2.ResourceRefPattern(
                                             toolId=rg.toolId,
                                             resourceGroupURL=rg.URL,
                                             URLPattern=".*")]))

        if not response.ok:
            print("Error in GetResourcesRequest: {}".format(response.msg))
            return

        for res in response.resources:
            print("{} {} {}".format(res.toolId, res.resourceGroupURL, res.URL))

            req = depi_pb2.GetDependencyGraphRequest(sessionId=session,
                                                     toolId=res.toolId,
                                                     resourceGroupURL=res.resourceGroupURL,
                                                     resourceURL=res.URL,
                                                     dependenciesType=depi_pb2.DependenciesType.Dependencies)
            resp2 = stub.GetDependencyGraph(req)
            if not resp2.ok:
                print("Error getting dependency graph: {}".format(resp2.msg))
                continue

            print("Dependancy links for {} {} {}".format(res.toolId, res.resourceGroupURL,
                                                         res.URL))
            for link2 in resp2.links:
                print("{} {} {} -> {} {} {}   dirty: {}  lastClean: {}".format(link2.fromRes.toolId,
                                                    link2.fromRes.resourceGroupURL,
                                                    link2.fromRes.URL,
                                                    link2.toRes.toolId,
                                                    link2.toRes.resourceGroupURL,
                                                    link2.toRes.URL,
                                                    link2.dirty,
                                                    link2.lastCleanVersion))
                if len(link2.inferredDirtiness) > 0:
                    print("    Inferred dirtiness from:")
                    for inferred in link2.inferredDirtiness:
                        print("        {} {} {} last clean in version {}".format(inferred.resource.toolId, inferred.resource.resourceGroupURL, inferred.resource.URL, inferred.lastCleanVersion))
            print("---------------------------------------------")

            print("{} {} {}".format(res.toolId, res.resourceGroupURL, res.URL))

            req = depi_pb2.GetDependencyGraphRequest(sessionId=session,
                                                     toolId=res.toolId,
                                                     resourceGroupURL=res.resourceGroupURL,
                                                     resourceURL=res.URL,
                                                     dependenciesType=depi_pb2.DependenciesType.Dependants)
            resp2 = stub.GetDependencyGraph(req)
            if not resp2.ok:
                print("Error getting dependency graph: {}".format(resp2.msg))
                continue

            print("Dependant links for {} {} {}".format(res.toolId, res.resourceGroupURL,
                                                        res.URL))
            for link2 in resp2.links:
                print("{} {} {} -> {} {} {}".format(link2.fromRes.toolId,
                                                    link2.fromRes.resourceGroupURL,
                                                    link2.fromRes.URL,
                                                    link2.toRes.toolId,
                                                    link2.toRes.resourceGroupURL,
                                                    link2.toRes.URL))
                if len(link2.inferredDirtiness) > 0:
                    print("    Inferred dirtiness from:")
                    for inferred in link2.inferredDirtiness:
                        print("        {} {} {} last clean in version {}".format(inferred.resource.toolId, inferred.resource.resourceGroupURL, inferred.resource.URL, inferred.lastCleanVersion))
            print("---------------------------------------------")


def run():
    with grpc.insecure_channel("localhost:5150") as channel:
        stub = depi_pb2_grpc.DepiStub(channel)
        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="git"))

        session = response.sessionId
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))

        response = stub.GetLinks(depi_pb2.GetBlackboardResourcesRequest(sessionId=session))
        if not response.ok:
            print("Error getting all links: {}".format(response.msg))

        showDepGraph(stub, session)

        resChange = depi_pb2.ResourceChange(name="Nand.p", URL="/Nand.p", changeType=depi_pb2.ChangeType.Modified,
                                            id="Nand.p")
        rgChange = depi_pb2.ResourceGroupChange(toolId="git", name="testrepo1", URL="/extra3/caid/testrepo1",
                                                version="12345", resources=[resChange])

        print("\n\nChanging Nand.p\n\n")
        response = stub.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(sessionId=session, resourceGroup=rgChange))
        if not response.ok:
            print("Error updating resource: {}".format(response.msg))

        showDepGraph(stub, session)

        response = stub.GetLinks(depi_pb2.GetLinksRequest(sessionId=session))
        if not response.ok:
            print("Error getting all links: {}".format(response.msg))


if __name__ == "__main__":
    logging.basicConfig()
    run()
