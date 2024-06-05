package db

import (
	"go-impl/model"
	"regexp"
)

type DB interface {
	GetBranch(name string) (Branch, error)
	GetTag(name string) (Branch, error)
	BranchExists(name string) bool
	TagExists(name string) bool
	CreateBranch(name string, fromBranch string) (Branch, error)
	CreateBranchFromTag(name string, fromTag string) (Branch, error)
	CreateTag(name string, fromBranch string) (Branch, error)
	GetBranchList() ([]string, error)
	GetTagList() ([]string, error)
}

type LinkResourceRef struct {
	Link        *model.Link
	ResourceRef *model.ResourceRef
}
type ResourceGroupAndResourceStream func(rr *model.ResourceGroupAndResource)
type LinkStream func(rr *model.LinkWithResources)

type patternRegex struct {
	pattern *model.ResourceRefPattern
	regex   *regexp.Regexp
}

type Branch interface {
	Lock()
	Unlock()
	GetName() string
	MarkResourcesClean(resourceRefs []*model.ResourceRef, propagateCleanliness bool) error
	MarkLinksClean(links []*model.Link, propagateCleanliness bool) error
	MarkInferredDirtinessClean(link *model.Link, dirtinessSource *model.ResourceRef,
		propagateCleanliness bool) ([]LinkResourceRef, error)
	AddResource(rg *model.ResourceGroup, res *model.Resource) (bool, error)
	AddResources(resources []*model.ResourceGroupAndResource) (bool, error)
	AddLink(newLink *model.LinkWithResources) (bool, error)
	AddLinks(links []*model.LinkWithResources) (bool, error)
	RemoveResourceRef(rr *model.ResourceRef) (bool, error)
	GetResourceGroup(toolId string, URL string) (*model.ResourceGroup, error)
	GetResource(rr *model.ResourceRef, includeDeleted bool) (*model.ResourceGroupAndResource, error)
	GetDependencyGraph(rr *model.ResourceRef, upstream bool, maxDepth int) ([]*model.LinkWithResources, error)
	RemoveLink(delLink *model.Link) (bool, error)
	GetResourceGroupVersion(toolId string, URL string) (string, error)
	GetResourceGroups() ([]*model.ResourceGroup, error)
	GetResourceByRef(rr *model.ResourceRef) (*model.Resource, error)
	IsResourceDeleted(rr *model.ResourceRef) (bool, error)
	GetResources(resPatterns []*model.ResourceRefPattern, includeDeleted bool) ([]*model.ResourceGroupAndResource, error)
	GetResourcesAsStream(resPatterns []*model.ResourceRefPattern, includeDeleted bool,
		stream ResourceGroupAndResourceStream) error
	GetLinks(linkPatterns []*model.ResourceLinkPattern) ([]*model.LinkWithResources, error)
	GetLinksAsStream(linkPatterns []*model.ResourceLinkPattern, stream LinkStream) error
	ExpandLinks(linkPatterns []*model.Link) ([]*model.LinkWithResources, error)
	GetAllLinks(includeDeleted bool) ([]*model.LinkWithResources, error)
	GetAllLinksAsStream(includeDeleted bool, stream LinkStream) error
	GetDirtyLinks(resourceGroup *model.ResourceGroupKey, withInferred bool) ([]*model.LinkWithResources, error)
	GetDirtyLinksAsStream(resourceGroup *model.ResourceGroup, withInferred bool, stream LinkStream) error
	UpdateResourceGroup(resourceGroupChange *model.ResourceGroupChange) ([]*model.Link, error)
	EditResourceGroup(oldResourceGroup *model.ResourceGroup, newResourceGroup *model.ResourceGroup) error
	RemoveResourceGroup(toolId string, URL string) error
	SaveBranchState() error
}
