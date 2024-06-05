import grpc
from server.src.server import depi_pb2_grpc
import depi_pb2
import logging
import threading

def watchdepi(stub, session):
    for data in stub.WatchDepi(depi_pb2.WatchDepiRequest(sessionId=session)):
        pass


def run():
    with grpc.insecure_channel("localhost:5150") as channel:
        stub = depi_pb2_grpc.DepiStub(channel)

        for i in range(0, 100000):
            response = stub.Login(depi_pb2.LoginRequest(user="mark", password="mark", project="testproj", toolId="git"))
            if not response.ok:
                print(response.msg)
                break
            git_session = response.sessionId
            t = threading.Thread(target=watchdepi, args=(stub, git_session))
            t.start()
            response = stub.Logout(depi_pb2.LogoutRequest(sessionId=git_session))
            if not response.ok:
                print(response.msg)
                break


if __name__ == "__main__":
    logging.basicConfig()
    run()
