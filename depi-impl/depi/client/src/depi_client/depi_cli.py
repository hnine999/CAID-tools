import argparse
import cmd
import json
import os
import re
import string
import traceback
from threading import Thread

import grpc

import depi_pb2
import depi_pb2_grpc


def cmdloop(self, intro=None):
    """Repeatedly issue a prompt, accept input, parse an initial prefix
    off the received input, and dispatch to action methods, passing them
    the remainder of the line as argument.

    """

    self.preloop()
    if self.use_rawinput and self.completekey:
        try:
            import readline
            self.old_completer = readline.get_completer()
            readline.set_completer(self.complete)
            readline.set_completer_delims(" ")
            readline.parse_and_bind(self.completekey + ": menu-complete")
        except ImportError:
            pass
    try:
        if intro is not None:
            self.intro = intro
        if self.intro:
            self.stdout.write(str(self.intro) + "\n")
        stop = None
        while not stop:
            if self.cmdqueue:
                line = self.cmdqueue.pop(0)
            else:
                if self.use_rawinput:
                    try:
                        line = input(self.prompt)
                    except EOFError:
                        line = 'EOF'
                else:
                    self.stdout.write(self.prompt)
                    self.stdout.flush()
                    line = self.stdin.readline()
                    if not len(line):
                        line = 'EOF'
                    else:
                        line = line.rstrip('\r\n')
            line = self.precmd(line)
            stop = self.onecmd(line)
            stop = self.postcmd(stop, line)
        self.postloop()
    finally:
        if self.use_rawinput and self.completekey:
            try:
                import readline
                readline.set_completer(self.old_completer)
            except ImportError:
                pass

cmd.IDENTCHARS = string.ascii_letters + string.digits + string.punctuation
cmd.Cmd.cmdloop = cmdloop

class DepiCli(cmd.Cmd):
    intro = 'Depi Command-line. Type help or ? to list commands.\n'
    prompt = 'Depi> '
    file = None

    def __init__(self, stub, session, token, addViaUpdate):
        super().__init__()
        self.stub = stub
        self.session = session
        self.token = token
        self.watchingDepi = False
        self.addViaUpdate = addViaUpdate
        self.blackboard = False

    def print_resource(self, res: depi_pb2.Resource):
        print("{} {} {}".format(res.toolId, res.resourceGroupURL, res.URL))

    def print_link(self, link: depi_pb2.ResourceLink):
        print("{} {} {} <- {} {} {}    dirty: {}  last clean: {}".format(
            link.fromRes.toolId, link.fromRes.resourceGroupURL, link.fromRes.URL,
            link.toRes.toolId, link.toRes.resourceGroupURL, link.toRes.URL,
            link.dirty, link.lastCleanVersion))
        if len(link.inferredDirtiness) > 0:
            print("  Inferred dirtiness from:")
            for inf in link.inferredDirtiness:
                print("    {} {} {}  last clean: {}".format(
                    inf.resource.toolId, inf.resource.resourceGroupURL, inf.resource.URL,
                    inf.lastCleanVersion))
        print("-----------------------------------------")

    @staticmethod
    def escape_re(pattern):
        if pattern == ".*":
            return pattern
        else:
            return re.escape(pattern)

    def do_branches(self, arg):
        'Show a list of all the branches'
        response = self.stub.GetBranchList(
            depi_pb2.GetBranchListRequest(sessionId=self.session))
        if not response.ok:
            print("Error fetching branches: {}".format(response.msg))
            return

        print("Branches:")
        for branch in response.branches:
            print(branch)

    def do_ping(self, arg):
        response = self.stub.Ping(depi_pb2.PingRequest(sessionId=self.session))
        if not response.ok:
            print("Ping failed")
        else:
            print("Ping succeeded, login token is: {}".format(response.loginToken))
    def do_blackboard(self, arg):
        if arg.lower() == "true" or arg.lower() == "y" or arg.lower() == "yes" or arg.lower() == "enable":
            self.blackboard = True
            print("Blackboard enabled")
        elif arg.lower() == "false" or arg.lower() == "n" or arg.lower() == "no" or arg.lower() == "disable":
            self.blackboard = False
            print("Blackboard disabled")
        else:
            print("Please indicate y(es) or n(o) to enable/disable the blackboard")

    def do_save(self, arg):
        if not self.blackboard:
            print("The blackboard is not enable, there is nothing to save")
            return
        response = self.stub.SaveBlackboard(
            depi_pb2.SaveBlackboardRequest(sessionId=self.session))
        if not response.ok:
            print("Error saving blackboard: {}".format(response.msg))
        else:
            print("Blackboard saved.")

    def do_add(self, arg):
        """Add a resource or a resource group:
           add rg tool-id url name version
           add res tool-id rg-url url name id"""
        args = arg.split()
        if len(arg) < 1:
            print("Not enough arguments")
        if args[0] == 'rg' and len(args) >= 5:
            if self.blackboard:
                print("Resource groups are not added to the blackboard, only resources")
                return
            req = depi_pb2.AddResourceGroupRequest(sessionId=self.session,
                                                   resourceGroup=depi_pb2.ResourceGroup(
                                                       toolId=args[1],
                                                       URL=args[2],
                                                       name=args[3],
                                                       version=args[4]))
            resp = self.stub.AddResourceGroup(req)
            if not resp.ok:
                print("Error adding resource group: {}".format(resp.msg))
            else:
                print("Resource group added")
        elif args[0] == 'res' and len(args) >= 6:
            URL=args[3]
            if args[1] == "git" and not URL.startswith("/"):
                URL="/"+URL
            if self.blackboard:
                version = ""
                if len(args) > 6:
                    version = args[6]
                req = depi_pb2.AddResourcesToBlackboardRequest(sessionId=self.session,
                                                               resources= [
                                                                   depi_pb2.Resource(
                                                                       toolId=args[1],
                                                                       resourceGroupURL=args[2],
                                                                       URL=URL,
                                                                       name=args[4],
                                                                       id=args[5],
                                                                       resourceGroupVersion=version)
                                                               ])
                resp = self.stub.AddResourcesToBlackboard(req)
            else:
                if not self.addViaUpdate:
                    req = depi_pb2.AddResourceRequest(sessionId=self.session,
                                                      toolId=args[1],
                                                      resourceGroupURL=args[2],
                                                      URL=URL,
                                                      name=args[4],
                                                      id=args[5])
                    resp = self.stub.AddResource(req)
                else:
                    req = depi_pb2.UpdateDepiRequest(sessionId=self.session,
                                                     updates=[
                                                         depi_pb2.Update(updateType=depi_pb2.UpdateType.AddResource,
                                                                         resource=depi_pb2.Resource(toolId=args[1],
                                                                                                    resourceGroupURL=args[2],
                                                                                                    URL=URL,
                                                                                                    name=args[4],
                                                                                                    id=args[5]))
                                                     ])
                    resp = self.stub.UpdateDepi(req)
            if not resp.ok:
                print("Error adding resource: {}".format(resp.msg))
            else:
                print("Resource added")
        else:
            print("Invalid add command")

    def do_delete(self, arg):
        """delete a resource:
           delete res tool-id rg-url url"""
        args = arg.split()
        if len(arg) < 1:
            print("Not enough arguments")
#        if args[0] == 'rg' and len(args) >= 5:
#            if not resp.ok:
#                print("Error adding resource group: {}".format(resp.msg))
#            else:
#                print("Resource group added")
        if args[0] == 'res' and len(args) >= 4:
            URL=args[3]
            if args[1] == "git" and not URL.startswith("/"):
                URL="/"+URL
            if self.blackboard:
                req = depi_pb2.RemoveResourcesFromBlackboard(sessionId=self.session,
                                                             resources=[
                                                                depi_pb2.ResourceRef(toolId=args[1],
                                                                    resourceGroupURL=args[2],
                                                                    URL=URL)
                                                             ])
                resp = self.stub.RemoveResourcesFromBlackboard(req)
            else:
                req = depi_pb2.UpdateDepiRequest(sessionId=self.session,
                                                 updates=[
                                                     depi_pb2.Update(updateType=depi_pb2.UpdateType.RemoveResource,
                                                                     resource=depi_pb2.Resource(toolId=args[1],
                                                                                                resourceGroupURL=args[2],
                                                                                                URL=URL,
                                                                                                name="",
                                                                                                id=""))
                                                 ])
                resp = self.stub.UpdateDepi(req)
            if not resp.ok:
                print("Error adding resource: {}".format(resp.msg))
            else:
                print("Resource added")
        else:
            print("Invalid delete command")

    def do_run(self, arg):
        'Execute the commands in a file: run filename'
        if os.path.exists(arg):
            with open(arg) as file:
                for line in file:
                    line = line.strip()
                    if len(line) > 0 and not line.startswith('#'):
                        if self.onecmd(line):
                            print("Script execution terminated")
                            return
            print("Script execution complete")
        else:
            print("Unknown file: {}".format(arg))

    def do_dump(self, arg):
        'Dump the current depi branch to a Depi-CLI script that can recreate the depi: dump filename'
        with open(arg, 'w') as file:
            print("blackboard yes", file=file)
            patterns = []
            response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))
            if not response.ok:
                print("Error fetching resource groups: {}".format(response.msg))
                return

            for rg in response.resourceGroups:
                patterns.append((rg.toolId, rg.URL, ".*"))

            req_patterns = []
            for (tool_id, rg, res) in patterns:
                req_patterns.append(depi_pb2.ResourceRefPattern(toolId=tool_id, resourceGroupURL=rg, URLPattern=res))

            for res in self.stub.GetResourcesAsStream(depi_pb2.GetResourcesRequest(sessionId=self.session, patterns=req_patterns)):
                if not res.ok:
                    print("Error fetching resources: {}".format(res.msg))
                    return
                print("add res {} {} {} {} {} {}".format(res.resource.toolId, res.resource.resourceGroupURL,
                                                      res.resource.URL, res.resource.name, res.resource.id,
                                                         res.resource.resourceGroupVersion),
                      file=file)

            depiLinks = self.stub.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session))
            for link in depiLinks:
                print("link {} {} {} {} {} {}".format(link.resourceLink.fromRes.toolId,
                                                      link.resourceLink.fromRes.resourceGroupURL,
                                                      link.resourceLink.fromRes.URL,
                                                      link.resourceLink.toRes.toolId,
                                                      link.resourceLink.toRes.resourceGroupURL,
                                                      link.resourceLink.toRes.URL), file=file)
            print("save", file=file)
        print("Depi dumped to {}".format(arg))

    def do_tags(self, arg):
        'Show a list of all the tags'
        response = self.stub.GetBranchList(
            depi_pb2.GetBranchListRequest(sessionId=self.session))
        if not response.ok:
            print("Error fetching branches: {}".format(response.msg))
            return

        print("Tags:")
        for tag in response.tags:
            print(tag)

    def do_checkout(self, arg):
        'Check out a different branch:  checkout branch-name'
        response = self.stub.SetBranch(depi_pb2.SetBranchRequest(sessionId=self.session,
                                                                 branch=arg))
        if not response.ok:
            print("Error switching to the {} branch: {}".format(arg, response.msg))
            return
        print("Now using branch: {}".format(arg))

    def do_tag(self, arg):
        'Tag the current (or optionally another) branch:  tag tag-name [branch]'
        args = arg.split()
        fromBranch = ""
        if len(args) > 1:
            fromBranch = args[1]
        response = self.stub.CreateTag(
            depi_pb2.CreateTagRequest(sessionId=self.session,
                                      tagName=args[0],
                                      fromBranch=fromBranch)
        )
        branchName = fromBranch
        if branchName == "":
            branchName = "(current)"
        if not response.ok:
            print("Error tagging branch {} as {}: {}".format(branchName, args[0], response.msg))
            return
        print("Tagged branch {} as {}".format(branchName, args[0]))

    def do_branch(self, arg):
        'Display current branch (no args) or create a new branch from the current (or optionally a tag or another branch): branch new-name [branch-or-tag]'
        if len(arg) == 0:
            response = self.stub.CurrentBranch(depi_pb2.CurrentBranchRequest(sessionId=self.session))
            if not response.ok:
                print("Error fetching current branch: {}".format(response.msg))
                return
            print("The current branch is: {}".format(response.branch))
            return

        args = arg.split()
        fromBranch = ""
        if len(args) > 1:
            fromBranch = args[1]
        response = self.stub.CreateBranch(
            depi_pb2.CreateBranchRequest(sessionId=self.session,
                                         branchName=args[0],
                                         fromBranch=fromBranch)
        )
        branchName = fromBranch
        if branchName == "":
            branchName = "(current)"
        if not response.ok:
            print("Error creating branch {} from {}: {}".format(args[0], branchName, response.msg))


    def do_rg(self, arg):
        'Show a list of all the resource groups'
        response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))
        if not response.ok:
            print("Error fetching resource groups: {}".format(response.msg))
            return

        print("Resource Groups:")
        for rg in response.resourceGroups:
            print("{} {}   {} {}".format( rg.toolId, rg.URL, rg.name, rg.version))
        return

    def do_res(self, arg):
        'Show all resources matching a pattern (toolId resourceGroupURL (resourceURL or .*)'
        args = arg.split()
        patterns = []
        if len(args) < 1:
            response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))
            if not response.ok:
                print("Error fetching resource groups: {}".format(response.msg))
                return

            for rg in response.resourceGroups:
                patterns.append((rg.toolId, rg.URL, ".*"))
        elif len(args) < 2:
            response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))
            if not response.ok:
                print("Error fetching resource groups: {}".format(response.msg))
                return

            for rg in response.resourceGroups:
                if rg.toolId == args[0]:
                    patterns.append((rg.toolId, rg.URL, ".*"))
        elif len(args) < 3:
            patterns.append((args[0], args[1], ".*"))
        else:
            patterns.append((args[0], args[1], args[2]))

        req_patterns = []
        for (tool_id, rg, res) in patterns:
            req_patterns.append(depi_pb2.ResourceRefPattern(toolId=tool_id, resourceGroupURL=rg, URLPattern=res))

        print("Resources:")
        for res in self.stub.GetResourcesAsStream(depi_pb2.GetResourcesRequest(sessionId=self.session, patterns=req_patterns)):
            if not res.ok:
                print("Error fetching resources: {}".format(res.msg))
                return
            self.print_resource(res.resource)

    def do_links(self, arg):
        'List all the links matching the parts given, no args=all, otherwise from-toolId from-rg from-res to-toolId to-rg to-res'
        args = arg.split()
        response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))
        if not response.ok:
            print("Unable to fetch links: {}".format(response.msg))
            return

        if len(args) < 6:
            depiLinks = self.stub.GetAllLinksAsStream(depi_pb2.GetAllLinksAsStreamRequest(sessionId=self.session))

        if len(args) < 1:
            for link in depiLinks:
                if not link.ok:
                    print("Unable to fetch links: {}".format(link.msg))
                    return
                self.print_link(link.resourceLink)
        elif len(args) < 2:
            for link in depiLinks:
                if link.resourceLink.fromRes.toolId == args[0]:
                    self.print_link(link.resourceLink)
        elif len(args) < 3:
            for link in depiLinks:
                if link.resourceLink.fromRes.toolId == args[0] and link.resourceLink.fromRes.resourceGroupURL == args[1]:
                    self.print_link(link.resourceLink)
        elif len(args) < 4:
            pattern = re.compile(self.escape_re(args[2]))
            for link in depiLinks:
                if link.resourceLink.fromRes.toolId == args[0] and link.resourceLink.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.resourceLink.fromRes.URL) is not None:
                    self.print_link(link.resourceLink)
        elif len(args) < 5:
            pattern = re.compile(self.escape_re(args[2]))
            for link in depiLinks:
                if link.resourceLink.fromRes.toolId == args[0] and link.resourceLink.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.resourceLink.fromRes.URL) is not None and link.resourceLink.toRes.toolId == args[3]:
                    self.print_link(link.resourceLink)
        elif len(args) < 6:
            pattern = re.compile(self.escape_re(args[2]))
            for link in depiLinks:
                if link.resourceLink.fromRes.toolId == args[0] and link.resourceLink.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.resourceLink.fromRes.URL) is not None and link.resourceLink.toRes.toolId == args[3] and \
                        link.resourceLink.toRes.resourceGroupURL == args[4]:
                    self.print_link(link.resourceLink)
        else:

            depiLinks = self.stub.GetLinksAsStream(depi_pb2.GetLinksRequest(sessionId=self.session,
                                                                            patterns=[
                                                                                depi_pb2.ResourceLinkPattern(
                                                                                    fromRes=depi_pb2.ResourceRefPattern(
                                                                                        toolId=args[0],
                                                                                        resourceGroupURL=args[1],
                                                                                        URLPattern=args[2]),
                                                                                    toRes=depi_pb2.ResourceRefPattern(
                                                                                        toolId=args[3],
                                                                                        resourceGroupURL=args[4],
                                                                                        URLPattern=args[5]))]))
            for link in depiLinks:
                self.print_link(link.resourceLink)

    def do_link(self, arg):
        'Link two resources: link from-toolId from-rg from-res to-toolId to-rg to-res'
        args = arg.split()

        if len(args) != 6:
            print("Please supply complete from and to resources for the link")
            return

        if self.blackboard:
            req = depi_pb2.LinkBlackboardResourcesRequest(sessionId=self.session,
                                                          links=[
                                                              depi_pb2.ResourceLinkRef(
                                                                  fromRes=depi_pb2.ResourceRef(toolId=args[0],
                                                                                       resourceGroupURL=args[1],
                                                                                       URL=args[2]),
                                                                  toRes=depi_pb2.ResourceRef(toolId=args[3],
                                                                                       resourceGroupURL=args[4],
                                                                                       URL=args[5]))
                                                          ])
            resp = self.stub.LinkBlackboardResources(req)
        else:
            req = depi_pb2.LinkResourcesRequest(sessionId=self.session,
                                                link=depi_pb2.ResourceLinkRef(
                                                                  depi_pb2.ResourceRef(toolId=args[0],
                                                                                       resourceGroupURL=args[1],
                                                                                       URL=args[2]),
                                                                  depi_pb2.ResourceRef(toolId=args[3],
                                                                                       resourceGroupURL=args[4],
                                                                                       URL=args[5])))
            resp = self.stub.LinkResources(req)

        if not resp.ok:
            print("Error linking resources: {}".format(resp.msg))
            return

    def do_unlink(self, arg):
        'Unlink two resources: unlink from-toolId from-rg from-res to-toolId to-rg to-res'
        args = arg.split()

        if len(args) != 6:
            print("Please supply complete from and to resources for the link")
            return

        if self.blackboard:
            req = depi_pb2.UnlinkBlackboardResourcesRequest(sessionId=self.session,
                                                          links=[
                                                              depi_pb2.ResourceLinkRef(
                                                                  depi_pb2.ResourceRef(toolId=args[0],
                                                                                       resourceGroupURL=args[1],
                                                                                       URL=args[2]),
                                                                  depi_pb2.ResourceRef(toolId=args[3],
                                                                                       resourceGroupURL=args[4],
                                                                                       URL=args[5]))
                                                          ])
            resp = self.stub.UnlinkBlackboardResources(req)
        else:
            req = depi_pb2.UnlinkResourcesRequest(sessionId=self.session,
                                                link=depi_pb2.ResourceLinkRef(
                                                    depi_pb2.ResourceRef(toolId=args[0],
                                                                         resourceGroupURL=args[1],
                                                                         URL=args[2]),
                                                    depi_pb2.ResourceRef(toolId=args[3],
                                                                         resourceGroupURL=args[4],
                                                                         URL=args[5])))
            resp = self.stub.UnlinkResources(req)

        if not resp.ok:
            print("Error unlinking resources: {}".format(resp.msg))
            return

    @staticmethod
    def makeLinkRef(link):
        return depi_pb2.ResourceLinkRef(fromRes=depi_pb2.ResourceRef(toolId=link.fromRes.toolId,
                                                                     resourceGroupURL=link.fromRes.resourceGroupURL,
                                                                     URL=link.fromRes.URL),
                                        toRes=depi_pb2.ResourceRef(toolId=link.toRes.toolId,
                                                                   resourceGroupURL=link.toRes.resourceGroupURL,
                                                                   URL=link.toRes.URL))
    def do_clean(self, arg):
        'Marks a link as clean: clean (propagate | no-propagate) from-toolId from-rgURL from-resURL to-toolId to-rgURL to-resURL'
        args = arg.split()

        response = self.stub.GetBlackboardResources(depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))
        if not response.ok:
            print("Unable to fetch links: {}".format(response.msg))
            return

        propagate = args[0] == "propagate"

        args = args[1:]
        links = []
        if len(args) < 1:
            for link in response.depiLinks:
                links.append(self.makeLinkRef(link))
        elif len(args) < 2:
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0]:
                    links.append(self.makeLinkRef(link))
        elif len(args) < 3:
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1]:
                    links.append(self.makeLinkRef(link))
        elif len(args) < 4:
            pattern = re.compile(self.escape_re(args[2]))
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.fromRes.URL) is not None:
                    links.append(self.makeLinkRef(link))
        elif len(args) < 5:
            pattern = re.compile(self.escape_re(args[2]))
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.fromRes.URL) is not None and link.toRes.toolId == args[3]:
                    links.append(self.makeLinkRef(link))
        elif len(args) < 6:
            pattern = re.compile(self.escape_re(args[2]))
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.fromRes.URL) is not None and link.toRes.toolId == args[3] and \
                        link.toRes.resourceGroupURL == args[4]:
                    links.append(self.makeLinkRef(link))
        else:
            pattern = re.compile(self.escape_re(args[2]))
            pattern2 = re.compile(self.escape_re(args[5]))
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.fromRes.URL) is not None and link.toRes.toolId == args[3] and \
                        link.toRes.resourceGroupURL == args[4] and pattern2.fullmatch(link.toRes.URL) is not None:
                    links.append(self.makeLinkRef(link))

        response = self.stub.MarkLinksClean(depi_pb2.MarkLinksCleanRequest(sessionId=self.session,
                                                                           links=links,
                                                                           propagateCleanliness=propagate))
        if not response.ok:
            print("Error marking links clean: {}".format(response))
        else:
            print("Links cleaned.")

    def do_cleaninf(self, arg):
        'Marks an inferred dirtiness in a link as clean: cleaninf (propagate | no-propagate) from-toolId from-rgURL from-resURL to-toolId to-rgURL to-resURL dirty-toolId dirty-rgURL dirty-resURL'
        args = arg.split()

        if len(args) < 10:
            print("An exact link and resource ref is required to clean inferred dirtiness")
            return

        propagate = args[0] == "propagate"

        link = depi_pb2.ResourceLinkRef(
            fromRes=depi_pb2.ResourceRef(toolId=args[1], resourceGroupURL=args[2], URL=args[3]),
            toRes=depi_pb2.ResourceRef(toolId=args[4], resourceGroupURL=args[5], URL=args[6]))
        ref = depi_pb2.ResourceRef(toolId=args[7], resourceGroupURL=args[8], URL=args[9])

        response = self.stub.MarkInferredDirtinessClean(
            depi_pb2.MarkInferredDirtinessCleanRequest(
                sessionId=self.session, link=link, dirtinessSource=ref,
                propagateCleanliness=propagate))
        if not response.ok:
            print("Error marking inferred dirtiness clean: {}".format(response.msg))
            return

        print("Inferred dirtiness cleaned.")

    def do_dep(self, arg):
        'Returns a dependency graph: dep (up | down) start-toolId start-rgURL start-resURL'
        args = arg.split()

        depend_type = depi_pb2.DependenciesType.Dependants
        if args[0] == "up":
            depend_type = depi_pb2.DependenciesType.Dependencies

        response = self.stub.GetDependencyGraph(
            depi_pb2.GetDependencyGraphRequest(sessionId=self.session,
                                               toolId=args[1],
                                               resourceGroupURL=args[2],
                                               resourceURL=args[3],
                                               dependenciesType=depend_type))
        if not response.ok:
            print("Error fetching dependency tree: {}".format(response.msg))
            return

        print("Dependency graph:")
        for link in response.links:
            self.print_link(link)

    def do_dirty(self, arg):
        'Marks all links with the from-resource as dirty: dirty from-toolId from-rgURL from-rgName from-rgVersion from-resURL from-name from-id'
        args = arg.split()

        resChange = depi_pb2.ResourceChange(name=args[5], URL=args[4], changeType=depi_pb2.ChangeType.Modified,
                                            id=args[6], new_name=args[5], new_URL=args[4], new_id=args[6])
        rgChange = depi_pb2.ResourceGroupChange(toolId=args[0], name=args[2], URL=args[1],
                                                version=args[3], resources=[resChange])

        response = self.stub.UpdateResourceGroup(
            depi_pb2.UpdateResourceGroupRequest(sessionId=self.session, resourceGroup=rgChange))
        if not response.ok:
            print("Error marking resource links as dirty: {}".format(response.msg))
            return

        print("Resource marked as dirty")

    def do_watchdepi(self, arg):
        'subscribe for depi events'
        if self.watchingDepi:
            print("Already watching the depi")
            return
        watch_thread = Thread(target=self.depi_watcher, args=[])
        watch_thread.start()

    def do_unwatchdepi(self, arg):
        self.stub.UnwatchDepi(depi_pb2.UnwatchDepiRequest(sessionId=self.session))
        print("Sent unwatch")


    def do_load(self, filename):
        "Bulk loads a cli script that was generated by a dump command: load filename"
        script_file = open(filename, "r")

        resp = self.stub.ClearBlackboard(depi_pb2.ClearBlackboardRequest(sessionId=self.session))
        if not resp.ok:
            print("Error clearing the blackboard: {}".format(resp.msg))
            return

        resources_to_add = []
        links_to_add = []
        for line in script_file:
            line = line.rstrip()
            if line.startswith("add res"):
                parts = line.split(" ")[2:]
                resources_to_add.append(depi_pb2.Resource(toolId=parts[0], resourceGroupURL=parts[1],
                                                   URL=parts[2], name=parts[3], id=parts[4],
                                                   resourceGroupVersion=parts[5]))

                if len(resources_to_add) > 100:
                    req = depi_pb2.AddResourcesToBlackboardRequest(sessionId=self.session,
                                                                   resources=resources_to_add)
                    resp = self.stub.AddResourcesToBlackboard(req)
                    if not resp.ok:
                        print("Error adding resource group: {}".format(resp.msg))
                        return
                    resources_to_add = []
            elif line.startswith("link"):
                parts = line.split(" ")[1:]

                links_to_add.append(depi_pb2.ResourceLinkRef(
                    fromRes=depi_pb2.ResourceRef(toolId=parts[0], resourceGroupURL=parts[1], URL=parts[2]),
                    toRes=depi_pb2.ResourceRef(toolId=parts[3], resourceGroupURL=parts[4], URL=parts[5])))

                if len(resources_to_add) > 0:
                    req = depi_pb2.AddResourcesToBlackboardRequest(sessionId=self.session,
                                                                   resources=resources_to_add)
                    resp = self.stub.AddResourcesToBlackboard(req)
                    if not resp.ok:
                        print("Error adding resource group: {}".format(resp.msg))
                        return
                    resources_to_add = []

                if len(links_to_add) > 100:
                    req = depi_pb2.LinkBlackboardResourcesRequest(sessionId=self.session,
                                                                  links=links_to_add)
                    resp = self.stub.LinkBlackboardResources(req)
                    if not resp.ok:
                        print("Error linking resources: {}".format(resp.msg))
                        return
                    links_to_add = []

        if len(resources_to_add) > 0:
            req = depi_pb2.AddResourcesToBlackboardRequest(sessionId=self.session,
                                                           resources=resources_to_add)
            resp = self.stub.AddResourcesToBlackboard(req)
            if not resp.ok:
                print("Error adding resource group: {}".format(resp.msg))
                return

        if len(links_to_add) > 0:
            req = depi_pb2.LinkBlackboardResourcesRequest(sessionId=self.session,
                                                          links=links_to_add)
            resp = self.stub.LinkBlackboardResources(req)
            if not resp.ok:
                print("Error linking resources: {}".format(resp.msg))
                return

        resp = self.stub.SaveBlackboard(depi_pb2.SaveBlackboardRequest(sessionId=self.session))
        if not resp.ok:
            print("Error saving blackboard: {}".format(resp.msg))
            return
        print("Depi script loaded")

    def depi_watcher(self):
        for evt in self.stub.WatchDepi(depi_pb2.WatchDepiRequest(sessionId=self.session)):
            print("\nGot depi update with {} updates".format(len(evt.updates)))
        print("Finished watching depi")

    def tool_id_completion(self, prefix):
        response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))

        if not response.ok:
            print("Error fetching resource groups: {}".format(response.msg))
            return []

        completions = []
        for rg in response.resourceGroups:
            if rg.toolId.startswith(prefix):
                completions.append(rg.toolId)
        return completions

    def resource_group_completion(self, tool_id, prefix):
        response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))

        if not response.ok:
            print("Error fetching resource groups: {}".format(response.msg))
            return []

        completions = []
        for rg in response.resourceGroups:
            if rg.toolId == tool_id and rg.URL.startswith(prefix):
                completions.append(rg.URL)
        return completions

    def resource_group_name_completion(self, tool_id, resourceGroupURL, prefix):
        response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))

        if not response.ok:
            print("Error fetching resource groups: {}".format(response.msg))
            return []

        completions = []
        for rg in response.resourceGroups:
            if rg.toolId == tool_id and rg.URL == resourceGroupURL and rg.name.startswith(prefix):
                completions.append(rg.name)
        return completions

    def resource_group_version_completion(self, tool_id, resourceGroupURL, prefix):
        response = self.stub.GetResourceGroups(depi_pb2.GetResourceGroupsRequest(sessionId=self.session))

        if not response.ok:
            print("Error fetching resource groups: {}".format(response.msg))
            return []

        completions = []
        for rg in response.resourceGroups:
            if rg.toolId == tool_id and rg.URL == resourceGroupURL and rg.name.startswith(prefix):
                completions.append(rg.version)
        return completions

    def resource_completion(self, tool_id, resource_group, prefix, allow_wildcard=True):
        completions = []
        if len(prefix) == 0 and allow_wildcard:
            completions.append(".*")

        pattern = depi_pb2.ResourceRefPattern(toolId=tool_id, resourceGroupURL=resource_group, URLPattern=prefix + ".*")

        response = self.stub.GetResources(depi_pb2.GetResourcesRequest(sessionId=self.session, patterns=[pattern]))
        if not response.ok:
            print("Error fetching resources: {}".format(response.msg))
            return []

        try:
            for res in response.resources:
                if res.toolId == tool_id and res.resourceGroupURL == resource_group and res.URL.startswith(prefix):
                    completions.append(res.URL)
        except Exception:
            traceback.format_exc()
        return completions

    def resource_name_completion(self, tool_id, resource_group, url, prefix):
        pattern = depi_pb2.ResourceRefPattern(toolId=tool_id, resourceGroupURL=resource_group, URLPattern=prefix + ".*")

        response = self.stub.GetResources(depi_pb2.GetResourcesRequest(sessionId=self.session, patterns=[pattern]))
        if not response.ok:
            print("Error fetching resources: {}".format(response.msg))
            return []

        completions = []
        for res in response.resources:
            if res.toolId == tool_id and res.resourceGroupURL == resource_group and res.URL == url and \
                res.name.startswith(prefix):
                completions.append(res.name)
        return completions

    def resource_id_completion(self, tool_id, resource_group, url, prefix):
        pattern = depi_pb2.ResourceRefPattern(toolId=tool_id, resourceGroupURL=resource_group, URLPattern=prefix + ".*")

        response = self.stub.GetResources(depi_pb2.GetResourcesRequest(sessionId=self.session, patterns=[pattern]))
        if not response.ok:
            print("Error fetching resources: {}".format(response.msg))
            return []

        completions = []
        for res in response.resources:
            if res.toolId == tool_id and res.resourceGroupURL == resource_group and res.URL == url and \
                    res.id.startswith(prefix):
                completions.append(res.id)
        return completions

    def resource_ref_completion(self, args, complete, allow_wildcards=False):
        if len(args) == 0:
            return self.tool_id_completion(complete)
        elif len(args) == 1:
            return self.resource_group_completion(args[0], complete)
        elif len(args) >= 2:
            return self.resource_completion(args[0], args[1], complete, allow_wildcards)

    def resource_change_completion(self, args, complete):
        if len(args) == 0:
            return self.tool_id_completion(complete)
        elif len(args) == 1:
            return self.resource_group_completion(args[0], complete)
        elif len(args) == 2:
            return self.resource_group_name_completion(args[0], args[1], complete)
        elif len(args) == 3:
            return self.resource_group_version_completion(args[0], args[1], complete)
        elif len(args) == 4:
            return self.resource_completion(args[0], args[1], complete)
        elif len(args) == 5:
            return self.resource_name_completion(args[0], args[1], args[4], complete)
        elif len(args) == 6:
            return self.resource_id_completion(args[0], args[1], args[4], complete)
        else:
            return []

    def complete_res(self, text, line, begidx, endidx):
        completed = line[:begidx]
        complete = line[begidx:endidx+1]

        args = completed.split()

        return self.resource_ref_completion(args[1:], complete, allow_wildcards=True)

    def complete_links(self, text, line, begidx, endidx):
        completed = line[:begidx]
        complete = line[begidx:endidx+1]

        args = completed.split()

        return self.link_completion(args[1:], complete)

    def complete_link(self, text, line, begidx, endidx):
        completed = line[:begidx]
        complete = line[begidx:endidx+1]

        args = completed.split()

        return self.link_completion(args[1:], complete)

    def complete_unlink(self, text, line, begidx, endidx):
        completed = line[:begidx]
        complete = line[begidx:endidx+1]

        args = completed.split()

        return self.link_completion(args[1:], complete)

    def complete_clean(self, text, line, begidx, endidx):
        completed = line[:begidx]
        complete = line[begidx:endidx+1]

        args = completed.split()
        if len(args) == 1:
            if len(complete) > 0:
                if "propagate".startswith(complete):
                    return ["propagate"]
                elif "no-propagate".startswith(complete):
                    return ["no-propagate"]
            return ["propagate", "no-propagate"]
        else:
            return self.link_completion(args[2:], complete)

    def complete_cleaninf(self, text, line, begidx, endidx):
        completed = line[:begidx]
        complete = line[begidx:endidx+1]

        args = completed.split()
        if len(args) == 1:
            return ["propagate", "no-propagate"]
        elif len(args) < 8:
            return self.link_completion(args[2:], complete)
        else:
            return self.resource_ref_completion(args[8:], complete)

    def complete_dirty(self, text, line, begidx, endidx):
        completed = line[:begidx]
        complete = line[begidx:endidx+1]

        args = completed.split()
        return self.resource_change_completion(args[1:], complete)

    def complete_dep(self, text, line, begidx, endidx):
        completed = line[:begidx]
        complete = line[begidx:endidx + 1]

        args = completed.split()

        if len(args) == 1:
            if "up".startswith(complete):
                return ["up"]
            elif "down".startswith(complete):
                return ["down"]
            return ["up", "down"]
        elif len(args) < 5:
            return self.resource_ref_completion(args[2:], complete, allow_wildcards=False)
        else:
            return []

    def link_completion(self, args, complete):
        response = self.stub.GetBlackboardResources(depi_pb2.GetBlackboardResourcesRequest(sessionId=self.session))
        if not response.ok:
            print("Unable to fetch links: {}".format(response.msg))
            return

        if len(args) == 0:
            completions = set()
            for link in response.depiLinks:
                if link.fromRes.toolId.startswith(complete):
                    completions.add(link.fromRes.toolId)
            return list(completions)
        elif len(args) == 1:
            completions = set()
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL.startswith(complete):
                    completions.add(link.fromRes.resourceGroupURL)
            return list(completions)
        elif len(args) == 2:
            completions = set()
            if len(complete) == 0:
                completions.add(".*")
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1] and \
                   link.fromRes.URL.startswith(complete):
                    completions.add(link.fromRes.URL)
            return list(completions)
        elif len(args) == 3:
            completions = set()
            pattern = re.compile(args[2])
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1] and \
                   pattern.fullmatch(link.fromRes.URL) is not None and link.toRes.toolId.startswith(complete):
                    completions.add(link.toRes.toolId)
            return list(completions)
        elif len(args) == 4:
            completions = set()
            pattern = re.compile(args[2])
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.fromRes.URL) is not None and link.toRes.toolId == args[3] and \
                        link.toRes.resourceGroupURL.startswith(complete):
                    completions.add(link.toRes.resourceGroupURL)
            return list(completions)
        elif len(args) == 5:
            completions = set()
            if len(complete) == 0:
                completions.add(".*")
            pattern = re.compile(args[2])
            for link in response.depiLinks:
                if link.fromRes.toolId == args[0] and link.fromRes.resourceGroupURL == args[1] and \
                        pattern.fullmatch(link.fromRes.URL) is not None and link.toRes.toolId == args[3] and \
                        link.toRes.resourceGroupURL == args[4] and link.toRes.URL.startswith(complete):
                    completions.add(link.toRes.URL)
            return list(completions)
        else:
            return []

    def load_json(self, filename):
        json_file = open(filename, "r")
        depi_json = json.load(json_file)
        json_file.close()

        if not "tools" in depi_json:
            print("No tools field found in json file")
            return

        resp = self.stub.ClearBlackboard(depi_pb2.ClearBlackboardRequest(sessionId=self.session))
        if not resp.ok:
            print("Error clearing the blackboard: {}".format(resp.msg))
            return

        tools = depi_json["tools"]
        resources_to_add = []
        for tool_id in tools:
            tool = tools[tool_id]
            for rg_url in tool:
                rg = tool[rg_url]

                for res in rg["resources"]:
                    if res["deleted"]:
                        continue
                    resources_to_add.append(depi_pb2.Resource(toolId=tool_id,
                                      resourceGroupURL=rg_url,
                                      resourceGroupVersion=rg["version"],
                                      resourceGroupName=rg["name"],
                                      URL=res["URL"],
                                      name=res["name"],
                                      id=res["id"]))

                    if len(resources_to_add) > 100:
                        req = depi_pb2.AddResourcesToBlackboardRequest(sessionId=self.session,
                                                    resources = resources_to_add)
                        resp = self.stub.AddResourcesToBlackboard(req)
                        if not resp.ok:
                            print("Error adding resource group: {}".format(resp.msg))
                            return
                        resources_to_add = []
        if len(resources_to_add) > 0:
            req = depi_pb2.AddResourcesToBlackboardRequest(sessionId=self.session,
                                                           resources=resources_to_add)
            resp = self.stub.AddResourcesToBlackboard(req)
            if not resp.ok:
                print("Error adding resource group: {}".format(resp.msg))
                return

        if not "links" in depi_json:
            print("No links field found in json file")
            return

        links = depi_json["links"]

        links_to_add = []
        for link in links:
            if link["deleted"]:
                continue
            fromRes = link["fromRes"]
            toRes = link["toRes"]
            links_to_add.append(depi_pb2.ResourceLinkRef(
                                    fromRes=depi_pb2.ResourceRef(toolId=fromRes["toolId"],
                                                                 resourceGroupURL=fromRes["resourceGroupURL"],
                                                                 URL=fromRes["URL"]),
                                    toRes=depi_pb2.ResourceRef(toolId=toRes["toolId"],
                                                               resourceGroupURL=toRes["resourceGroupURL"],
                                                               URL=toRes["URL"])))

            if len(links_to_add) > 100:
                req = depi_pb2.LinkBlackboardResourcesRequest(sessionId=self.session,
                                                      links=links_to_add)
                resp = self.stub.LinkBlackboardResources(req)
                if not resp.ok:
                    print("Error linking resources: {}".format(resp.msg))
                    return
                links_to_add = []

        if len(links_to_add) > 0:
            req = depi_pb2.LinkBlackboardResourcesRequest(sessionId=self.session,
                                                          links=links_to_add)
            resp = self.stub.LinkBlackboardResources(req)
            if not resp.ok:
                print("Error linking resources: {}".format(resp.msg))
                return
        links_to_add = []

        resp = self.stub.SaveBlackboard(depi_pb2.SaveBlackboardRequest(sessionId=self.session))
        if not resp.ok:
            print("Error saving blackboard: {}".format(resp.msg))
            return


def get_config_item(config, field, default):
    if field in config:
        return config[field]
    else:
        return default

def open_channel(host, port, use_ssl, cert, options=None):
    if not use_ssl:
        return grpc.insecure_channel(host+":"+str(port))
    else:
        if cert is not None and len(cert) > 0:
            with open(cert, "rb") as file:
                cert_pem = file.read()
            cred = grpc.ssl_channel_credentials(root_certificates=cert_pem)
        else:
            cred = grpc.ssl_channel_credentials()
        return grpc.secure_channel(host+":"+str(port), cred, options=options)


def run():
    client_root = os.path.dirname(__file__)
    with open(client_root+"/configs/depi_cli.json") as cfg_file:
        config = json.load(cfg_file)

    parser = argparse.ArgumentParser(
        prog="Depi CLI",
        description="Command-Line interface for Depi")
    parser.add_argument("-host", "--host", dest="host",
                        default=get_config_item(config, "host", "localhost"))
    parser.add_argument("-p", "--port", dest="port", type=int,
                        default=get_config_item(config, "port", 5150))
    parser.add_argument("--ssl", dest="ssl", action="store_true", help="If true¸ use SSL for connection")
    parser.add_argument("-cert", "--cert", dest="cert",
                        default=get_config_item(config, "cert", ""))
    parser.add_argument("-u", "--user", dest="user",
                        default=get_config_item(config, "user", ""))
    parser.add_argument("-t", "--token", dest="token",
                        default=get_config_item(config, "token", ""))
    parser.add_argument("-nt", "--notoken", dest="notoken", type=bool,
                        default=get_config_item(config, "token", False))
    parser.add_argument("-pw", "--password", dest="password",
                        default=get_config_item(config, "password", ""))
    parser.add_argument("-proj", "--project", dest="project",
                        default=get_config_item(config, "project", ""))
    parser.add_argument("-upd", "--upd", dest="update", type=bool,
                        default=get_config_item(config, "update", False))
    parser.add_argument("-ssl-target-name", "--ssl-target-name", dest="ssl_target_name",
                        default=get_config_item(config, "ssl_target_name", ""))
    parser.add_argument("-script", "--script", dest="script", default="")
    parser.add_argument("-json", "--json", dest="json", default="")

    args = parser.parse_args()

    host = args.host
    port = args.port
    user = args.user
    use_ssl = args.ssl
    cert = args.cert
    password = args.password
    project = args.project
    update = args.update
    token = args.token
    no_token = args.notoken

    options = None
    if args.ssl_target_name is not None and len(args.ssl_target_name) > 0:
        options = (("grpc.ssl_target_name_override", args.ssl_target_name),)

    with open_channel(host, port, use_ssl, cert, options) as channel:
        stub = depi_pb2_grpc.DepiStub(channel)
        if len(token) > 0:
            response = stub.LoginWithToken(depi_pb2.LoginWithTokenRequest(loginToken=token))
        else:
            if not no_token and os.path.exists(".depi_token_"+user):
                file = open(".depi_token_" + user, "r")
                token = file.readline().strip()
                response = stub.LoginWithToken(depi_pb2.LoginWithTokenRequest(loginToken=token))
                if not response.ok:
                    response = stub.Login(
                        depi_pb2.LoginRequest(user=user, password=password, project=project, toolId="cli"))
            else:
                response = stub.Login(depi_pb2.LoginRequest(user=user, password=password, project=project, toolId="cli"))
        if not response.ok:
            print("Error logging into depi: {}".format(response.msg))

        file = open(".depi_token_"+user, "w")
        print(response.loginToken, file=file)
        file.close()

        session = response.sessionId

        if args.script is not None and len(args.script) > 0:
            DepiCli(stub, session, token, update).do_run(args.script)
        elif args.json is not None and len(args.json) > 0:
            DepiCli(stub, session, token, update).load_json(args.json)
        else:
            DepiCli(stub, session, token, update).cmdloop()


if __name__ == "__main__":
    run()
