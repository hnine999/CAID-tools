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
def run():
    with grpc.insecure_channel("localhost:5150") as channel:
        stub = depi_pb2_grpc.DepiStub(channel)

        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="git"))
        git_session = response.sessionId
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))

        response = stub.WatchResourceGroup(depi_pb2.WatchResourceGroupRequest(
                                               sessionId=git_session, URL="/git1"))
        if not response.ok:
            print("Error watching resource group: {}".format(response.msg))
            return

        for updateNotify in stub.RegisterCallback(depi_pb2.RegisterCallbackRequest(sessionId=git_session)):
            for update in updateNotify.updates:
                print("{} - {} - {} updated linked to {}".format(
                      update.updatedResource.toolId,
                      update.updatedResource.resourceGroupName,
                      update.updatedResource.name,
                      update.watchedResource.name))
if __name__ == "__main__":
    logging.basicConfig()
    run()
