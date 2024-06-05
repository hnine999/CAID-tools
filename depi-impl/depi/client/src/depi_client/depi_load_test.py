import grpc
from server.src.server import depi_pb2_grpc
import depi_pb2
import logging
import datetime

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

def large_blackboard(stub, git_session):
    resources = []

    res_group_res = {}
    res_groups = {}
    for i in range(0, 100000):
        res_name = "res"+str(i)
        res_path = gen_resource_path(i // 10)
        if len(res_path) > 0:
            res_path = res_path + "/"
        print(res_path)
        rg_url = "/extra3/caid/dummy"+str(i//10000)
        rg_name = "dummy"+str(i//10000)
        res = make_res("git", rg_name, rg_url, "000000",
                       res_name, res_path+res_name)
        if rg_name not in res_group_res:
            res_group_res[rg_name] = [res]
        else:
            res_group_res[rg_name].append(res)
        if rg_name not in res_groups:
            res_groups[rg_name] = depi_pb2.ResourceGroupChange(toolId="git", name=rg_name, URL=rg_url,
                                                               version="000000", resources=[])
        resources.append(res)


    start = datetime.datetime.now()
    for i in range(0, 10):
        response = stub.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=git_session,
                resources=resources[i*10000:(i+1)*10000]))

        if not response.ok:
            print("Error adding resources to blackboard: {}".format(response.msg))
            return

    end = datetime.datetime.now()
    print("It took {} seconds to add {} resources to the blackboard".format(
          (end-start).total_seconds(), len(resources)))

    links = []
    for i in range(0,9000):
        for j in range(0, 9):
            fromRes = resources[i*10+j]
            toRes = resources[i*10+977+j+1]
            links.append(depi_pb2.ResourceLinkRef(
                fromRes=depi_pb2.ResourceRef(toolId=fromRes.toolId, resourceGroupURL=fromRes.resourceGroupURL,
                                             URL=fromRes.URL),
                toRes=depi_pb2.ResourceRef(toolId=toRes.toolId, resourceGroupURL=toRes.resourceGroupURL,
                                             URL=toRes.URL)))

    start = datetime.datetime.now()
    for i in range(0, 10):
        response = stub.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(sessionId=git_session, links=links[i*10000:(i+1)*10000]))

        if not response.ok:
            print("Error adding resources to blackboard: {}".format(response.msg))
            return

    end = datetime.datetime.now()
    print("It took {} seconds to link {} blackboard resources".format(
        (end-start).total_seconds(), len(links)))

    start = datetime.datetime.now()
    response = stub.SaveBlackboard(
        depi_pb2.SaveBlackboardRequest(sessionId=git_session))

    if not response.ok:
        print("Error saving blackboard: {}".format(response.msg))
        return
    end = datetime.datetime.now()
    print("It took {} seconds to save the blackboard".format(
        (end-start).total_seconds()))

    for rg in res_groups:
        change = True
        rg_change = res_groups[rg]
        for res in res_group_res[rg]:
            if change:
                rg_change.resources.append(make_res_change(res))
            change = not change
        start = datetime.datetime.now()
        response = stub.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(sessionId=git_session, resourceGroup=rg_change))
        end = datetime.datetime.now()
        print("It took {} seconds to update resource group {}", (end-start).total_seconds(), rg_change.URL)
        break



def run():
    with grpc.insecure_channel("localhost:5150") as channel:
        stub = depi_pb2_grpc.DepiStub(channel)

        response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="git"))
        git_session = response.sessionId
        print("response.ok={}  response.msg={}".format(response.ok, response.msg))

        large_blackboard(stub, git_session);

if __name__ == "__main__":
    logging.basicConfig()
    run()
