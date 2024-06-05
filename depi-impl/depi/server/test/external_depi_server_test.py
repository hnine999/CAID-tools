import unittest

import depi_pb2
import depi_pb2_grpc

from depi_server.model.depi_model import (ResourceGroup, Resource, Link, LinkWithResources, ResourceRef)

class TestExternalDepiServer(unittest.TestCase):
    depi: depi_pb2_grpc.DepiStub = None
    channel = None
    server_pipe = None
    def login(self):
        req = depi_pb2.LoginRequest(user="mark", password="mark", project="unittest", toolId="git")
        resp = self.depi.Login(req)
        self.assertTrue(resp.ok, "Login failed with error: "+resp.msg)
        self.session = resp.sessionId

    def make_resource(self, tool_id, rg, res, version):
        return (ResourceGroup(name=rg, toolId=tool_id, URL=rg, version=version),
                Resource(name=res, id=res, URL=res))

    def make_link(self, from_rg_res, to_rg_res):
        from_rg, from_res = from_rg_res
        to_rg, to_res = to_rg_res
        return LinkWithResources(fromRg=from_rg, fromRes=from_res,
                                 toRg=to_rg, toRes=to_res)

    def add_resource(self, rg, res):
        self.depi.AddResourceGroup(depi_pb2.AddResourceGroupRequest(sessionId=self.session,
                                                                    resourceGroup=depi_pb2.ResourceGroup(
                                                                        toolId=rg.toolId,
                                                                        URL=rg.URL,
                                                                        name=rg.name,
                                                                        version=rg.version)))
        self.depi.AddResource(depi_pb2.AddResourceRequest(sessionId=self.session,
                                                          toolId=rg.toolId,
                                                          resourceGroupURL=rg.URL,
                                                          URL=res.URL,
                                                          name=res.name,
                                                          id=res.id))
    def make_data_model(self):
        self.r1 = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        self.add_resource(self.r1[0], self.r1[1])
        self.r2 = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')
        self.add_resource(self.r2[0], self.r2[1])
        self.r3 = self.make_resource('git', 'resourcegroup1', 'resource3', '000000')
        self.add_resource(self.r3[0], self.r3[1])
        self.r4 = self.make_resource('git', 'resourcegroup2', 'resource4', '123456')
        self.add_resource(self.r4[0], self.r4[1])
        self.r5 = self.make_resource('git', 'resourcegroup2', 'resource5', '123456')
        self.add_resource(self.r5[0],self. r5[1])

        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(self.r1, self.r2).toLink().toGrpc()))
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(self.r2, self.r3).toLink().toGrpc()))
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(self.r3, self.r4).toLink().toGrpc()))
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(self.r4, self.r5).toLink().toGrpc()))

    def test_login_success(self):
        req = depi_pb2.LoginRequest(user="mark", password="mark", project="unittest", toolId="git")
        resp = self.depi.Login(req)
        self.assertTrue(resp.ok, "Login should succeed")

    def test_login_failure(self):
        req = depi_pb2.LoginRequest(user="mark", password="wrong", project="unittest", toolId="git")
        resp = self.depi.Login(req)
        self.assertFalse(resp.ok, "Login should fail")

    def test_create_tag(self):
        self.login()
        self.depi.CreateTag(depi_pb2.CreateTagRequest(sessionId=self.session, tagName="testtag", fromBranch="main"))

        self.depi.SetBranch(depi_pb2.SetBranchRequest(sessionId=self.session, branch="testtag"))

    def test_get_all_resources(self):
        self.login()
        self.make_data_model()

        response = self.depi.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))
        patterns = []
        for rg in response.resourceGroups:
            patterns.append(depi_pb2.ResourceRefPattern(toolId=rg.toolId, resourceGroupURL=rg.URL, URLPattern=".*"))

        response = self.depi.GetResources(depi_pb2.GetResourcesRequest(sessionId=self.session, patterns=patterns))
        self.assertEqual(5, len(response.resources), "There should be 5 resources in the database")

    def test_get_all_resources_as_stream(self):
        self.login()
        self.make_data_model()

        response = self.depi.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))
        patterns = []
        for rg in response.resourceGroups:
            patterns.append(depi_pb2.ResourceRefPattern(toolId=rg.toolId, resourceGroupURL=rg.URL, URLPattern=".*"))

        count = 0
        for res in self.depi.GetResourcesAsStream(depi_pb2.GetResourcesRequest(sessionId=self.session, patterns=patterns)):
            count = count + 1
        self.assertEqual(5, count, "There should be 5 resources in the database")

    def test_get_all_links_as_stream(self):
        self.login()
        self.make_data_model()

        count = 0
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            count = count + 1
        self.assertEqual(4, count, "There should be 4 links in the database")

    def test_get_links(self):
        self.login()
        self.make_data_model()

        count = 0
        request = depi_pb2.GetLinksRequest(sessionId=self.session, patterns=[
            depi_pb2.ResourceLinkPattern(fromRes=depi_pb2.ResourceRefPattern(toolId=self.r1[0].toolId,resourceGroupURL=self.r1[0].URL,URLPattern=self.r1[1].URL),
                                         toRes=depi_pb2.ResourceRefPattern(toolId=self.r2[0].toolId,resourceGroupURL=self.r2[0].URL,URLPattern=self.r2[1].URL))])

        response = self.depi.GetLinks(request)
        self.assertEqual(1, len(response.resourceLinks), "There should be 1 link returned")
        self.assertEqual(self.r1[1].URL, response.resourceLinks[0].fromRes.URL, "from URL should match r1")
        self.assertEqual(self.r2[1].URL, response.resourceLinks[0].toRes.URL, "to URL should match r2")

    def test_get_links_as_stream(self):
        self.login()
        self.make_data_model()

        count = 0
        request = depi_pb2.GetLinksRequest(sessionId=self.session, patterns=[
            depi_pb2.ResourceLinkPattern(fromRes=depi_pb2.ResourceRefPattern(toolId=self.r1[0].toolId,resourceGroupURL=self.r1[0].URL,URLPattern=self.r1[1].URL),
                                         toRes=depi_pb2.ResourceRefPattern(toolId=self.r2[0].toolId,resourceGroupURL=self.r2[0].URL,URLPattern=self.r2[1].URL))])

        links = []
        for link in self.depi.GetLinksAsStream(request):
            links.append(link)
        self.assertEqual(1, len(links), "There should be 1 link returned")
        self.assertEqual(self.r1[1].URL, links[0].resourceLink.fromRes.URL, "from URL should match r1")
        self.assertEqual(self.r2[1].URL, links[0].resourceLink.toRes.URL, "to URL should match r2")

    def test_edit_resource_group(self):
        self.login()
        self.make_data_model()
        (folder, folderres) = self.make_resource("git", "folderrg", "/thing", "111111")
        self.add_resource(folder, folderres)

        rg_edit = depi_pb2.ResourceGroupEdit(toolId="git", URL="folderrg",
                                             new_toolId="git2", new_URL="folder2rg", new_name="folder2rgname",
                                             new_version="222222")

        edit_req = depi_pb2.EditResourceGroupRequest(sessionId=self.session, resourceGroup=rg_edit)

        resp = self.depi.EditResourceGroup(edit_req)
        self.assertTrue(resp.ok, resp.msg)

        get_rgs_req = depi_pb2.GetResourceGroupsRequest(sessionId=self.session)
        resp = self.depi.GetResourceGroups(get_rgs_req)
        self.assertTrue(resp.ok, resp.msg)

        found = False
        for rg in resp.resourceGroups:
            self.assertFalse(rg.toolId != "git" and rg.URL=="folderrg", "There should be no resource group with folderrg as a URL")
            if rg.toolId == "git2" and rg.URL == "folder2rg":
                found = True
                self.assertEqual(rg.name, "folder2rgname", "resource group name should be updated")
                self.assertEqual(rg.version, "222222", "resource group version should be updated")
        self.assertTrue(found, "The updated resource group should be present in the resource groups")

    def test_update_in_folder(self):
        self.login()
        self.make_data_model()
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(sessionId=self.session,
                                                              link=self.make_link(folder, self.r1).toLink().toGrpc()))

        depiUpdates = self.depi.RegisterCallback(
            depi_pb2.RegisterCallbackRequest(sessionId=self.session))

        self.depi.WatchResourceGroup(
            depi_pb2.WatchResourceGroupRequest(sessionId=self.session, toolId=self.r1[0].toolId,
                                        URL=self.r1[0].URL))

        res_change = depi_pb2.ResourceChange(
            URL="/folder/res1.c",
            name="/folder/res1.c",
            id="/folder/res1.c",
            new_URL="/folder/res1.c",
            new_name="/folder/res1.c",
            new_id="/folder/res1.c",
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId="git",
            URL="folderrg",
            name="folderrg",
            version="111112",
            resources=[res_change]
        )

        update_watched_rr = ResourceRef(toolId=self.r1[0].toolId, resourceGroupURL=self.r1[0].URL, url=self.r1[1].URL)
        update_changed_rr = ResourceRef(toolId="git", resourceGroupURL="folderrg", url="/folder/")

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        notification = next(depiUpdates)
        updateWatched = ResourceRef.fromGrpc(notification.updates[0].watchedResource)
        updateChanged = ResourceRef.fromGrpc(notification.updates[0].updatedResource)
        self.assertEqual(update_watched_rr, updateWatched, "Watched is not correct")
        self.assertEqual(update_changed_rr, updateChanged, "Changed is not correct")

        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/":
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result of the update")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

    def test_add_in_folder(self):
        self.login()
        self.make_data_model()
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(sessionId=self.session,
                                                              link=self.make_link(folder, self.r1).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL="/folder/res1.c",
            name="/folder/res1.c",
            id="/folder/res1.c",
            new_URL="/folder/res1.c",
            new_name="/folder/res1.c",
            new_id="/folder/res1.c",
            changeType=depi_pb2.ChangeType.Added
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId="git",
            URL="folderrg",
            name="folderrg",
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change
            ))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/":
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result of the add")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

    def test_rename_in_folder(self):
        self.login()
        self.make_data_model()
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(sessionId=self.session,
                                                              link=self.make_link(folder, self.r1).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL="/folder/res1.c",
            name="/folder/res1.c",
            id="/folder/res1.c",
            new_URL="/folder/res1.c",
            new_name="/folder/res1.c",
            new_id="/folder/res1.c",
            changeType=depi_pb2.ChangeType.Renamed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId="git",
            URL="folderrg",
            name="folderrg",
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/":
                self.assertFalse(link.resourceLink.dirty, "Link should not be marked dirty as a result of the rename")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

    def test_modify_rename_in_folder(self):
        self.login()
        self.make_data_model()
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(sessionId=self.session,
                                                              link=self.make_link(folder, self.r1).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL="/folder/res1.c",
            name="/folder/res1.c",
            id="/folder/res1.c",
            new_URL="/folder/res1.c",
            new_name="/folder/res1.c",
            new_id="/folder/res1.c",
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId="git",
            URL="folderrg",
            name="folderrg",
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change
            )
        )
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/":
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result of the rename")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

    def test_rename_in_folder_known_resource(self):
        self.login()
        self.make_data_model()
        known = self.make_resource("git", "folderrg", "/folder/res2.c", "111111")
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(known[0], known[1])
        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(folder, self.r1).toLink().toGrpc()))
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(known, self.r2).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL="/folder/res2.c",
            name="/folder/res2.c",
            id="/folder/res2.c",
            new_URL="/folder/res2b.c",
            new_name="/folder/res2b.c",
            new_id="/folder/res2b.c",
            changeType=depi_pb2.ChangeType.Renamed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId="git",
            URL="folderrg",
            name="folderrg",
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change
            )
        )
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/":
                self.assertFalse(link.resourceLink.dirty, "Link should not be marked dirty as a result of the rename")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/res2b.c":
                self.assertFalse(link.resourceLink.dirty, "Link should not be marked dirty as a result of the rename")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

    def test_modify_rename_in_folder_known_resource(self):
        self.login()
        self.make_data_model()
        known = self.make_resource("git", "folderrg", "/folder/res2.c", "111111")
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(known[0], known[1])
        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(folder, self.r1).toLink().toGrpc()))
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(known, self.r1).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL="/folder/res2.c",
            name="/folder/res2.c",
            id="/folder/res2.c",
            new_URL="/folder/res2b.c",
            new_name="/folder/res2b.c",
            new_id="/folder/res2b.c",
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId="git",
            URL="folderrg",
            name="folderrg",
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change
            )
        )
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")


        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/":
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result of the rename")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/res2b.c":
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result of the rename")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

    def test_delete_resource_group(self):
        self.login()
        self.make_data_model()

        del_rg_req = depi_pb2.RemoveResourceGroupRequest(sessionId=self.session,
                                                         resourceGroup=depi_pb2.ResourceGroupRef(
                                                             toolId="git", URL="resourcegroup1"))
        resp = self.depi.RemoveResourceGroup(del_rg_req)
        self.assertTrue(resp.ok, "DeleteResourceGroup should succeed")

        del_rg_req = depi_pb2.RemoveResourceGroupRequest(sessionId=self.session,
                                                         resourceGroup=depi_pb2.ResourceGroupRef(
                                                             toolId="git", URL="resourcegroup2"))
        resp = self.depi.RemoveResourceGroup(del_rg_req)
        self.assertTrue(resp.ok, "DeleteResourceGroup should succeed")

        num_rg = 0
        for rg in self.depi.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session)).resourceGroups:
            num_rg += 1

        num_links = 0
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            num_links += 1

        self.assertEqual(0, num_rg, "there should be no resource groups left")
        self.assertEqual(0, num_links, "there should be no links left")

    def test_delete_in_folder(self):
        self.login()
        self.make_data_model()
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(folder, self.r1).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL="/folder/res1.c",
            name="/folder/res1.c",
            id="/folder/res1.c",
            new_URL="/folder/res1.c",
            new_name="/folder/res1.c",
            new_id="/folder/res1.c",
            changeType=depi_pb2.ChangeType.Removed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId="git",
            URL="folderrg",
            name="folderrg",
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change
            )
        )
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/":
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result of the delete")
                self.assertFalse(link.resourceLink.deleted, "Link should not be deleted for deleting an unknown resource")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

    def test_delete_in_folder_known_resource(self):
        self.login()
        self.make_data_model()
        known = self.make_resource("git", "folderrg", "/folder/res2.c", "111111")
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(known[0], known[1])
        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(folder, self.r1).toLink().toGrpc()))
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(known, self.r2).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL="/folder/res2.c",
            name="/folder/res2.c",
            id="/folder/res2.c",
            new_URL="/folder/res2b.c",
            new_name="/folder/res2b.c",
            new_id="/folder/res2b.c",
            changeType=depi_pb2.ChangeType.Removed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId="git",
            URL="folderrg",
            name="folderrg",
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change
            )
        )
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session, includeDeleted=True)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/":
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result of the delete")
                self.assertFalse(link.resourceLink.deleted, "Link should not be deleted for deleting an unknown resource")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session, includeDeleted=True)):
            if link.resourceLink.fromRes.toolId == "git" and \
                    link.resourceLink.fromRes.resourceGroupURL == "folderrg" and \
                    link.resourceLink.fromRes.URL == "/folder/res2.c":
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result of the delete")
                self.assertTrue(link.resourceLink.deleted, "Link should be deleted for deleting the from resource")
                found = True
        self.assertTrue(found, "Should have found the link that was updated")

    def test_delete_in_folder_to_resource(self):
        self.login()
        self.make_data_model()
        known = self.make_resource("git", "folderrg", "/folder/res2.c", "111111")
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(known[0], known[1])
        self.add_resource(folder[0], folder[1])
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(folder, self.r1).toLink().toGrpc()))
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(known, self.r2).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Removed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change
            )
        )
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session, includeDeleted=True)):
            if link.resourceLink.toRes.toolId == self.r2[0].toolId and \
                    link.resourceLink.toRes.resourceGroupURL == self.r2[0].URL and \
                    link.resourceLink.toRes.URL == self.r2[1].URL:
                self.assertFalse(link.resourceLink.dirty, "Link should not be marked dirty as a result deleting the to resource")
                self.assertTrue(link.resourceLink.deleted, "Link should be deleted if the to resource is deleted")
                found = True
        self.assertFalse(found, "Link should have been deleted when to resource was deleted")

    def test_delete_from_resource(self):
        self.login()
        self.make_data_model()
        known = self.make_resource("git", "folderrg", "/folder/res2.c", "111111")
        target = self.make_resource("git", "folderrg", "/folder/target.c", "111111")
        folder = self.make_resource("git", "folderrg", "/folder/", "111111")

        self.add_resource(known[0], known[1])
        self.add_resource(target[0], target[1])
        self.add_resource(folder[0], folder[1])

        known_link = self.make_link(known, target)
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=known_link.toLink().toGrpc()))
        self.depi.LinkResources(depi_pb2.LinkResourcesRequest(
            sessionId=self.session, link=self.make_link(folder, self.r1).toLink().toGrpc()))

        res_change = depi_pb2.ResourceChange(
            URL=known[1].URL,
            name=known[1].name,
            id=known[1].id,
            new_URL=known[1].URL,
            new_name=known[1].name,
            new_id=known[1].id,
            changeType=depi_pb2.ChangeType.Removed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=known[0].toolId,
            URL=known[0].URL,
            name=known[0].name,
            version=known[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change
            )
        )
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session, includeDeleted=True)):
            if link.resourceLink.fromRes.toolId == known[0].toolId and \
                    link.resourceLink.fromRes.resourceGroupURL == known[0].URL and \
                    link.resourceLink.fromRes.URL == known[1].URL:
                self.assertTrue(link.resourceLink.dirty, "Link should be marked dirty as a result deleting the from resource")
                self.assertTrue(link.resourceLink.deleted, "Link should be deleted if the from resource is deleted")
                found = True
        self.assertTrue(found, "Link should should be marked deleted and dirty, but not physically deleted")

        req = depi_pb2.GetResourcesRequest(sessionId=self.session,
                                           patterns=[
                                               depi_pb2.ResourceRefPattern(toolId=known[0].toolId, resourceGroupURL=known[0].URL,
                                                                           URLPattern=known[1].URL)
                                           ], includeDeleted=True)
        resp = self.depi.GetResources(req)
        self.assertTrue(resp.ok, "GetResources should succeed")
        found = False
        for res in resp.resources:
            if res.toolId == known[0].toolId and res.resourceGroupURL == known[0].URL and \
                res.URL == known[1].URL:
                found = True
                self.assertTrue(res.deleted, "Res should be marked as deleted")
        self.assertTrue(found, "Res should still appear in branch")

        req = depi_pb2.MarkLinksCleanRequest(
            sessionId=self.session,
            links=[known_link.toLink().toGrpc()],
            propagateCleanliness=True
        )

        resp = self.depi.MarkLinksClean(req)
        self.assertTrue(resp.ok, "mark link as clean should succeed")

        found = False
        for link in self.depi.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session)):
            if link.resourceLink.fromRes.toolId == known[0].toolId and \
                    link.resourceLink.fromRes.resourceGroupURL == known[0].URL and \
                    link.resourceLink.fromRes.URL == known[1].URL:
                found = True

        self.assertFalse(found, "Link should have been deleted after being marked clean")

        req = depi_pb2.GetResourcesRequest(sessionId=self.session,
                                           patterns=[
                                               depi_pb2.ResourceRefPattern(toolId=known[0].toolId, resourceGroupURL=known[0].URL,
                                                                           URLPattern=known[1].URL)
                                           ], includeDeleted=True)
        resp = self.depi.GetResources(req)
        self.assertTrue(resp.ok, "GetResources should succeed")
        found = False
        for res in resp.resources:
            if res.toolId == known[0].toolId and res.resourceGroupURL == known[0].URL and \
                    res.URL == known[1].URL:
                found = True
        self.assertFalse(found, "Res should be deleted after link marked clean")

    def test_get_dirty_links_after_modify(self):
        self.login()
        self.make_data_model()

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))

        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r3[0].toolId,
            name = self.r3[0].name,
            URL = self.r3[0].URL,
            withInferred=False
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed with "+resp.msg)

        self.assertEqual(len(resp.links), 1, "There should only be one dirty link")
        self.assertEqual(resp.links[0].fromRes.URL, self.r2[1].URL, "From res should be from r2")
        self.assertEqual(resp.links[0].toRes.URL, self.r3[1].URL, "To res should be to r3")

    def test_get_dirty_links_after_delete(self):
        self.login()
        self.make_data_model()

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Removed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()
        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r3[0].toolId,
            name = self.r3[0].name,
            URL = self.r3[0].URL,
            withInferred=False
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed with "+resp.msg)

        self.assertEqual(len(resp.links), 0, "There should be no dirty links")
    def test_get_dirty_links_with_inf_after_modify(self):
        self.login()
        self.make_data_model()

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()

        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r4[0].toolId,
            name = self.r4[0].name,
            URL = self.r4[0].URL,
            withInferred=True
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed with "+resp.msg)

        self.assertEqual(len(resp.links), 2, "There should be two dirty links")
        self.assertFalse(resp.links[0].dirty, "The link itself should not be dirty, only the inferred")
        self.assertNotEqual(len(resp.links[0].inferredDirtiness), 0, "The inferred dirtiness for the link should not be empty")
        self.assertFalse(resp.links[1].dirty, "The link itself should not be dirty, only the inferred")
        self.assertNotEqual(len(resp.links[1].inferredDirtiness), 0, "The inferred dirtiness for the link should not be empty")

    def test_get_dirty_links_as_stream_with_inf_after_modify(self):
        self.login()
        self.make_data_model()

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        self.reSetUp()

        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r4[0].toolId,
            name = self.r4[0].name,
            URL = self.r4[0].URL,
            withInferred=True
        )

        links = []
        for link in self.depi.GetDirtyLinksAsStream(req):
            self.assertTrue(link.ok, link.msg)
            links.append(link)
        self.assertTrue(resp.ok, "GetDirtyLinks failed with "+resp.msg)

        self.assertEqual(len(links), 2, "There should be two dirty links")
        self.assertFalse(links[0].link.dirty, "The link itself should not be dirty, only the inferred")
        self.assertNotEqual(len(links[0].link.inferredDirtiness), 0, "The inferred dirtiness for the link should not be empty")
        self.assertFalse(links[1].link.dirty, "The link itself should not be dirty, only the inferred")
        self.assertNotEqual(len(links[1].link.inferredDirtiness), 0, "The inferred dirtiness for the link should not be empty")

    def test_mark_links_clean(self):
        self.login()
        self.make_data_model()

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        from_rr = depi_pb2.ResourceRef(
            toolId = self.r2[0].toolId,
            resourceGroupURL=self.r2[0].URL,
            URL=self.r2[1].URL
        )

        to_rr = depi_pb2.ResourceRef(
            toolId = self.r3[0].toolId,
            resourceGroupURL=self.r3[0].URL,
            URL=self.r3[1].URL
        )
        link = depi_pb2.ResourceLinkRef( fromRes=from_rr, toRes=to_rr )

        depiUpdates = self.depi.WatchDepi(
            depi_pb2.WatchDepiRequest(sessionId=self.session))

        req = depi_pb2.MarkLinksCleanRequest(
            sessionId=self.session,
            links=[link],
            propagateCleanliness=True
        )

        resp = self.depi.MarkLinksClean(req)
        self.assertTrue(resp.ok, "MarkLinksClean failed: "+resp.msg)

        notification = next(depiUpdates)
        self.assertEqual(depi_pb2.UpdateType.MarkLinkClean, notification.updates[0].updateType)

        self.reSetUp()
        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r3[0].toolId,
            name = self.r3[0].name,
            URL = self.r3[0].URL,
            withInferred=True
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed: "+resp.msg)

        self.assertEqual(len(resp.links), 0, "There should be no dirty links for r3")

        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r4[0].toolId,
            name = self.r4[0].name,
            URL = self.r4[0].URL,
            withInferred=True
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed: "+resp.msg)

        self.assertEqual(len(resp.links), 0, "There should be no dirty links for r4")

        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r5[0].toolId,
            name = self.r5[0].name,
            URL = self.r5[0].URL,
            withInferred=True
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed: "+resp.msg)

        self.assertEqual(len(resp.links), 0, "There should be no dirty links for r5")

    def test_mark_links_clean_no_prop(self):
        self.login()
        self.make_data_model()

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        from_rr = depi_pb2.ResourceRef(
            toolId = self.r2[0].toolId,
            resourceGroupURL=self.r2[0].URL,
            URL=self.r2[1].URL
        )

        to_rr = depi_pb2.ResourceRef(
            toolId = self.r3[0].toolId,
            resourceGroupURL=self.r3[0].URL,
            URL=self.r3[1].URL
        )
        link = depi_pb2.ResourceLinkRef( fromRes=from_rr, toRes=to_rr )

        req = depi_pb2.MarkLinksCleanRequest(
            sessionId=self.session,
            links=[link],
            propagateCleanliness=False
        )

        resp = self.depi.MarkLinksClean(req)
        self.assertTrue(resp.ok, "MarkLinksClean failed: "+resp.msg)

        self.reSetUp()
        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r3[0].toolId,
            name = self.r3[0].name,
            URL = self.r3[0].URL,
            withInferred=True
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed: "+resp.msg)

        self.assertEqual(len(resp.links), 0, "There should be no dirty links for r3")

        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId = self.r4[0].toolId,
            name = self.r4[0].name,
            URL = self.r4[0].URL,
            withInferred=True
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed: "+resp.msg)

        self.assertEqual(len(resp.links), 2, "There should be two inferred dirty links for r4")

    def test_mark_inf_clean_watch(self):
        self.login()
        self.make_data_model()

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        from_rr = depi_pb2.ResourceRef(
            toolId=self.r3[0].toolId,
            resourceGroupURL=self.r3[0].URL,
            URL=self.r3[1].URL
        )

        to_rr = depi_pb2.ResourceRef(
            toolId=self.r4[0].toolId,
            resourceGroupURL=self.r4[0].URL,
            URL=self.r4[1].URL
        )
        link = depi_pb2.ResourceLinkRef(fromRes=from_rr, toRes=to_rr)

        source = depi_pb2.ResourceRef(
            toolId=self.r2[0].toolId,
            resourceGroupURL=self.r2[0].URL,
            URL=self.r2[1].URL
        )

        depiUpdates = self.depi.WatchDepi(
            depi_pb2.WatchDepiRequest(sessionId=self.session))

        req = depi_pb2.MarkInferredDirtinessCleanRequest(
            sessionId=self.session,
            link=link,
            dirtinessSource=source,
            propagateCleanliness=False)

        resp = self.depi.MarkInferredDirtinessClean(req)
        self.assertTrue(resp.ok, "MarkInferredDirtinessClean failed: " + resp.msg)

        notification = next(depiUpdates)
        self.assertEqual(depi_pb2.UpdateType.MarkInferredLinkClean, notification.updates[0].updateType)

        self.reSetUp()
        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId=self.r4[0].toolId,
            name=self.r4[0].name,
            URL=self.r4[0].URL,
            withInferred=True
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed: " + resp.msg)

        self.assertEqual(1, len(resp.links), "There should be one inferred dirty links for r4")


    def test_mark_inf_clean(self):
        self.login()
        self.make_data_model()

        res_change = depi_pb2.ResourceChange(
            URL=self.r2[1].URL,
            name=self.r2[1].name,
            id=self.r2[1].id,
            new_URL=self.r2[1].URL,
            new_name=self.r2[1].name,
            new_id=self.r2[1].id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=self.r2[0].toolId,
            URL=self.r2[0].URL,
            name=self.r2[0].name,
            version=self.r2[0].version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        from_rr = depi_pb2.ResourceRef(
            toolId=self.r3[0].toolId,
            resourceGroupURL=self.r3[0].URL,
            URL=self.r3[1].URL
        )

        to_rr = depi_pb2.ResourceRef(
            toolId=self.r4[0].toolId,
            resourceGroupURL=self.r4[0].URL,
            URL=self.r4[1].URL
        )
        link = depi_pb2.ResourceLinkRef(fromRes=from_rr, toRes=to_rr)

        source = depi_pb2.ResourceRef(
            toolId=self.r2[0].toolId,
            resourceGroupURL=self.r2[0].URL,
            URL=self.r2[1].URL
        )

        req = depi_pb2.MarkInferredDirtinessCleanRequest(
            sessionId=self.session,
            link=link,
            dirtinessSource=source,
            propagateCleanliness=False)

        resp = self.depi.MarkInferredDirtinessClean(req)
        self.assertTrue(resp.ok, "MarkInferredDirtinessClean failed: " + resp.msg)

        self.reSetUp()
        req = depi_pb2.GetDirtyLinksRequest(
            sessionId=self.session,
            toolId=self.r4[0].toolId,
            name=self.r4[0].name,
            URL=self.r4[0].URL,
            withInferred=True
        )

        resp = self.depi.GetDirtyLinks(req)
        self.assertTrue(resp.ok, "GetDirtyLinks failed: " + resp.msg)

        self.assertEqual(1, len(resp.links), "There should be one inferred dirty links for r4")

    def test_get_dependency_chain_default_order(self):
        self.login()
        self.make_data_model()

        resource_ref = depi_pb2.ResourceRef(
            toolId=self.r1[0].toolId,
            resourceGroupURL=self.r1[0].URL,
            URL=self.r1[1].URL
        )

        req = depi_pb2.GetDependencyGraphRequest(
            sessionId=self.session,
            resource=resource_ref,
            dependenciesType=depi_pb2.DependenciesType.Dependants
        )

        resp = self.depi.GetDependencyGraph(req)
        self.assertTrue(resp.ok, "GetDependencyGraph failed: " + resp.msg)

        self.assertIsNotNone(resp.resource)
        # Check it's not empty and grab a rg prop so it's not just the refdata
        self.assertEqual(resp.resource.name, 'resource1')
        self.assertEqual(resp.resource.resourceGroupVersion, '000000')

        self.assertEqual(4, len(resp.links))

    def test_get_dependency_chain_default_order_depth1(self):
        self.login()
        self.make_data_model()

        resource_ref = depi_pb2.ResourceRef(
            toolId=self.r1[0].toolId,
            resourceGroupURL=self.r1[0].URL,
            URL=self.r1[1].URL
        )

        req = depi_pb2.GetDependencyGraphRequest(
            sessionId=self.session,
            resource=resource_ref,
            dependenciesType=depi_pb2.DependenciesType.Dependants,
            maxDepth=1
        )

        resp = self.depi.GetDependencyGraph(req)
        self.assertTrue(resp.ok, "GetDependencyGraph failed: " + resp.msg)

        self.assertIsNotNone(resp.resource)
        # Check it's not empty and grab a rg prop so it's not just the refdata
        self.assertEqual(resp.resource.name, 'resource1')
        self.assertEqual(resp.resource.resourceGroupVersion, '000000')

        self.assertEqual(1, len(resp.links))

    def test_get_dependency_chain_reverse_order(self):
        self.login()
        self.make_data_model()

        resource_ref = depi_pb2.ResourceRef(
            toolId=self.r5[0].toolId,
            resourceGroupURL=self.r5[0].URL,
            URL=self.r5[1].URL
        )

        req = depi_pb2.GetDependencyGraphRequest(
            sessionId=self.session,
            resource=resource_ref,
            dependenciesType=depi_pb2.DependenciesType.Dependencies
        )

        resp = self.depi.GetDependencyGraph(req)
        self.assertTrue(resp.ok, "GetDependencyGraph failed: " + resp.msg)

        self.assertIsNotNone(resp.resource)

        self.assertEqual(4, len(resp.links))

    def test_get_dependency_chain_reverse_order_depth1(self):
        self.login()
        self.make_data_model()

        resource_ref = depi_pb2.ResourceRef(
            toolId=self.r5[0].toolId,
            resourceGroupURL=self.r5[0].URL,
            URL=self.r5[1].URL
        )

        req = depi_pb2.GetDependencyGraphRequest(
            sessionId=self.session,
            resource=resource_ref,
            dependenciesType=depi_pb2.DependenciesType.Dependencies,
            maxDepth=1
        )

        resp = self.depi.GetDependencyGraph(req)
        self.assertTrue(resp.ok, "GetDependencyGraph failed: " + resp.msg)

        self.assertIsNotNone(resp.resource)

        self.assertEqual(1, len(resp.links))

    def test_get_dependency_chain_error_if_no_resource(self):
        self.login()
        self.make_data_model()

        resource_ref = depi_pb2.ResourceRef(
            toolId='git',
            resourceGroupURL='resourcegroup1',
            URL='farouk'
        )

        req = depi_pb2.GetDependencyGraphRequest(
            sessionId=self.session,
            resource=resource_ref,
            dependenciesType=depi_pb2.DependenciesType.Dependencies
        )

        resp = self.depi.GetDependencyGraph(req)
        self.assertFalse(resp.ok, "GetDependencyGraph should have failed: " + resp.msg)
        self.assertEqual(resp.msg.lower(), "parent resource not found")

    def test_blackboard_add(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')
        (rg3, r3) = self.make_resource('git', 'resourcegroup1', 'resource3', '000000')
        (rg4, r4) = self.make_resource('git', 'resourcegroup2', 'resource4', '123456')
        (rg5, r5) = self.make_resource('git', 'resourcegroup2', 'resource5', '123456')


        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource,
                    "Notification should contain added resource")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        found = False
        for res in resp.resources:
            if res.toolId == addResource.toolId and \
                res.resourceGroupURL == addResource.resourceGroupURL and \
                res.URL == addResource.URL:
                found = True

        self.assertTrue(found, "Resource should be in the blackboard")

        addResource2 = r2.toGrpc(rg2)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))

        addResource3 = r3.toGrpc(rg3)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))


        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource2,
                         "Notification should contain added resource")

        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource3,
                         "Notification should contain added resource")


    def test_blackboard_remove(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')

        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource,
                         "Notification should contain added resource")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        found = False
        for res in resp.resources:
            if res == addResource:
                found = True

        self.assertTrue(found, "Resource should be in the blackboard")

        self.depi.RemoveResourcesFromBlackboard(
            depi_pb2.RemoveResourcesFromBlackboardRequest(
                sessionId=self.session,
                resourceRefs=[ResourceRef.fromResourceGroupAndRes(rg1, r1).toGrpc()]))

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        found = False
        for res in resp.resources:
            if res == addResource:
                found = True

        self.assertFalse(found, "Resource should not be in the blackboard")

    def test_blackboard_add_link(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')


        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        addResource = r1.toGrpc(rg1)
        addResource2 = r2.toGrpc(rg2)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource, addResource2]))

        self.depi.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=self.session,
                links=[Link(ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg1.URL, url=r1.URL),
                            ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg2.URL, url=r2.URL)).toGrpc()]
            ))
        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource,
                         "Notification should contain added resource")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        found = False
        for res in resp.resources:
            if res == addResource:
                found = True

        self.assertTrue(found, "Resource should be in the blackboard")

    def test_blackboard_clear(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')
        (rg3, r3) = self.make_resource('git', 'resourcegroup1', 'resource3', '000000')
        (rg4, r4) = self.make_resource('git', 'resourcegroup2', 'resource4', '123456')
        (rg5, r5) = self.make_resource('git', 'resourcegroup2', 'resource5', '123456')


        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource,
                         "Notification should contain added resource")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        found = False
        for res in resp.resources:
            if res == addResource:
                found = True

        self.assertTrue(found, "Resource should be in the blackboard")

        addResource2 = r2.toGrpc(rg2)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))

        addResource3 = r3.toGrpc(rg3)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))


        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource2,
                         "Notification should contain added resource")

        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource3,
                         "Notification should contain added resource")

        self.depi.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=self.session,
                links=[Link(ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg1.URL, url=r1.URL),
                            ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg2.URL, url=r2.URL)).toGrpc()]
            ))

        self.depi.ClearBlackboard(
            depi_pb2.ClearBlackboardRequest(
                sessionId=self.session))

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.assertEqual(len(resp.resources), 0, "There should be no resources in the blackboard")
        self.assertEqual(len(resp.links), 0, "There should be no links in the blackboard")

    def test_blackboard_save(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')
        (rg3, r3) = self.make_resource('git', 'resourcegroup1', 'resource3', '000000')
        (rg4, r4) = self.make_resource('git', 'resourcegroup2', 'resource4', '123456')
        (rg5, r5) = self.make_resource('git', 'resourcegroup2', 'resource5', '123456')


        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource,
                         "Notification should contain added resource")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        found = False
        for res in resp.resources:
            if res == addResource:
                found = True

        self.assertTrue(found, "Resource should be in the blackboard")

        addResource2 = r2.toGrpc(rg2)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))

        addResource3 = r3.toGrpc(rg3)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))


        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource2,
                         "Notification should contain added resource")

        notification = next(blackboardUpdates)
        self.assertEqual(notification.updates[0].resource, addResource3,
                         "Notification should contain added resource")

        self.depi.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=self.session,
                links=[Link(ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg1.URL, url=r1.URL),
                            ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg2.URL, url=r2.URL)).toGrpc()]
            ))


        self.depi.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(
                sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.reSetUp()

        self.depi.ClearBlackboard(
            depi_pb2.ClearBlackboardRequest(
                sessionId=self.session))

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.assertEqual(len(resp.resources), 0, "There should be no resources in the blackboard")
        self.assertEqual(len(resp.links), 0, "There should be no links in the blackboard")

    def test_blackboard_verify_removed(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')
        (rg3, r3) = self.make_resource('git', 'resourcegroup1', 'resource3', '000000')
        (rg4, r4) = self.make_resource('git', 'resourcegroup2', 'resource4', '123456')
        (rg5, r5) = self.make_resource('git', 'resourcegroup2', 'resource5', '123456')


        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        addResource2 = r2.toGrpc(rg2)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))

        addResource3 = r3.toGrpc(rg3)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))

        resp = self.depi.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(
                sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))

        res_change = depi_pb2.ResourceChange(
            URL=r1.URL,
            name=r1.name,
            id=r1.id,
            new_URL=r1.URL,
            new_name=r1.name,
            new_id=r1.id,
            changeType=depi_pb2.ChangeType.Removed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=rg1.toolId,
            URL=rg1.URL,
            name=rg1.name,
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        notification = next(blackboardUpdates)
        self.assertEqual(2, len(notification.updates), "There should be two updates in the notification")
        self.assertEqual(notification.updates[0].updateType, depi_pb2.UpdateType.ResourceGroupVersionChanged,
                         "There should be a blackboard update about the RG version change")
        self.assertEqual(notification.updates[1].updateType, depi_pb2.UpdateType.RemoveResource,
                         "There should be a blackboard update about the resource being removed")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)
        for res in resp.resources:
            rg = ResourceGroup.fromGrpcResource(res)
            r = Resource.fromGrpcResource(res)
            if rg == rg1:
                self.assertNotEqual(r, r1, "Resource1 should no longer be in the blackboard")

    def test_blackboard_verify_rename(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')
        (rg3, r3) = self.make_resource('git', 'resourcegroup1', 'resource3', '000000')
        (rg4, r4) = self.make_resource('git', 'resourcegroup2', 'resource4', '123456')
        (rg5, r5) = self.make_resource('git', 'resourcegroup2', 'resource5', '123456')


        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        addResource2 = r2.toGrpc(rg2)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))

        addResource3 = r3.toGrpc(rg3)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))

        resp = self.depi.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(
                sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))

        (rg1rn, r1rn) = self.make_resource('git', 'resourcegroup1', 'resource1rn', '111112')

        res_change = depi_pb2.ResourceChange(
            URL=r1.URL,
            name=r1.name,
            id=r1.id,
            new_URL=r1rn.URL,
            new_name=r1rn.name,
            new_id=r1rn.id,
            changeType=depi_pb2.ChangeType.Renamed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=rg1.toolId,
            URL=rg1.URL,
            name=rg1.name,
            version=rg1rn.version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        notification = next(blackboardUpdates)
        self.assertEqual(2, len(notification.updates), "There should be two updates in the notification")
        self.assertEqual(notification.updates[0].updateType, depi_pb2.UpdateType.ResourceGroupVersionChanged,
                         "There should be a blackboard update about the RG version change")
        self.assertEqual(notification.updates[1].updateType, depi_pb2.UpdateType.RenameResource,
                         "There should be a blackboard update about the resource being removed")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)
        found = False
        foundOld = False
        for res in resp.resources:
            rg = ResourceGroup.fromGrpcResource(res)
            r = Resource.fromGrpcResource(res)
            if rg == rg1 and r == r1rn:
                found = True
            if rg == rg1 and r == r1:
                foundOld = True
        self.assertTrue(found, "Renamed resource should be in blackboard")
        self.assertFalse(foundOld, "Old resource name should no longer be present")

    def test_blackboard_verify_modify(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')
        (rg3, r3) = self.make_resource('git', 'resourcegroup1', 'resource3', '000000')
        (rg4, r4) = self.make_resource('git', 'resourcegroup2', 'resource4', '123456')
        (rg5, r5) = self.make_resource('git', 'resourcegroup2', 'resource5', '123456')


        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        addResource2 = r2.toGrpc(rg2)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))

        addResource3 = r3.toGrpc(rg3)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))

        resp = self.depi.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(
                sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))

        res_change = depi_pb2.ResourceChange(
            URL=r1.URL,
            name=r1.name,
            id=r1.id,
            new_URL=r1.URL,
            new_name=r1.name,
            new_id=r1.id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=rg1.toolId,
            URL=rg1.URL,
            name=rg1.name,
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        notification = next(blackboardUpdates)
        self.assertGreaterEqual(len(notification.updates), 1, "There should be at least one update in the notification")
        self.assertEqual(notification.updates[0].updateType, depi_pb2.UpdateType.ResourceGroupVersionChanged,
                         "There should be a blackboard update about the RG version change")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)
        found = False
        for res in resp.resources:
            rg = ResourceGroup.fromGrpcResource(res)
            r = Resource.fromGrpcResource(res)
            if rg == rg1 and r == r1:
                self.assertEqual("111112", rg.version, "Resource group version should be updated")
                found = True
        self.assertTrue(found, "Modified resource should be in blackboard")

    def test_blackboard_verify_modify_rename(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')
        (rg3, r3) = self.make_resource('git', 'resourcegroup1', 'resource3', '000000')
        (rg4, r4) = self.make_resource('git', 'resourcegroup2', 'resource4', '123456')
        (rg5, r5) = self.make_resource('git', 'resourcegroup2', 'resource5', '123456')


        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        addResource2 = r2.toGrpc(rg2)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))

        addResource3 = r3.toGrpc(rg3)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))

        resp = self.depi.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(
                sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource3]))

        (rg1rn, r1rn) = self.make_resource('git', 'resourcegroup1', 'resource1rn', '111112')

        res_change = depi_pb2.ResourceChange(
            URL=r1.URL,
            name=r1.name,
            id=r1.id,
            new_URL=r1rn.URL,
            new_name=r1rn.name,
            new_id=r1rn.id,
            changeType=depi_pb2.ChangeType.Modified
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=rg1.toolId,
            URL=rg1.URL,
            name=rg1.name,
            version=rg1rn.version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        notification = next(blackboardUpdates)
        self.assertEqual(2, len(notification.updates), "There should be two updates in the notification")
        self.assertEqual(notification.updates[0].updateType, depi_pb2.UpdateType.ResourceGroupVersionChanged,
                         "There should be a blackboard update about the RG version change")
        self.assertEqual(notification.updates[1].updateType, depi_pb2.UpdateType.RenameResource,
                         "There should be a blackboard update about the resource being removed")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)
        found = False
        foundOld = False
        for res in resp.resources:
            rg = ResourceGroup.fromGrpcResource(res)
            r = Resource.fromGrpcResource(res)
            if rg == rg1 and r == r1rn:
                found = True
            if rg == rg1 and r == r1:
                foundOld = True
        self.assertTrue(found, "Renamed resource should be in blackboard")
        self.assertFalse(foundOld, "Old resource name should no longer be present")

    def test_blackboard_verify_rename_link(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')


        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        addResource2 = r2.toGrpc(rg2)

        self.depi.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=self.session,
                links=[Link(ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg1.URL, url=r1.URL),
                            ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg2.URL, url=r2.URL)).toGrpc()]
            ))

        resp = self.depi.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(
                sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))
        self.depi.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=self.session,
                links=[Link(ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg1.URL, url=r1.URL),
                            ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg2.URL, url=r2.URL)).toGrpc()]
            ))

        (rg1rn, r1rn) = self.make_resource('git', 'resourcegroup1', 'resource1rn', '111112')

        res_change = depi_pb2.ResourceChange(
            URL=r1.URL,
            name=r1.name,
            id=r1.id,
            new_URL=r1rn.URL,
            new_name=r1rn.name,
            new_id=r1rn.id,
            changeType=depi_pb2.ChangeType.Renamed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=rg1.toolId,
            URL=rg1.URL,
            name=rg1.name,
            version=rg1rn.version,
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        notification = next(blackboardUpdates)
        self.assertEqual(3, len(notification.updates), "There should be two updates in the notification")
        self.assertEqual(notification.updates[0].updateType, depi_pb2.UpdateType.ResourceGroupVersionChanged,
                         "There should be a blackboard update about the RG version change")
        self.assertEqual(notification.updates[1].updateType, depi_pb2.UpdateType.RenameLink,
                         "There should be a blackboard update about the link being renamed")
        self.assertEqual(notification.updates[2].updateType, depi_pb2.UpdateType.RenameResource,
                         "There should be a blackboard update about the resource being removed")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)
        found = False
        foundOld = False
        for res in resp.resources:
            rg = ResourceGroup.fromGrpcResource(res)
            r = Resource.fromGrpcResource(res)
            if rg == rg1 and r == r1rn:
                found = True
            if rg == rg1 and r == r1:
                foundOld = True
        self.assertTrue(found, "Renamed resource should be in blackboard")
        self.assertFalse(foundOld, "Old resource name should no longer be present")

    def test_blackboard_verify_delete_link(self):
        self.login()

        (rg1, r1) = self.make_resource('git', 'resourcegroup1', 'resource1', '000000')
        (rg2, r2) = self.make_resource('git', 'resourcegroup1', 'resource2', '000000')


        addResource = r1.toGrpc(rg1)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))

        addResource2 = r2.toGrpc(rg2)

        self.depi.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=self.session,
                links=[Link(ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg1.URL, url=r1.URL),
                            ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg2.URL, url=r2.URL)).toGrpc()]
            ))

        resp = self.depi.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(
                sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)

        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource]))
        self.depi.AddResourcesToBlackboard(
            depi_pb2.AddResourcesToBlackboardRequest(
                sessionId=self.session,
                resources=[addResource2]))
        self.depi.LinkBlackboardResources(
            depi_pb2.LinkBlackboardResourcesRequest(
                sessionId=self.session,
                links=[Link(ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg1.URL, url=r1.URL),
                            ResourceRef(toolId=rg1.toolId, resourceGroupURL=rg2.URL, url=r2.URL)).toGrpc()]
            ))

        res_change = depi_pb2.ResourceChange(
            URL=r1.URL,
            name=r1.name,
            id=r1.id,
            new_URL=r1.URL,
            new_name=r1.name,
            new_id=r1.id,
            changeType=depi_pb2.ChangeType.Removed
        )
        rg_change = depi_pb2.ResourceGroupChange(
            toolId=rg1.toolId,
            URL=rg1.URL,
            name=rg1.name,
            version="111112",
            resources=[res_change]
        )

        resp = self.depi.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(
                sessionId=self.session,
                resourceGroup=rg_change))
        self.assertTrue(resp.ok, "UpdateResourceGroup should succeed")

        blackboardUpdates = self.depi.WatchBlackboard(
            depi_pb2.WatchBlackboardRequest(sessionId=self.session))

        notification = next(blackboardUpdates)
        self.assertEqual(3, len(notification.updates), "There should be two updates in the notification")
        self.assertEqual(notification.updates[0].updateType, depi_pb2.UpdateType.ResourceGroupVersionChanged,
                         "There should be a blackboard update about the RG version change")
        self.assertEqual(notification.updates[1].updateType, depi_pb2.UpdateType.RemoveResource,
                         "There should be a blackboard update about the resource being removed")
        self.assertEqual(notification.updates[2].updateType, depi_pb2.UpdateType.RemoveLink,
                         "There should be a blackboard update about the link being renamed")

        resp = self.depi.GetBlackboardResources(
            depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))

        self.assertTrue(resp.ok, resp.msg)
        found = False
        for res in resp.resources:
            rg = ResourceGroup.fromGrpcResource(res)
            r = Resource.fromGrpcResource(res)
            if rg == rg1 and r == r1:
                found = True
        self.assertFalse(found, "Deleted resource should not be in blackboard")

        found = False
        for link in resp.links:
            if link.fromRes.toolId == rg1.toolId and \
               link.fromRes.resourceGroupURL == rg1.URL and \
               link.fromRes.URL == r1.URL:
                found = True
            elif link.toRes.toolId == rg1.toolId and \
                    link.toRes.resourceGroupURL == rg1.URL and \
                    link.toRes.URL == r1.URL:
                found = True
        self.assertFalse(found, "Links with deleted resource should be removed from blackboard")


