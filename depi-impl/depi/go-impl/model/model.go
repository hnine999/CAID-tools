package model

import (
	"encoding/json"
	"go-impl/config"
	"go-impl/depi_grpc"
	"strings"
)

const (
	ChangeType_Added    int = 0
	ChangeType_Modified int = 1
	ChangeType_Renamed  int = 2
	ChangeType_Removed  int = 3
)

type Resource struct {
	Name       string `json:"name"`
	Id         string `json:"id"`
	URL        string `json:"URL"`
	Deleted    bool   `json:"deleted"`
	ChangeType int    `json:"-"`
}

type ResourceChange struct {
	Name       string
	Id         string
	URL        string
	NewName    string
	NewId      string
	NewURL     string
	Deleted    bool
	ChangeType int
}

type ResourceGroup struct {
	Name      string
	ToolId    string
	URL       string
	Version   string
	Resources map[string]*Resource
}

type ResourceGroupKey struct {
	ToolId string
	URL    string
}

type ResourceGroupChange struct {
	Name      string
	ToolId    string
	URL       string
	Version   string
	Resources map[string]*ResourceChange
}

type ResourceRef struct {
	ToolId           string `json:"toolId"`
	ResourceGroupURL string `json:"resourceGroupURL"`
	URL              string `json:"URL"`
}

type InferredDirtiness struct {
	ToolId           string
	ResourceGroupURL string
	URL              string
	LastCleanVersion string
}

type InferredDirtinessExt struct {
	ResourceGroup    *ResourceGroup
	Resource         *Resource
	LastCleanVersion string
}

type InferredDirtinessJson struct {
	Res              ResourceRef `json:"Resource"`
	LastCleanVersion string      `json:"lastCleanVersion"`
}

type Link struct {
	FromRes           *ResourceRef
	ToRes             *ResourceRef
	Dirty             bool
	Deleted           bool
	LastCleanVersion  string
	InferredDirtiness map[ResourceRef]string
}

type LinkWithResources struct {
	FromResourceGroup *ResourceGroup
	FromRes           *Resource
	ToResourceGroup   *ResourceGroup
	ToRes             *Resource
	Dirty             bool
	Deleted           bool
	LastCleanVersion  string
	InferredDirtiness []InferredDirtinessExt
}

type LinkKey struct {
	FromRes ResourceRef
	ToRes   ResourceRef
}

type ResourceRefPattern struct {
	ToolId           string
	ResourceGroupURL string
	URLPattern       string
}

type ResourceLinkPattern struct {
	FromRes *ResourceRefPattern
	ToRes   *ResourceRefPattern
}

func NewResourceLinkPatternFromGrpc(pattern *depi_grpc.ResourceLinkPattern) *ResourceLinkPattern {
	return &ResourceLinkPattern{
		FromRes: NewResourceRefPatternFromGrpc(pattern.FromRes),
		ToRes:   NewResourceRefPatternFromGrpc(pattern.ToRes),
	}
}

func (r *Resource) ToGrpc(resourceGroup *ResourceGroup) *depi_grpc.Resource {
	return &depi_grpc.Resource{
		ToolId:               resourceGroup.ToolId,
		ResourceGroupURL:     resourceGroup.URL,
		ResourceGroupName:    resourceGroup.Name,
		ResourceGroupVersion: resourceGroup.Version,
		Name:                 r.Name,
		URL:                  r.URL,
		Id:                   r.Id,
		Deleted:              r.Deleted,
	}
}

func (r *Resource) ToGrpcChange() *depi_grpc.ResourceChange {
	return &depi_grpc.ResourceChange{
		Name:       r.Name,
		URL:        r.URL,
		Id:         r.Id,
		ChangeType: depi_grpc.ChangeType(r.ChangeType),
	}
}

func (r *ResourceChange) ToGrpc() *depi_grpc.ResourceChange {
	return &depi_grpc.ResourceChange{
		Name:       r.Name,
		URL:        r.URL,
		Id:         r.Id,
		ChangeType: depi_grpc.ChangeType(r.ChangeType),
		NewName:    r.NewName,
		New_URL:    r.NewURL,
		NewId:      r.NewId,
	}
}

func NewResourceFromGrpc(grpcRes *depi_grpc.Resource) *Resource {
	return &Resource{
		Name: grpcRes.Name,
		Id:   grpcRes.Id,
		URL:  grpcRes.URL,
	}
}

func NewResourceFromGrpcResourceChange(grpcRes *depi_grpc.ResourceChange) *Resource {
	return &Resource{
		Name:       grpcRes.Name,
		Id:         grpcRes.Id,
		URL:        grpcRes.URL,
		ChangeType: int(grpcRes.ChangeType),
	}
}

func NewResourceChangeFromGrpc(grpcRes *depi_grpc.ResourceChange) *ResourceChange {
	return &ResourceChange{
		Name:       grpcRes.Name,
		Id:         grpcRes.Id,
		URL:        grpcRes.URL,
		NewName:    grpcRes.NewName,
		NewId:      grpcRes.NewId,
		NewURL:     grpcRes.New_URL,
		ChangeType: int(grpcRes.ChangeType),
	}
}

func (resChange *ResourceChange) ToResource() *Resource {
	return &Resource{
		Name:       resChange.Name,
		URL:        resChange.URL,
		Id:         resChange.Id,
		Deleted:    resChange.Deleted,
		ChangeType: resChange.ChangeType,
	}
}

func (resChange *ResourceChange) GetChangeAsUpdateType() depi_grpc.UpdateType {
	switch resChange.ChangeType {
	case 0:
		return depi_grpc.UpdateType_AddResource
	case 1:
		return depi_grpc.UpdateType_ChangeResource
	case 2:
		return depi_grpc.UpdateType_RenameResource
	case 3:
		return depi_grpc.UpdateType_RemoveResource
	}
	return 0
}

func (rg *ResourceGroup) Copy() *ResourceGroup {
	resources := map[string]*Resource{}
	for _, r := range rg.Resources {
		newRes := *r
		resources[newRes.URL] = &newRes
	}

	return &ResourceGroup{
		ToolId:    rg.ToolId,
		URL:       rg.URL,
		Name:      rg.Name,
		Version:   rg.Version,
		Resources: resources,
	}
}

func (rg *ResourceGroup) GetResource(url string) (*Resource, bool) {
	res, ok := rg.Resources[url]
	return res, ok
}

func (rg *ResourceGroup) AddResource(res *Resource) bool {
	_, ok := rg.Resources[res.URL]
	if !ok {
		rg.Resources[res.URL] = res
		return true
	} else {
		return false
	}
}

func (rg *ResourceGroup) RemoveResource(url string) bool {
	_, ok := rg.Resources[url]
	if ok {
		delete(rg.Resources, url)
		return true
	} else {
		return false
	}
}

func (rg *ResourceGroup) GetResources() []*Resource {
	res := []*Resource{}
	for _, r := range rg.Resources {
		res = append(res, r)
	}
	return res
}

func (rg *ResourceGroup) ToGrpc(includeResources bool) *depi_grpc.ResourceGroup {
	res := []*depi_grpc.Resource{}
	if includeResources {
		for _, r := range rg.Resources {
			res = append(res, r.ToGrpc(rg))
		}
	}

	return &depi_grpc.ResourceGroup{
		ToolId:    rg.ToolId,
		URL:       rg.URL,
		Name:      rg.Name,
		Version:   rg.Version,
		Resources: res,
	}
}
func NewResourceGroupFromGrpcResource(res *depi_grpc.Resource) *ResourceGroup {
	return &ResourceGroup{
		Name:    res.ResourceGroupName,
		ToolId:  res.ToolId,
		URL:     res.ResourceGroupURL,
		Version: res.ResourceGroupVersion,
	}
}

func NewResourceGroupFromGrpc(rg *depi_grpc.ResourceGroup) *ResourceGroup {
	resources := map[string]*Resource{}
	for _, res := range rg.Resources {
		resources[res.URL] = NewResourceFromGrpc(res)
	}

	return &ResourceGroup{
		ToolId:    rg.ToolId,
		URL:       rg.URL,
		Name:      rg.Name,
		Version:   rg.Version,
		Resources: resources,
	}
}

func NewResourceGroupChangeFromGrpc(rg *depi_grpc.ResourceGroupChange) *ResourceGroupChange {
	resources := map[string]*ResourceChange{}
	for _, res := range rg.Resources {
		resources[res.URL] = NewResourceChangeFromGrpc(res)
	}

	return &ResourceGroupChange{
		ToolId:    rg.ToolId,
		URL:       rg.URL,
		Name:      rg.Name,
		Version:   rg.Version,
		Resources: resources,
	}
}

func (rg ResourceGroup) MarshalJSON() ([]byte, error) {
	resources := []Resource{}
	for _, r := range rg.Resources {
		resources = append(resources, *r)
	}
	return json.Marshal(struct {
		Name      string     `json:"name"`
		ToolId    string     `json:"toolId"`
		URL       string     `json:"URL"`
		Version   string     `json:"version"`
		Resources []Resource `json:"resources"`
	}{
		rg.Name, rg.ToolId, rg.URL, rg.Version, resources,
	})
}

func (rg *ResourceGroup) UnmarshalJSON(data []byte) error {
	s := struct {
		Name      string     `json:"name"`
		ToolId    string     `json:"toolId"`
		URL       string     `json:"URL"`
		Version   string     `json:"version"`
		Resources []Resource `json:"resources"`
	}{}
	err := json.Unmarshal(data, &s)
	if err != nil {
		return err
	}
	rg.Name = s.Name
	rg.ToolId = s.ToolId
	rg.URL = s.URL
	rg.Version = s.Version
	rg.Resources = map[string]*Resource{}
	for _, r := range s.Resources {
		rg.Resources[r.URL] = &r
	}

	return nil
}

func (rgChange *ResourceGroupChange) ToResourceGroup() *ResourceGroup {
	resources := map[string]*Resource{}
	for url, res := range rgChange.Resources {
		resources[url] = res.ToResource()
	}
	return &ResourceGroup{
		Name:      rgChange.Name,
		ToolId:    rgChange.ToolId,
		URL:       rgChange.URL,
		Version:   rgChange.Version,
		Resources: resources,
	}
}

func NewResourceRefFromRGAndRes(rg *ResourceGroup, res *Resource) *ResourceRef {
	return &ResourceRef{ToolId: rg.ToolId, ResourceGroupURL: rg.URL, URL: res.URL}
}

func NewResourceRefFromGrpc(rr *depi_grpc.ResourceRef) *ResourceRef {
	return &ResourceRef{
		ToolId:           rr.ToolId,
		ResourceGroupURL: rr.ResourceGroupURL,
		URL:              rr.URL,
	}
}

func NewResourceRefPatternFromGrpc(rr *depi_grpc.ResourceRefPattern) *ResourceRefPattern {
	return &ResourceRefPattern{
		ToolId:           rr.ToolId,
		ResourceGroupURL: rr.ResourceGroupURL,
		URLPattern:       rr.URLPattern,
	}
}

func NewResourceRefFromGrpcResource(res *depi_grpc.Resource) *ResourceRef {
	return &ResourceRef{
		ToolId:           res.ToolId,
		ResourceGroupURL: res.ResourceGroupURL,
		URL:              res.URL,
	}
}

func (rr *ResourceRef) ToGrpc() *depi_grpc.ResourceRef {
	return &depi_grpc.ResourceRef{
		ToolId:           rr.ToolId,
		ResourceGroupURL: rr.ResourceGroupURL,
		URL:              rr.URL,
	}
}

func (rr *ResourceRef) ToGrpcResource() *depi_grpc.Resource {
	resourceGroup := &ResourceGroup{
		ToolId: rr.ToolId,
		URL:    rr.ResourceGroupURL,
	}
	res := &Resource{
		URL: rr.URL,
	}
	return res.ToGrpc(resourceGroup)
}

func (l *Link) Copy() *Link {
	fromRes := *l.FromRes
	toRes := *l.ToRes
	inferred := map[ResourceRef]string{}

	for inf, lastCleanVersion := range l.InferredDirtiness {
		inferred[inf] = lastCleanVersion
	}

	return &Link{
		FromRes:           &fromRes,
		ToRes:             &toRes,
		Dirty:             l.Dirty,
		Deleted:           l.Deleted,
		InferredDirtiness: inferred,
	}
}

func (l *Link) CompareFromResURL(resURL string) bool {
	if l.FromRes.URL == resURL {
		return true
	}

	toolConfig, ok := config.GlobalConfig.ToolConfig[l.FromRes.ToolId]
	pathSep := "/"
	if ok {
		pathSep = toolConfig.PathSeparator
	}

	if strings.HasSuffix(l.FromRes.URL, pathSep) {
		return strings.HasPrefix(resURL, l.FromRes.URL)
	} else {
		return strings.HasPrefix(resURL, l.FromRes.URL+pathSep)
	}
}

func (l *Link) HasFromLink(rg *ResourceGroup, res *Resource) bool {
	return l.FromRes.ToolId == rg.ToolId &&
		l.FromRes.ResourceGroupURL == rg.URL &&
		l.FromRes.URL == res.URL
}

func (l *Link) HasFromLinkRef(rr *ResourceRef) bool {
	return l.FromRes.ToolId == rr.ToolId &&
		l.FromRes.ResourceGroupURL == rr.ResourceGroupURL &&
		l.FromRes.URL == rr.URL
}

func (l *Link) HasFromLinkExt(rg *ResourceGroup, res *Resource, pathSeparator string) bool {
	resURL := res.URL
	if !strings.HasPrefix(resURL, pathSeparator) {
		resURL = pathSeparator + resURL
	}

	return l.FromRes.ToolId == rg.ToolId &&
		l.FromRes.ResourceGroupURL == rg.URL &&
		(l.FromRes.URL == res.URL ||
			strings.HasPrefix(resURL, l.FromRes.URL))
}
func (l *Link) HasToLink(rg *ResourceGroup, res *Resource) bool {
	return l.ToRes.ToolId == rg.ToolId &&
		l.ToRes.ResourceGroupURL == rg.URL &&
		l.ToRes.URL == res.URL
}

func (l *Link) HasToLinkRef(rr *ResourceRef) bool {
	return l.ToRes.ToolId == rr.ToolId &&
		l.ToRes.ResourceGroupURL == rr.ResourceGroupURL &&
		l.ToRes.URL == rr.URL
}

func (l *Link) ToGrpc() *depi_grpc.ResourceLinkRef {
	return &depi_grpc.ResourceLinkRef{
		FromRes: l.FromRes.ToGrpc(),
		ToRes:   l.ToRes.ToGrpc(),
	}
}

func (l *Link) ToGrpcResourceLink() *depi_grpc.ResourceLink {
	return &depi_grpc.ResourceLink{
		FromRes: l.FromRes.ToGrpcResource(),
		ToRes:   l.ToRes.ToGrpcResource(),
	}
}

func (l Link) MarshalJSON() ([]byte, error) {
	inferred := []InferredDirtinessJson{}
	for inf, lastCleanVersion := range l.InferredDirtiness {
		inferred = append(inferred,
			InferredDirtinessJson{
				Res: ResourceRef{
					ToolId:           inf.ToolId,
					ResourceGroupURL: inf.ResourceGroupURL,
					URL:              inf.URL,
				},
				LastCleanVersion: lastCleanVersion,
			})
	}
	return json.Marshal(struct {
		FromRes           ResourceRef             `json:"fromRes"`
		ToRes             ResourceRef             `json:"toRes"`
		Dirty             bool                    `json:"dirty"`
		Deleted           bool                    `json:"deleted"`
		InferredDirtiness []InferredDirtinessJson `json:"inferredDirtiness"`
	}{
		FromRes:           *l.FromRes,
		ToRes:             *l.ToRes,
		Dirty:             l.Dirty,
		Deleted:           l.Deleted,
		InferredDirtiness: inferred,
	})
}

func (l *Link) UnmarshalJSON(data []byte) error {
	s := struct {
		FromRes           ResourceRef             `json:"fromRes"`
		ToRes             ResourceRef             `json:"toRes"`
		Dirty             bool                    `json:"dirty"`
		Deleted           bool                    `json:"deleted"`
		InferredDirtiness []InferredDirtinessJson `json:"inferredDirtiness"`
	}{}

	err := json.Unmarshal(data, &s)
	if err != nil {
		return err
	}

	l.FromRes = &s.FromRes
	l.ToRes = &s.ToRes
	l.Dirty = s.Dirty
	l.Deleted = s.Deleted
	l.InferredDirtiness = map[ResourceRef]string{}
	for _, infJson := range s.InferredDirtiness {
		inf := ResourceRef{
			ToolId:           infJson.Res.ToolId,
			ResourceGroupURL: infJson.Res.ResourceGroupURL,
			URL:              infJson.Res.URL,
		}
		l.InferredDirtiness[inf] = infJson.LastCleanVersion
	}

	return nil
}

func NewLinkFromGrpc(link *depi_grpc.ResourceLink) *Link {
	inferred := map[ResourceRef]string{}
	for _, infGrpc := range link.InferredDirtiness {
		inf := ResourceRef{
			ToolId:           infGrpc.Resource.ToolId,
			ResourceGroupURL: infGrpc.Resource.ResourceGroupURL,
			URL:              infGrpc.Resource.URL,
		}
		inferred[inf] = infGrpc.LastCleanVersion
	}
	return &Link{
		FromRes:           NewResourceRefFromGrpcResource(link.FromRes),
		ToRes:             NewResourceRefFromGrpcResource(link.ToRes),
		Dirty:             link.Dirty,
		Deleted:           link.Deleted,
		InferredDirtiness: inferred,
	}
}

func NewLinkFromGrpcLinkRef(link *depi_grpc.ResourceLinkRef) *Link {
	inferred := map[ResourceRef]string{}
	return &Link{
		FromRes:           NewResourceRefFromGrpc(link.FromRes),
		ToRes:             NewResourceRefFromGrpc(link.ToRes),
		Dirty:             false,
		Deleted:           false,
		InferredDirtiness: inferred,
	}
}

func (l *LinkWithResources) CompareFromResURL(resURL string) bool {
	if l.FromRes.URL == resURL {
		return true
	}

	toolConfig, ok := config.GlobalConfig.ToolConfig[l.FromResourceGroup.ToolId]
	pathSep := "/"
	if ok {
		pathSep = toolConfig.PathSeparator
	}

	if strings.HasSuffix(l.FromRes.URL, pathSep) {
		return strings.HasPrefix(resURL, l.FromRes.URL)
	} else {
		return strings.HasPrefix(resURL, l.FromRes.URL+pathSep)
	}
}

func (l *LinkWithResources) HasFromLink(rg *ResourceGroup, res *Resource) bool {
	return l.FromResourceGroup.ToolId == rg.ToolId &&
		l.FromResourceGroup.URL == rg.URL &&
		l.FromRes.URL == res.URL
}

func (l *LinkWithResources) HasFromLinkRef(rr *ResourceRef) bool {
	return l.FromResourceGroup.ToolId == rr.ToolId &&
		l.FromResourceGroup.URL == rr.ResourceGroupURL &&
		l.FromRes.URL == rr.URL
}

func (l *LinkWithResources) HasFromLinkExt(rg *ResourceGroup, res *Resource, pathSeparator string) bool {
	resURL := res.URL
	if !strings.HasPrefix(resURL, pathSeparator) {
		resURL = pathSeparator + resURL
	}

	return l.FromResourceGroup.ToolId == rg.ToolId &&
		l.FromResourceGroup.URL == rg.URL &&
		(l.FromRes.URL == res.URL ||
			strings.HasPrefix(resURL, l.FromRes.URL))
}
func (l *LinkWithResources) HasToLink(rg *ResourceGroup, res *Resource) bool {
	return l.ToResourceGroup.ToolId == rg.ToolId &&
		l.ToResourceGroup.URL == rg.URL &&
		l.ToRes.URL == res.URL
}

func (l *LinkWithResources) HasToLinkRef(rr *ResourceRef) bool {
	return l.ToResourceGroup.ToolId == rr.ToolId &&
		l.ToResourceGroup.URL == rr.ResourceGroupURL &&
		l.ToRes.URL == rr.URL
}

func (l *LinkWithResources) ToGrpc() *depi_grpc.ResourceLink {
	inferred := []*depi_grpc.InferredDirtiness{}
	for _, inf := range l.InferredDirtiness {
		inferred = append(inferred,
			&depi_grpc.InferredDirtiness{
				Resource:         inf.Resource.ToGrpc(inf.ResourceGroup),
				LastCleanVersion: inf.LastCleanVersion,
			})
	}
	return &depi_grpc.ResourceLink{
		FromRes:           l.FromRes.ToGrpc(l.FromResourceGroup),
		ToRes:             l.ToRes.ToGrpc(l.ToResourceGroup),
		Dirty:             l.Dirty,
		Deleted:           l.Deleted,
		InferredDirtiness: inferred,
	}
}

func (inf *InferredDirtinessExt) ToInferredDirtiness() *InferredDirtiness {
	return &InferredDirtiness{
		ToolId:           inf.ResourceGroup.ToolId,
		ResourceGroupURL: inf.ResourceGroup.URL,
		URL:              inf.Resource.URL,
		LastCleanVersion: inf.LastCleanVersion,
	}
}

func (inf *InferredDirtinessExt) ToResourceRef() *ResourceRef {
	return &ResourceRef{
		ToolId:           inf.ResourceGroup.ToolId,
		ResourceGroupURL: inf.ResourceGroup.URL,
		URL:              inf.Resource.URL,
	}
}

func NewInferredDirtiness(rg *ResourceGroup, res *Resource, lastCleanVersion string) *InferredDirtiness {
	return &InferredDirtiness{
		ToolId:           rg.ToolId,
		ResourceGroupURL: rg.URL,
		URL:              res.URL,
		LastCleanVersion: lastCleanVersion,
	}
}

func (l *LinkWithResources) ToLink() *Link {
	inferred := map[ResourceRef]string{}
	for _, infExt := range l.InferredDirtiness {
		inferred[*infExt.ToResourceRef()] = infExt.LastCleanVersion
	}
	return &Link{
		FromRes: &ResourceRef{
			ToolId:           l.FromResourceGroup.ToolId,
			ResourceGroupURL: l.FromResourceGroup.URL,
			URL:              l.FromRes.URL,
		},
		ToRes: &ResourceRef{
			ToolId:           l.ToResourceGroup.ToolId,
			ResourceGroupURL: l.ToResourceGroup.URL,
			URL:              l.ToRes.URL,
		},
		Dirty:             l.Dirty,
		Deleted:           l.Deleted,
		InferredDirtiness: inferred,
	}
}

func GetLinkKey(link *Link) LinkKey {
	return LinkKey{FromRes: *link.FromRes, ToRes: *link.ToRes}
}

func GetLinkWithResourcesKey(link *LinkWithResources) LinkKey {
	return LinkKey{
		FromRes: *NewResourceRefFromRGAndRes(link.FromResourceGroup, link.FromRes),
		ToRes:   *NewResourceRefFromRGAndRes(link.ToResourceGroup, link.ToRes),
	}
}

type ResourceGroupAndResource struct {
	ResourceGroup *ResourceGroup
	Resource      *Resource
}

func (rg *ResourceGroup) GetKey() ResourceGroupKey {
	return ResourceGroupKey{
		ToolId: rg.ToolId,
		URL:    rg.URL,
	}
}
