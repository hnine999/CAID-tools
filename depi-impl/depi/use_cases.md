# CAID Use Cases

## Purpose

CAID focuses on the difficulty in associating dependencies with assurance cases, so that
it is possible to determine when tests used for evidence in an assurance case are up-to-date
with the code and model(s). While this has been a stated goal, CAID can be used simply to track
dependencies for a typical software development lifecycle, giving developers a way to determine
whether code and element artifacts are in sync (although it does require someone to determine
whether the changes flagged by CAID actually require updates to the related code, models, or
other artifacts).

## Description

There are several tools. Tools operate on projects.
Tools manage all the artifacts related to a project.
Artifacts can include source code artifacts, models, databases, formal verification, data
Artifacts are version-controlled, One way or another a tool does the version control over
the artifacts under its authority. Individual tools can do their own editing, create
their own versions.

We need a Depi-like database that supports the traceability across the artifacts in a project.
Gives the infrastructure for building more sophisticated operations like finding related
artifacts.

In the middle is the Depi database that is running on a server that is responsible for
managing the artifact links. Each tool will have some kind of adaptor that is looking
at the Depi database server from the tool side and reacts to it. The adaptor is tightly
connected to the tool, like a WebGME plugin or a VSCode plugin.

Need to be able to link not just containers, but also elements within a container.
For example, in a WebGME model, there can be a model element that doesn't contain
anything, need to be able to refer not just to the container but also to the element
itself. In a codebase, we may want to refer not just to files but fragments of code
within the files.

Artifacts may reside in non-file structures, like elements in a SQL database, or rows
in a spreadsheet.

The protocol between the tool adaptors and the Depi database should be agnostic to
the type of storage. The adaptor should be aware of how to access the artifacts
in the tool's repository.

## Link artifacts together

A user wants to create a link between two or more artifacts, including the possibility of
linking specific parts of an artifact together (e.g. a particular C++ function linked to an attribute
of an object in a WebGME model).

From a tool, the user is able to select an artifact or a section of an artifact, then select an
option to create a link. The tool then prompts the user for the other resources to be linked to.

Once an artifact is linked to other artifacts, the link should be preserved across changes to
any of the linked artifacts.

A separate blackboard interface lets the user drag&drop the artifact that needs to be linked.
The user would then use each tool to put the artifact into the same blackboard instance.

The Depi should keep track of the shareable resources.
You "drop" the resources into the Depi, and at some point later to create the links.

Resource Lifecycle in Depi:

1. Resource gets added to Depi as a shareable resource
2. You can add the resource to a link
3. You can remove it from a link
4. You can remove it from the set of shareable resources

The user needs to be able to recognize resources in the Depi Blackboard.
Options:

1. From the blackboard, you should be able to select a resource and have it highlighted in a tool
2. A human-readable URI that makes it obvious what the item is. The adaptor would be responsible for generating
   human-readable path names. When the user adds a resource to the blackboard, they can provide a human-readable
   description.

When resoures are added to the blackboard, it may be a good idea to store them as a hierarchy
so you can select the whole resource, or some sub-resource. How the resources are arranged in
a hierarchy is up to the adaptor (e.g. for source code, if the adapter adds resources that are
functions or classes, it is up to the adaptor to do that).

From the blackboard you should be able to see all the resources in the Depi.

### Versioning

You always need to know what version you are working with.

Suppose you always need to have a stable tag in order to do linking. In Git, it has to be something
that has been committed and pushed.

WebGME versions have to be tagged.

We won't be able to preserve links across moves.

## Create a new version in a tool

What happens to the Depi with regard to links that were established for the previous tagged version.

For each linked resource in a version, Depi performs the following updates to links:

1. If the resource is unchanged, the link stays the same
2. If the resource is changed, the resource is marked as changed in the link, and the linked resources
   are marked as dirty in the link.
3. If the resource is deleted, the resource is marked as deleted in the link, and the linked resources
   are marked as dirty in the link.

The change of a version of one or more projects within a Depi version constitutes the
creation of a new version.

The Depi keeps a list of things that need to be resolved, based on resources being marked
as dirty in a link. The discrepancy list should show what tools have a new version and what
resources have been changed in each tool. The Depi should provide an override mechanism to allow
a version of the Depi as stable, which would mark all the links as clean.

The Depi should have a capability of marking versions as stable or unstable, where a stable
version contains links with dirty resources.

The tool adaptor should tell Depi that there is a new version and provide the list of changes for
the version and what the new version is.

If the Depi has the ability to branch, there will need to be a separate discrepancy list for
each branch, so that the list of items to look at may be different depending on which Depi branch
you are working with.

## Navigate to Resources From Discrepancy List

Given a task, the user needs to go to a tool, make changes (or not) and then mark the task as
being completed.
The tasks are tied to links, so marking a resource as clean because of a particular linked
resource changed, does not mean that the resource is clean with respect to a changed resource
in a different link.

## Unlink artifacts

An artifact may be linked to other resources and the user determines that a particular link is
no longer valid. The user should have an option in the tool they are using to remove the artifact
from a link (i.e. if there are more than 2 artifacts linked, the other artifacts may still need
to be linked together), or they should be able to remove the link entirely (i.e. mark it as removed).

## Change linked artifact

The user makes a change to an artifact that is linked and saves the change. If the artifact is
linked to other artifacts, the links to the other artifacts are marked as being dirty
(dirty = linked to a resource that has changed and has not been changed or cleared of needing changes).
If they have other tools open that contain items linked to the changed artifact,
those tools notify the user that a linked resource has changed.

### Open Questions

1. For each tool, we need to identify what "saved" means. For WebGME because of the microcommits, this would basically be any change. For Git, when a commit is pushed to a central server.

## View artifacts that need to be changed

The user is working with a tool where they may not have seen the change notifications (the tool
may not have been running, or they saw the change notification but need to see it again). The user
selects an option to show dirty resources. Since links may be made to specific parts of an artifact,
the user should be able to request notifications for the current file, or directory, or project (i.e.
the various hierarchy levels supposed by the tool).

### Open Questions

1. Do we need a generic client for doing these operations that is independent of any tool, for the cases where we can't modify/extend the tool?

## Update or clean linked artifact

When the user is notified of a change, one thing that may happen is that the user has to make
changes to an artifact linked to the changed item. The user edits the linked item, and then
marks the item as clean in the link. Since it may be possible that an artifact or a part of
an artifact is linked multiple times, the user will need to indicate which links are now clean
for the object. It may be possible that the user changes something to satisfy changes in one link,
but another link requires some additional changes that the user has not yet made.

When the user is notified of a change, it may be that a linked artifact does not need to be
changed. The user can mark the item as clean just as they do when they have changed an artifact.
Again, the user will have to mark the item clean for each linked change, since it may be the
case that some linked changes do require the artifact to be changed, while others may not.

### Open Questions

1. When making an update due to a particular change, might the user want to update the link so that the original changed object needs to be revisited? This shouldn't be done automatically, but might occasionally be necessary.

## Research Questions

1. How do various graph databases handle branching in their version control
