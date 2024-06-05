import grpc
from server.src.server import depi_pb2_grpc
import depi_pb2
import logging

def run():
    with grpc.insecure_channel("localhost:5150") as channel:
        stub = depi_pb2_grpc.DepiStub(channel)
        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="git"))

        session = response.sessionId
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))

        response = stub.GetResourceGroups(
            depi_pb2.GetResourceGroupsRequest(sessionId=session))

        if not response.ok:
            print("Error getting resource groups: {}".format(response.msg))
            return

        for rg in response.resourceGroups:
            print("{} {}".format(rg.name, rg.URL))

        response = stub.GetDirtyLinks(
            depi_pb2.GetDirtyLinksRequest(sessionId=session, toolId="git", name="testrepo2", URL="/Users/mark/vandy/caid/testrepo2"))
        if not response.ok:
            print("Error getting dirty resources: {}".format(response.msg))
            return

        for r in response.resources:
            print("{} is dirty".format(r.name))
# alc git@git.isis.vanderbilt.edu:alc/alc

        for l in response.links:
            print("{} {} {} -> {} {} {} is dirty".format(
                l.fromRes.toolId, l.fromRes.resourceGroupURL, l.fromRes.URL,
                l.toRes.toolId, l.toRes.resourceGroupURL, l.toRes.URL))


#        updates = []
#        updates.append(depi_pb2.Update(updateType=depi_pb2.UpdateType.RemoveResource,
#            resource=depi_pb2.ResourceRef(toolId="git", resourceGroupName="testrepo1",
#                resourceGroupURL="/Users/mark/vandy/caid/testrepo1",
#                name="Foxtrot2.p", URL="Foxtrot2.p", id="Foxtrot2.p")))
#
#        response = stub.UpdateDepi(depi_pb2.UpdateDepiRequest(sessionId=session, updates=updates))
#        if not response.ok:
#            print("Error removing resource: {}".format(response.msg))

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
                                                         resourceURL=res.URL)
                resp2 = stub.GetDependencyGraph(req)
                if not resp2.ok:
                    print("Error getting dependency graph: {}".format(resp2.msg))
                    continue

                print("Dependency links for {} {} {}".format(res.toolId, res.resourceGroupURL,
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
                            print("        {} {} {}".format(inferred.toolId, inferred.resourceGroupURL, inferred.URL))
                print("---------------------------------------------")

        response = stub.GetLinks(
            depi_pb2.GetLinksRequest(sessionId=session,
                patterns=[
                    depi_pb2.ResourceLinkPattern(
                        fromRes=depi_pb2.ResourceRefPattern(
                            toolId="git",
                            resourceGroupURL="git@git.isis.vanderbilt.edu:alc/alc",
                            URLPattern=".*"),
                        toRes=depi_pb2.ResourceRefPattern(
                            toolId="git",
                            resourceGroupURL="git@git.isis.vanderbilt.edu:alc/alc",
                            URLPattern=".*")
                    )]))

        for link in response.resourceLinks:
            print("-----------------------------")
            print("{} {} {} -> {} {} {}".format(
                link.fromRes.toolId,
                link.fromRes.resourceGroupURL,
                link.fromRes.URL,
                link.toRes.toolId,
                link.toRes.resourceGroupURL,
                link.toRes.URL))


if __name__ == "__main__":
    logging.basicConfig()
    run()
