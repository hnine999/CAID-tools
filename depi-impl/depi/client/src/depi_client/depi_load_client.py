import grpc
from server.src.server import depi_pb2_grpc
import depi_pb2
import logging


def make_res(toolId, rgn, rgu, rgv, name, URL):
    return depi_pb2.Resource(toolId=toolId,
                             resourceGroupName=rgn,
                             resourceGroupURL=rgu,
                             resourceGroupVersion=rgv,
                             name=name,
                             URL=URL,
                             id=name)


def make_res_change(res):
    return depi_pb2.ResourceChange(
                             name=res.name,
                             URL=res.URL,
                             id=res.name,
                             new_name=res.name,
                             new_URL=res.URL,
                             new_id=res.name,
                             changeType=depi_pb2.ChangeType.Modified)


def make_resource_group(rrs, newVersion):
    return depi_pb2.ResourceGroupChange(name=rrs[0].resourceGroupName,
                                        toolId=rrs[0].toolId,
                                        URL=rrs[0].resourceGroupURL,
                                        version=newVersion,
                                        resources=[depi_pb2.ResourceChange(name=rr.name, URL=rr.URL, id=rr.id,
                                                                           new_name=rr.name, new_URL=rr.URL,
                                                                           new_id=rr.id,
                                                                           changeType=depi_pb2.ChangeType.Modified) for rr in rrs])

def factors(n):
    facs = []
    divisor = 2
    while n > 1:
        if n % divisor == 0:
            facs.append(divisor)
            n = n / divisor
        else:
            divisor += 1
    return facs

def gen_resource_path(resnum):
    if resnum < 2:
        return ""
    facs = factors(resnum)
    if len(facs) == 1:
        return ""
    return "/".join(["d"+str(n) for n in facs])

def do_queries(stub, git_session):

    while True:
        rg_resp = stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=git_session))
        if not rg_resp.ok:
            print("Error getting resource groups: {}".format(rg_resp.msg))
            return
        print("Fetched {} resource groups".format(len(rg_resp.resourceGroups)))
        for rg in rg_resp.resourceGroups:
            num_fetched = 0
            for res_resp in stub.GetResourcesAsStream(depi_pb2.GetResourcesRequest(sessionId=git_session,
                                                                      patterns=[
                                                                          depi_pb2.ResourceRefPattern(toolId=rg.toolId, resourceGroupURL=rg.URL, URLPattern=".*")
                                                                      ])):
                if not res_resp.ok:
                    print("Error getting resources: {}".format(res_resp.msg))
                    return
                num_fetched += 1
            print("Fetched {} resources from {}".format(num_fetched, rg.URL))



def run():
    with grpc.insecure_channel("localhost:5150") as channel:
        stub = depi_pb2_grpc.DepiStub(channel)

        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="git"))
        git_session = response.sessionId
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))

        do_queries(stub, git_session);

if __name__ == "__main__":
    logging.basicConfig()
    run()
