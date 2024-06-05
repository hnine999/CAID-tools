package server

import (
	"go-impl/depi_grpc"
	"go-impl/model"
)

type Blackboard struct {
	ChangedLinks map[model.LinkKey]*model.LinkWithResources
	DeletedLinks map[model.LinkKey]*model.LinkWithResources
	Resources    map[string]map[string]*model.ResourceGroup
}

func NewBlackboard() *Blackboard {
	return &Blackboard{
		ChangedLinks: map[model.LinkKey]*model.LinkWithResources{},
		DeletedLinks: map[model.LinkKey]*model.LinkWithResources{},
		Resources:    map[string]map[string]*model.ResourceGroup{},
	}
}

func (bb *Blackboard) GetResources() []*model.ResourceGroupAndResource {
	resList := []*model.ResourceGroupAndResource{}
	for _, tool := range bb.Resources {
		for _, rg := range tool {
			for _, res := range rg.Resources {
				resList = append(resList, &model.ResourceGroupAndResource{
					ResourceGroup: rg,
					Resource:      res,
				})
			}
		}
	}
	return resList
}

func (bb *Blackboard) AddResource(resourceGroup *model.ResourceGroup,
	resource *model.Resource) bool {
	tool, ok := bb.Resources[resourceGroup.ToolId]
	if !ok {
		tool = map[string]*model.ResourceGroup{}
		bb.Resources[resourceGroup.ToolId] = tool
	}
	toolRg, ok := tool[resourceGroup.URL]
	if !ok {
		toolRg = &model.ResourceGroup{
			Name:      resourceGroup.Name,
			ToolId:    resourceGroup.ToolId,
			URL:       resourceGroup.URL,
			Version:   resourceGroup.Version,
			Resources: map[string]*model.Resource{},
		}
		tool[resourceGroup.URL] = toolRg
	}

	newRes := &model.Resource{
		Name: resource.Name,
		Id:   resource.Id,
		URL:  resource.URL,
	}
	return toolRg.AddResource(newRes)
}

func (bb *Blackboard) RemoveResource(rr *model.ResourceRef) bool {
	tool, ok := bb.Resources[rr.ToolId]
	if !ok {
		return false
	}
	rg, ok := tool[rr.ResourceGroupURL]
	if !ok {
		return false
	}
	return rg.RemoveResource(rr.URL)
}

func (bb *Blackboard) ExpandResource(toolId string, resourceGroupURL string,
	resource string) *model.ResourceGroupAndResource {
	tool, ok := bb.Resources[toolId]
	if !ok {
		return nil
	}
	rg, ok := tool[resourceGroupURL]
	if !ok {
		return nil
	}
	res, ok := rg.Resources[resource]
	if !ok {
		return nil
	}
	return &model.ResourceGroupAndResource{
		ResourceGroup: rg,
		Resource:      res,
	}
}

func (bb *Blackboard) LinkResources(links []*model.LinkWithResources) []*depi_grpc.Update {
	updates := []*depi_grpc.Update{}
	for _, link := range links {
		linkKey := model.GetLinkWithResourcesKey(link)
		_, ok := bb.ChangedLinks[linkKey]
		if !ok {
			bb.ChangedLinks[linkKey] = link
			update := &depi_grpc.Update{
				UpdateType: depi_grpc.UpdateType_AddLink,
				UpdateData: &depi_grpc.Update_Link{
					Link: link.ToGrpc(),
				},
			}
			updates = append(updates, update)
			delete(bb.DeletedLinks, linkKey)
		} else {
			_, ok := bb.DeletedLinks[linkKey]
			if ok {
				delete(bb.DeletedLinks, linkKey)
				bb.ChangedLinks[linkKey] = link
				update := &depi_grpc.Update{
					UpdateType: depi_grpc.UpdateType_AddLink,
					UpdateData: &depi_grpc.Update_Link{
						Link: link.ToGrpc(),
					},
				}
				updates = append(updates, update)
			}
		}
	}
	return updates
}

func (bb *Blackboard) UnlinkResources(links []*model.LinkWithResources) []*depi_grpc.Update {
	updates := []*depi_grpc.Update{}
	for _, link := range links {
		linkKey := model.GetLinkWithResourcesKey(link)
		_, ok := bb.DeletedLinks[linkKey]
		bb.ChangedLinks[linkKey] = link
		bb.DeletedLinks[linkKey] = link
		if !ok {
			update := &depi_grpc.Update{
				UpdateType: depi_grpc.UpdateType_RemoveLink,
				UpdateData: &depi_grpc.Update_Link{
					Link: link.ToGrpc(),
				},
			}
			updates = append(updates, update)
		}
	}
	return updates
}
