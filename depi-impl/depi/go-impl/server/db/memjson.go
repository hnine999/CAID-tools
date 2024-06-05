package db

import (
	"encoding/json"
	"errors"
	"fmt"
	"go-impl/config"
	"go-impl/model"
	"log"
	"os"
	"regexp"
	"strconv"
	"strings"
	"sync"
)

type MemJsonDB struct {
	StateDir string
	Branches map[string]*MemBranch
	Tags     map[string]*MemBranch
	lock     sync.Mutex
}

type MemBranch struct {
	Name          string
	DB            *MemJsonDB
	IsTag         bool
	LastVersion   int
	ParentName    string
	ParentVersion int
	Links         map[model.LinkKey]*model.Link
	Tools         map[string]map[string]*model.ResourceGroup
	lock          sync.Mutex
}

type MemBranchJson struct {
	Name          string       `json:"name"`
	LastVersion   int          `json:"lastVersion"`
	ParentName    string       `json:"parentName"`
	ParentVersion int          `json:"parentVersion"`
	Links         []model.Link `json:"links"`
	Tools         map[string]map[string]model.ResourceGroup
}

func NewMemJsonDB() *MemJsonDB {
	stateDir := config.GlobalConfig.DBConfig.StateDir
	if stateDir == "" {
		stateDir = ".state"
	}
	memdb := MemJsonDB{
		StateDir: stateDir,
		Branches: map[string]*MemBranch{},
		Tags:     map[string]*MemBranch{},
	}
	memdb.Branches["main"] = NewMemBranch(&memdb, "main", 0, "")
	loadAllState(&memdb)

	return &memdb
}

func loadAllState(memdb *MemJsonDB) {
	stat, err := os.Stat(memdb.StateDir)
	if err == nil && !stat.IsDir() {
		os.Remove(memdb.StateDir)
	}

	if err != nil && err == os.ErrNotExist {
		os.MkdirAll(memdb.StateDir, 06666)
		memdb.Branches["main"] = NewMemBranch(memdb, "main", 0, "")
		memdb.Branches["main"].SaveBranchState()
	}

	entries, err := os.ReadDir(memdb.StateDir)
	if err == nil {
		for _, branchEntry := range entries {
			branch := branchEntry.Name()
			if branch == "tags" {
				continue
			}
			latestVer := 0
			branchDir := memdb.StateDir + "/" + branch
			stat, err := os.Stat(branchDir)
			if err == nil && stat.IsDir() {
				branchEntries, err := os.ReadDir(branchDir)
				if err == nil {
					for _, nextBranchEntry := range branchEntries {
						if !nextBranchEntry.IsDir() {
							ver, err := strconv.Atoi(nextBranchEntry.Name())
							if err == nil && ver > latestVer {
								latestVer = ver
							}
						}
					}
					if latestVer > 0 {
						loadedBranch, err := memdb.loadBranchData(branchDir, latestVer)
						if err != nil {
							log.Printf("error loading branch %s: %+v\n", branch, err)
							continue
						}
						memdb.Branches[branch] = loadedBranch
					}
				}
			}
		}
	}

	if _, err := os.Stat(memdb.StateDir + "/tags"); err != nil {
		return
	}

	entries, err = os.ReadDir(memdb.StateDir + "/tags")
	if err != nil {
		log.Printf("error reading tags directory: %+v\n", err)
		return
	}

	for _, tagEntry := range entries {
		tag := tagEntry.Name()
		tagInfo := struct {
			Branch  string `json:"branch"`
			Version int    `json:"version"`
		}{}
		data, err := os.ReadFile(memdb.StateDir + "/tags/" + tag)
		if err != nil {
			log.Printf("Error reading tag file %s: %+v", tag, err)
			continue
		}
		err = json.Unmarshal(data, &tagInfo)
		if err != nil {
			log.Printf("Error parsing tag file %s: %+v", tag, err)
			continue
		}
		tagBranch, err := memdb.loadBranchData(memdb.StateDir+"/"+tagInfo.Branch, tagInfo.Version)
		if err != nil {
			log.Printf("Error loading tagged branch %s:%d: %+v", tagInfo.Branch, tagInfo.Version, err)
			continue
		}
		tagBranch.IsTag = true
		memdb.Tags[tag] = tagBranch
	}
}

func (memdb *MemJsonDB) loadBranchData(branchDir string, version int) (*MemBranch, error) {
	inFile, err := os.Open(branchDir + "/" + strconv.Itoa(version))
	if err != nil {
		return nil, err
	}
	defer inFile.Close()

	dec := json.NewDecoder(inFile)
	newBranch := MemBranchJson{}
	err = dec.Decode(&newBranch)
	if err != nil {
		return nil, err
	}

	tools := map[string]map[string]*model.ResourceGroup{}
	for toolId, tool := range newBranch.Tools {
		newTool := map[string]*model.ResourceGroup{}
		for rgURL, rg := range tool {
			newTool[rgURL] = &rg
		}
		tools[toolId] = newTool
	}

	links := map[model.LinkKey]*model.Link{}
	for _, link := range newBranch.Links {
		linkKey := model.GetLinkKey(&link)
		links[linkKey] = &link
	}

	return &MemBranch{
		Name:          newBranch.Name,
		DB:            memdb,
		IsTag:         false,
		LastVersion:   newBranch.LastVersion,
		ParentName:    newBranch.ParentName,
		ParentVersion: newBranch.ParentVersion,
		Links:         links,
		Tools:         tools,
	}, nil
}

func (m *MemJsonDB) saveBranch(branch *MemBranch) error {
	m.lock.Lock()
	defer m.lock.Unlock()

	dirName := m.StateDir + "/" + branch.Name
	err := os.MkdirAll(dirName, 0755)
	if err != nil {
		fmt.Printf("Error creating state directory: %+v\n", err)
		return err
	}

	nextVersion := branch.LastVersion + 1
	outFile, err := os.Create(m.StateDir + "/" + branch.Name + "/" + strconv.Itoa(nextVersion))
	if err != nil {
		return err
	}
	defer outFile.Close()

	tools := map[string]map[string]model.ResourceGroup{}
	for toolId, tool := range branch.Tools {
		newTool := map[string]model.ResourceGroup{}
		for rgURL, rg := range tool {
			newTool[rgURL] = *rg
		}
		tools[toolId] = newTool
	}

	links := []model.Link{}
	for _, link := range branch.Links {
		links = append(links, *link)
	}
	enc := json.NewEncoder(outFile)
	return enc.Encode(&MemBranchJson{
		Name:          branch.Name,
		LastVersion:   branch.LastVersion,
		ParentName:    branch.ParentName,
		ParentVersion: branch.ParentVersion,
		Links:         links,
		Tools:         tools,
	})
}

func (m *MemJsonDB) GetBranch(name string) (Branch, error) {
	m.lock.Lock()
	defer m.lock.Unlock()
	branch, ok := m.Branches[name]
	if ok {
		return branch, nil
	} else {
		return nil, errors.New(fmt.Sprintf("branch %s does not exist", name))
	}
}

func (m *MemJsonDB) GetTag(name string) (Branch, error) {
	m.lock.Lock()
	defer m.lock.Unlock()
	branch, ok := m.Tags[name]
	if ok {
		return branch, nil
	} else {
		return nil, errors.New(fmt.Sprintf("tag %s does not exist", name))
	}
}

func (m *MemJsonDB) BranchExists(name string) bool {
	m.lock.Lock()
	defer m.lock.Unlock()
	_, ok := m.Branches[name]
	return ok
}

func (m *MemJsonDB) TagExists(name string) bool {
	m.lock.Lock()
	defer m.lock.Unlock()
	_, ok := m.Tags[name]
	return ok
}

func (m *MemJsonDB) CreateBranch(name string, fromBranch string) (Branch, error) {
	m.lock.Lock()
	defer m.lock.Unlock()
	if m.BranchExists(name) {
		return nil, errors.New(fmt.Sprintf("branch %s already exists", name))
	}
	if !m.BranchExists(fromBranch) {
		return nil, errors.New(fmt.Sprintf("branch %s does not exist", name))
	}
	newBranch, err := m.GetBranch(fromBranch)
	if err != nil {
		return nil, err
	}
	m.Branches[name] = newBranch.(*MemBranch).copy(name)
	newBranch.(*MemBranch).saveBranchState()
	return newBranch, nil
}

func (m *MemJsonDB) CreateBranchFromTag(name string, fromTag string) (Branch, error) {
	if m.BranchExists(name) {
		return nil, errors.New(fmt.Sprintf("branch %s already exists", name))
	}
	if !m.TagExists(fromTag) {
		return nil, errors.New(fmt.Sprintf("tag %s does not exist", name))
	}
	newBranch, err := m.GetTag(fromTag)
	if err != nil {
		return nil, err
	}
	m.lock.Lock()
	defer m.lock.Unlock()

	m.Branches[name] = newBranch.(*MemBranch).copy(name)
	newBranch.(*MemBranch).saveBranchState()
	return newBranch, nil
}

func (m *MemJsonDB) CreateTag(name string, fromBranch string) (Branch, error) {
	if m.TagExists(name) {
		return nil, errors.New(fmt.Sprintf("tag %s already exists", name))
	}
	if !m.BranchExists(fromBranch) {
		return nil, errors.New(fmt.Sprintf("branch %s does not exist", name))
	}
	newBranch, err := m.GetBranch(fromBranch)
	if err != nil {
		return nil, err
	}
	m.lock.Lock()
	defer m.lock.Unlock()

	m.Tags[name] = newBranch.(*MemBranch).copy(name)
	newBranch.(*MemBranch).IsTag = true

	tagsDir := m.StateDir + "/tags"
	if _, err := os.Stat(tagsDir); errors.Is(err, os.ErrNotExist) {
		os.MkdirAll(tagsDir, 0666)
	}
	f, err := os.Create(tagsDir + "/" + name)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	enc := json.NewEncoder(f)
	err = enc.Encode(newBranch)

	return newBranch, nil
}

func (m *MemJsonDB) GetBranchList() ([]string, error) {
	branches := []string{}
	for key := range m.Branches {
		branches = append(branches, key)
	}
	return branches, nil
}

func (m *MemJsonDB) GetTagList() ([]string, error) {
	tags := []string{}
	for key := range m.Tags {
		tags = append(tags, key)
	}
	return tags, nil
}

func NewMemBranch(memdb *MemJsonDB, branch string, version int, parent string) *MemBranch {
	return &MemBranch{
		Name:        branch,
		DB:          memdb,
		IsTag:       false,
		LastVersion: version,
		ParentName:  parent,
		Links:       map[model.LinkKey]*model.Link{},
		Tools:       map[string]map[string]*model.ResourceGroup{},
	}
}

func (branch *MemBranch) Lock() {
	branch.lock.Lock()
}

func (branch *MemBranch) Unlock() {
	branch.lock.Unlock()
}

func (branch *MemBranch) GetName() string {
	return branch.Name
}

func (branch *MemBranch) saveBranchState() error {
	return branch.DB.saveBranch(branch)
}

func (branch *MemBranch) copy(name string) *MemBranch {
	newCopy := MemBranch{
		DB:            branch.DB,
		Name:          name,
		LastVersion:   0,
		ParentName:    branch.Name,
		ParentVersion: branch.LastVersion,
		Links:         map[model.LinkKey]*model.Link{},
		Tools:         map[string]map[string]*model.ResourceGroup{},
	}

	for toolId, tool := range branch.Tools {
		newTool := map[string]*model.ResourceGroup{}
		for rgURL, rg := range tool {
			newTool[rgURL] = rg.Copy()
		}
		newCopy.Tools[toolId] = newTool
	}

	for linkKey, link := range branch.Links {
		newCopy.Links[linkKey] = link.Copy()

	}

	return &newCopy
}

func linkResMatches(pathSeparator string, linkURL string, resURL string) bool {
	if strings.HasSuffix(linkURL, pathSeparator) {
		return strings.HasPrefix(resURL, linkURL)
	} else {
		return strings.HasPrefix(resURL, linkURL+pathSeparator)
	}
}

func (branch *MemBranch) linkToLinkWithResources(link *model.Link) (*model.LinkWithResources, error) {
	fromRgAndRes, err := branch.GetResource(link.FromRes, true)
	if err != nil {
		return nil, err
	}
	toRgAndRes, err := branch.GetResource(link.ToRes, true)
	if err != nil {
		return nil, err
	}

	inferred := []model.InferredDirtinessExt{}
	for infd, lastClean := range link.InferredDirtiness {
		infRgAndRes, err := branch.GetResource(
			&model.ResourceRef{
				ToolId:           infd.ToolId,
				ResourceGroupURL: infd.ResourceGroupURL,
				URL:              infd.URL,
			}, true)
		if err != nil {
			return nil, err
		}
		inferred = append(inferred,
			model.InferredDirtinessExt{
				ResourceGroup:    infRgAndRes.ResourceGroup,
				Resource:         infRgAndRes.Resource,
				LastCleanVersion: lastClean,
			})
	}

	return &model.LinkWithResources{
		FromResourceGroup: fromRgAndRes.ResourceGroup,
		FromRes:           fromRgAndRes.Resource,
		ToResourceGroup:   toRgAndRes.ResourceGroup,
		ToRes:             toRgAndRes.Resource,
		Dirty:             link.Dirty,
		Deleted:           link.Deleted,
		LastCleanVersion:  link.LastCleanVersion,
		InferredDirtiness: inferred,
	}, nil
}

func (branch *MemBranch) markLinkDirty(link *model.Link, currentVersion string) {
	linkKey := model.GetLinkKey(link)

	if !link.Dirty {
		link.LastCleanVersion = currentVersion
	}

	link.Dirty = true
	linksUpdated := map[model.ResourceRef]bool{}
	linksToProcess := []*model.ResourceRef{link.ToRes}

	linkMap := map[model.ResourceRef][]*model.Link{}
	for _, currLink := range branch.Links {
		lm, ok := linkMap[*currLink.FromRes]
		if !ok {
			linkMap[*currLink.FromRes] = []*model.Link{currLink}
		} else {
			linkMap[*currLink.FromRes] = append(lm, currLink)
		}
	}

	for len(linksToProcess) > 0 {
		var infLink *model.ResourceRef
		infLink, linksToProcess = linksToProcess[len(linksToProcess)-1], linksToProcess[:len(linksToProcess)-1]
		linksUpdated[*infLink] = true

		links, ok := linkMap[*infLink]
		if ok {
			for _, currLink := range links {
				if model.GetLinkKey(currLink) != linkKey {
					found := false
					for infd := range currLink.InferredDirtiness {
						if infd.ToolId == link.FromRes.ToolId &&
							infd.ResourceGroupURL == link.FromRes.ResourceGroupURL &&
							infd.URL == link.FromRes.URL {
							found = true
							break
						}
					}

					if !found {
						currLink.InferredDirtiness[model.ResourceRef{
							ToolId:           link.FromRes.ToolId,
							ResourceGroupURL: link.FromRes.ResourceGroupURL,
							URL:              link.FromRes.URL,
						}] = currentVersion
						_, ok := linksUpdated[*currLink.ToRes]
						if !ok {
							linksToProcess = append(linksToProcess, currLink.ToRes)
						}
					}
				}
			}
		}
	}
}

func (branch *MemBranch) UpdateResourceGroup(resourceGroupChange *model.ResourceGroupChange) ([]*model.Link, error) {
	fmt.Printf("Updating resource group %s %s\n", resourceGroupChange.ToolId, resourceGroupChange.URL)
	tool, ok := branch.Tools[resourceGroupChange.ToolId]
	if !ok {
		tool = map[string]*model.ResourceGroup{}
		branch.Tools[resourceGroupChange.ToolId] = tool
	}

	pathSeparator := "/"
	toolConfig, ok := config.GlobalConfig.ToolConfig[resourceGroupChange.ToolId]
	if ok {
		pathSeparator = toolConfig.PathSeparator
	}

	key := resourceGroupChange.URL
	resourceGroup := tool[key]

	linkedResourceGroupsToUpdate := map[model.LinkKey]*model.Link{}

	if resourceGroup == nil {
		resourceGroup = resourceGroupChange.ToResourceGroup()
		tool[key] = resourceGroup
		return []*model.Link{}, nil
	}

	originalVersion := resourceGroup.Version
	resourceGroup.Version = resourceGroupChange.Version

	for _, resourceChange := range resourceGroupChange.Resources {
		fmt.Printf("Processing resource change %s %d\n", resourceChange.URL, resourceChange.ChangeType)
		if resourceChange.ChangeType == model.ChangeType_Added ||
			resourceChange.ChangeType == model.ChangeType_Modified {
			for linkKey, link := range branch.Links {
				if link.HasFromLinkExt(resourceGroup, resourceChange.ToResource(), pathSeparator) {
					branch.markLinkDirty(link, originalVersion)
					linkedResourceGroupsToUpdate[linkKey] = link
				}
			}
		}

		if resourceChange.ChangeType == model.ChangeType_Renamed ||
			(resourceChange.ChangeType == model.ChangeType_Modified &&
				(resourceChange.URL != resourceChange.NewURL ||
					resourceChange.Name != resourceChange.NewName ||
					resourceChange.Id != resourceChange.NewId)) {
			resource := resourceChange.ToResource()
			newLinks := map[model.LinkKey]*model.Link{}
			for linkKey, link := range branch.Links {
				if link.HasFromLinkExt(resourceGroup, resource, pathSeparator) {
					fromRgRes, err := branch.GetResource(link.FromRes, false)
					if err != nil {
						fmt.Printf("Error fetching resource %s %s %s\n", link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL)
						continue
					}
					if fromRgRes.Resource.URL == resourceChange.URL {
						delete(resourceGroup.Resources, fromRgRes.Resource.URL)
						fromRgRes.Resource.Name = resourceChange.NewName
						fromRgRes.Resource.URL = resourceChange.NewURL
						fromRgRes.Resource.Id = resourceChange.NewId
						resourceGroup.Resources[fromRgRes.Resource.URL] = fromRgRes.Resource
						link.FromRes.URL = resourceChange.NewURL
						newLinkKey := model.GetLinkKey(link)
						newLinks[newLinkKey] = link
						linkedResourceGroupsToUpdate[linkKey] = link
					} else {
						newLinks[linkKey] = link
					}
				} else if link.HasToLink(resourceGroup, resource) {
					newLinks[linkKey] = link
					toRgRes, err := branch.GetResource(link.ToRes, false)
					if err != nil {
						fmt.Printf("Error fetching resource %s %s %s\n", link.ToRes.ToolId, link.FromRes.ResourceGroupURL, link.ToRes.URL)
						continue
					}
					toRgRes.Resource.Name = resourceChange.NewName
					toRgRes.Resource.URL = resourceChange.NewURL
					toRgRes.Resource.Id = resourceChange.NewId
					link.ToRes.URL = resourceChange.NewURL
				} else {
					newLinks[linkKey] = link
				}
				for inferred, lastClean := range link.InferredDirtiness {
					if inferred.ToolId == resourceGroupChange.ToolId &&
						inferred.ResourceGroupURL == resourceGroupChange.URL &&
						inferred.URL == resourceChange.URL {
						delete(link.InferredDirtiness, inferred)
						inferred.URL = resourceChange.NewURL
						link.InferredDirtiness[inferred] = lastClean
						break
					}
				}
			}
			branch.Links = newLinks
			res, ok := resourceGroup.Resources[resourceChange.URL]
			if ok {
				delete(resourceGroup.Resources, resourceChange.URL)
				res.URL = resourceChange.NewURL
				resourceGroup.Resources[resourceChange.NewURL] = res
			}
		} else if resourceChange.ChangeType == model.ChangeType_Removed {
			linksToRemove := []model.LinkKey{}
			removeResource := true
			resource := resourceChange.ToResource()
			for linkKey, link := range branch.Links {
				if link.HasFromLinkExt(resourceGroup, resource, pathSeparator) {
					branch.markLinkDirty(link, originalVersion)
					fromRgRes, err := branch.GetResource(link.FromRes, true)
					if err != nil {
						continue
					}
					if fromRgRes.Resource.URL == resourceChange.URL {
						fromRgRes.Resource.Deleted = true
						link.Deleted = true
						removeResource = false
					}
					linkedResourceGroupsToUpdate[linkKey] = link
				} else if link.HasToLink(resourceGroup, resource) {
					toRgRes, err := branch.GetResource(link.ToRes, true)
					if err != nil {
						continue
					}
					toRgRes.Resource.Deleted = true
					linksToRemove = append(linksToRemove, linkKey)
				}
				delete(link.InferredDirtiness, model.ResourceRef{
					ToolId:           resourceGroup.ToolId,
					ResourceGroupURL: resourceGroup.URL,
					URL:              resource.URL,
				})
			}
			for _, link := range linksToRemove {
				delete(branch.Links, link)
				if removeResource {
					delete(resourceGroup.Resources, resourceChange.URL)
				}
			}
		}
	}
	returnLinks := []*model.Link{}
	for _, link := range linkedResourceGroupsToUpdate {
		returnLinks = append(returnLinks, link)
	}
	return returnLinks, nil
}

func (branch *MemBranch) MarkResourcesClean(resourceRefs []*model.ResourceRef, propagateCleanliness bool) error {
	for _, rr := range resourceRefs {
		for _, link := range branch.Links {
			if link.HasToLinkRef(rr) {
				link.Dirty = false
				link.LastCleanVersion = ""
				delete(link.InferredDirtiness, *rr)
			}
		}
	}
	return nil
}

func (branch *MemBranch) MarkLinksClean(links []*model.Link, propagateCleanliness bool) error {
	for _, cl := range links {
		linksToDelete := []model.LinkKey{}
		for linkKey, link := range branch.Links {
			if link.HasFromLinkRef(cl.FromRes) &&
				link.HasToLinkRef(cl.ToRes) {
				link.Dirty = false
				link.LastCleanVersion = ""
				if link.Deleted {
					linksToDelete = append(linksToDelete, linkKey)
				}
			}
		}

		for _, link := range linksToDelete {
			delete(branch.Links, link)
			resInfo, err := branch.GetResource(&link.FromRes, true)
			if err != nil {
				continue
			}

			deleteRes := resInfo.Resource.Deleted
			for _, lk2 := range branch.Links {
				if *lk2.FromRes == link.FromRes && !lk2.Deleted {
					deleteRes = false
				}
			}
			if deleteRes {
				delete(resInfo.ResourceGroup.Resources, resInfo.Resource.URL)
				for _, lk2 := range branch.Links {
					infToRemove := []model.ResourceRef{}
					for rr := range lk2.InferredDirtiness {
						if rr.ToolId == resInfo.ResourceGroup.ToolId &&
							rr.ResourceGroupURL == resInfo.ResourceGroup.URL &&
							rr.URL == resInfo.Resource.URL {
							infToRemove = append(infToRemove, rr)
						}
					}

					for _, rr := range infToRemove {
						delete(lk2.InferredDirtiness, rr)
					}
				}
			}
		}

		if propagateCleanliness {
			branch.MarkInferredDirtinessClean(cl, cl.FromRes, propagateCleanliness)
		}
	}

	return nil
}

func (branch *MemBranch) MarkInferredDirtinessClean(linkToClean *model.Link, dirtinessSource *model.ResourceRef,
	propagateCleanliness bool) ([]LinkResourceRef, error) {
	var targetLink *model.Link
	for _, link := range branch.Links {
		if link.HasFromLinkRef(linkToClean.FromRes) &&
			link.HasToLinkRef(linkToClean.ToRes) {
			targetLink = link
		}
	}
	if targetLink == nil {
		return []LinkResourceRef{}, nil
	}

	cleanedLinks := []LinkResourceRef{}
	if !propagateCleanliness {
		_, present := targetLink.InferredDirtiness[*dirtinessSource]
		if present {
			delete(targetLink.InferredDirtiness, *dirtinessSource)
			cleanedLinks = append(cleanedLinks, LinkResourceRef{
				Link:        targetLink,
				ResourceRef: dirtinessSource,
			})
		}
	} else {
		workQueue := []*model.Link{targetLink}
		processedLinks := map[model.LinkKey]*model.Link{}

		for len(workQueue) > 0 {
			var currLink *model.Link
			currLink, workQueue = workQueue[len(workQueue)-1], workQueue[:len(workQueue)-1]
			processedLinks[model.GetLinkKey(currLink)] = currLink

			_, present := currLink.InferredDirtiness[*dirtinessSource]
			if present {
				delete(currLink.InferredDirtiness, *dirtinessSource)
				cleanedLinks = append(cleanedLinks, LinkResourceRef{
					Link:        currLink,
					ResourceRef: dirtinessSource,
				})
			}

			for _, link := range branch.Links {
				if *link.FromRes == *currLink.ToRes {
					_, processed := processedLinks[model.GetLinkKey(link)]
					if !processed {
						workQueue = append(workQueue, link)
					}
				}

			}
		}
	}

	return cleanedLinks, nil
}

func (branch *MemBranch) AddResource(rg *model.ResourceGroup, res *model.Resource) (bool, error) {
	tool, ok := branch.Tools[rg.ToolId]
	if !ok {
		tool = map[string]*model.ResourceGroup{}
		branch.Tools[rg.ToolId] = tool
	}

	key := rg.URL
	resourceGroup, ok := tool[key]
	if !ok {
		tool[key] = rg
		resourceGroup = rg
	}
	if res == nil {
		return false, nil
	}

	oldRes, ok := resourceGroup.Resources[res.URL]
	if !ok {
		resourceGroup.Resources[res.URL] = res
		return true, nil
	} else {
		wasDeleted := oldRes.Deleted
		oldRes.Deleted = false
		return wasDeleted, nil
	}

}

func (branch *MemBranch) AddResources(resources []*model.ResourceGroupAndResource) (bool, error) {
	addedSome := false
	for _, res := range resources {
		added, err := branch.AddResource(res.ResourceGroup, res.Resource)
		if err != nil {
			return addedSome, err
		}
		addedSome = addedSome || added
	}
	return addedSome, nil
}

func (branch *MemBranch) AddLink(newLink *model.LinkWithResources) (bool, error) {
	branch.AddResource(newLink.FromResourceGroup, newLink.FromRes)
	branch.AddResource(newLink.ToResourceGroup, newLink.ToRes)

	addMe := newLink.ToLink()
	linkKey := model.GetLinkKey(addMe)
	oldLink, ok := branch.Links[linkKey]
	if ok {
		wasDeleted := oldLink.Deleted
		oldLink.Deleted = false
		return wasDeleted, nil
	} else {
		branch.Links[linkKey] = addMe
		return true, nil
	}
}

func (branch *MemBranch) AddLinks(links []*model.LinkWithResources) (bool, error) {
	addedSome := false
	for _, link := range links {
		added, err := branch.AddLink(link)
		if err != nil {
			return addedSome, err
		}
		addedSome = addedSome || added
	}
	return addedSome, nil
}

func (branch *MemBranch) RemoveResourceRef(rr *model.ResourceRef) (bool, error) {
	tool, ok := branch.Tools[rr.ToolId]
	if !ok {
		return false, nil
	}

	key := rr.ResourceGroupURL
	resourceGroup, ok := tool[key]
	if !ok {
		return false, nil
	}

	res, ok := resourceGroup.Resources[rr.URL]
	if !ok {
		return false, nil
	}

	if res.Deleted {
		return false, nil
	}
	res.Deleted = true
	for _, link := range branch.Links {
		if link.HasFromLinkRef(rr) || link.HasToLinkRef(rr) {
			link.Deleted = true
		}
	}
	return true, nil
}

func (branch *MemBranch) GetResourceGroup(toolId string, URL string) (*model.ResourceGroup, error) {
	tool, ok := branch.Tools[toolId]
	if !ok {
		return nil, errors.New(fmt.Sprintf("no tool %s", toolId))
	}

	resourceGroup, ok := tool[URL]
	if !ok {
		return nil, errors.New(fmt.Sprintf("no resource group %s in tool %s", URL, toolId))
	}
	return resourceGroup, nil
}

func (branch *MemBranch) GetResource(rr *model.ResourceRef, includeDeleted bool) (*model.ResourceGroupAndResource, error) {
	tool, ok := branch.Tools[rr.ToolId]
	if !ok {
		return nil, errors.New(fmt.Sprintf("no tool %s", rr.ToolId))
	}

	key := rr.ResourceGroupURL
	resourceGroup, ok := tool[key]
	if !ok {
		return nil, errors.New(fmt.Sprintf("no resource group %s in tool %s", key, rr.ToolId))
	}

	res, ok := resourceGroup.Resources[rr.URL]
	if !ok {
		return nil, errors.New(fmt.Sprintf("no resource %s in %s %s", rr.URL, rr.ToolId, rr.ResourceGroupURL))
	}

	if res.Deleted && !includeDeleted {
		return nil, errors.New(fmt.Sprintf("resource %s %s %s is deleted",
			rr.ToolId, rr.ResourceGroupURL, rr.URL))
	}
	return &model.ResourceGroupAndResource{
		ResourceGroup: resourceGroup,
		Resource:      res,
	}, nil
}

func (branch *MemBranch) getLinksWithResource(rr *model.ResourceRef, useTo bool) ([]*model.Link, error) {
	links := []*model.Link{}
	for _, link := range branch.Links {
		if link.Deleted {
			continue
		}

		if (!useTo && *link.FromRes == *rr) || (useTo && *link.ToRes == *rr) {
			links = append(links, link)
		}
	}
	return links, nil
}

type LinkWithDepth struct {
	key   model.LinkKey
	link  *model.Link
	depth int
}

func (branch *MemBranch) GetDependencyGraph(rr *model.ResourceRef, upstream bool, maxDepth int) ([]*model.LinkWithResources, error) {
	processedLinks := map[model.LinkKey]bool{}

	resourceLinks, err := branch.getLinksWithResource(rr, upstream)
	if err != nil {
		return nil, err
	}

	workLinks := []LinkWithDepth{}
	for _, link := range resourceLinks {
		workLinks = append(workLinks, LinkWithDepth{
			key:   model.GetLinkKey(link),
			link:  link,
			depth: 1,
		})
	}

	links := []*model.Link{}

	for len(workLinks) > 0 {
		newWorkLinks := []LinkWithDepth{}
		for _, linkWithDepth := range workLinks {
			_, ok := processedLinks[linkWithDepth.key]
			if ok || (maxDepth > 0 && linkWithDepth.depth > maxDepth) {
				continue
			}
			processedLinks[linkWithDepth.key] = true
			links = append(links, linkWithDepth.link)
			searchLink := linkWithDepth.link.ToRes
			if upstream {
				searchLink = linkWithDepth.link.FromRes
			}
			dependencies, err := branch.getLinksWithResource(searchLink, upstream)
			if err != nil {
				continue
			}
			for _, depLink := range dependencies {
				depKey := model.GetLinkKey(depLink)
				_, ok := processedLinks[depKey]
				if !ok {
					newWorkLinks = append(newWorkLinks, LinkWithDepth{
						key:   depKey,
						link:  depLink,
						depth: linkWithDepth.depth + 1,
					})
				}
			}
		}
		workLinks = newWorkLinks
	}

	linksWithResources := []*model.LinkWithResources{}
	for _, link := range links {
		lwr, err := branch.linkToLinkWithResources(link)
		if err != nil {
			continue
		}
		linksWithResources = append(linksWithResources, lwr)
	}
	return linksWithResources, nil
}

func (branch *MemBranch) RemoveLink(delLink *model.Link) (bool, error) {
	linksToDelete := []model.LinkKey{}
	linkWasDeleted := false

	for linkKey, link := range branch.Links {
		if *link.FromRes == *delLink.FromRes && *link.ToRes == *delLink.ToRes {
			linksToDelete = append(linksToDelete, linkKey)
			linkWasDeleted = true
		}
	}

	for _, link := range linksToDelete {
		delete(branch.Links, link)
	}
	return linkWasDeleted, nil
}

func (branch *MemBranch) EditResourceGroup(oldResourceGroup *model.ResourceGroup, newResourceGroup *model.ResourceGroup) error {
	oldTool, ok := branch.Tools[oldResourceGroup.ToolId]
	if !ok {
		return nil
	}

	rg, ok := oldTool[oldResourceGroup.URL]
	if !ok {
		return nil
	}

	rg.Version = newResourceGroup.Version
	rg.ToolId = newResourceGroup.ToolId
	rg.URL = newResourceGroup.URL
	rg.Name = newResourceGroup.Name

	if oldResourceGroup.ToolId != newResourceGroup.ToolId ||
		oldResourceGroup.URL != newResourceGroup.URL {
		delete(oldTool, oldResourceGroup.URL)
		newTool, ok := branch.Tools[newResourceGroup.ToolId]
		if !ok {
			newTool = map[string]*model.ResourceGroup{}
			branch.Tools[newResourceGroup.ToolId] = newTool
		}
		newTool[newResourceGroup.URL] = rg
	}
	return nil
}

func (branch *MemBranch) RemoveResourceGroup(toolId string, URL string) error {
	tool, ok := branch.Tools[toolId]
	if !ok {
		return nil
	}

	delete(tool, URL)
	removeLinks := []model.LinkKey{}
	for linkKey, link := range branch.Links {
		if (link.FromRes.ToolId == toolId && link.FromRes.ResourceGroupURL == URL) ||
			(link.ToRes.ToolId == toolId && link.ToRes.ResourceGroupURL == URL) {
			removeLinks = append(removeLinks, linkKey)
		}
	}
	for _, link := range removeLinks {
		delete(branch.Links, link)
	}
	return nil
}

func (branch *MemBranch) GetResourceGroupVersion(toolId string, URL string) (string, error) {
	tool, ok := branch.Tools[toolId]
	if !ok {
		return "", nil
	}

	rg, ok := tool[URL]
	if !ok {
		return "", nil
	}
	return rg.Version, nil
}

func (branch *MemBranch) GetResourceGroups() ([]*model.ResourceGroup, error) {
	resourceGroups := []*model.ResourceGroup{}
	for _, tool := range branch.Tools {
		for _, rg := range tool {
			resourceGroups = append(resourceGroups, rg)
		}
	}
	return resourceGroups, nil
}

func (branch *MemBranch) GetResourceByRef(rr *model.ResourceRef) (*model.Resource, error) {
	tool, ok := branch.Tools[rr.ToolId]
	if !ok {
		return nil, nil
	}

	rg, ok := tool[rr.ResourceGroupURL]
	if !ok {
		return nil, nil
	}

	r, ok := rg.Resources[rr.URL]
	if !ok {
		return nil, nil
	}
	return r, nil
}

func (branch *MemBranch) IsResourceDeleted(rr *model.ResourceRef) (bool, error) {
	res, err := branch.GetResourceByRef(rr)
	if err != nil {
		return true, err
	}
	if res == nil {
		return true, nil
	}
	return res.Deleted, nil
}

func (branch *MemBranch) GetResources(resPatterns []*model.ResourceRefPattern, includeDeleted bool) ([]*model.ResourceGroupAndResource, error) {
	resources := []*model.ResourceGroupAndResource{}

	patterns := []*patternRegex{}
	for _, pattern := range resPatterns {
		regex, err := regexp.Compile(pattern.URLPattern)
		if err != nil {
			return nil, err
		}
		patterns = append(patterns, &patternRegex{pattern: pattern, regex: regex})
	}

	for toolId, tool := range branch.Tools {
		found := false
		for _, pattern := range patterns {
			if pattern.pattern.ToolId == toolId {
				found = true
				break
			}
		}

		if !found {
			continue
		}

		for _, rg := range tool {
			for _, pattern := range patterns {
				if pattern.pattern.ToolId == toolId &&
					pattern.pattern.ResourceGroupURL == rg.URL {
					for _, res := range rg.Resources {
						if !includeDeleted && res.Deleted {
							continue
						}
						if pattern.regex.Match([]byte(res.URL)) {
							resources = append(resources, &model.ResourceGroupAndResource{
								ResourceGroup: rg,
								Resource:      res,
							})
						}
					}

				}
			}
		}
	}
	return resources, nil
}

func (branch *MemBranch) GetResourcesAsStream(resPatterns []*model.ResourceRefPattern, includeDeleted bool,
	stream ResourceGroupAndResourceStream) error {

	patterns := []*patternRegex{}
	for _, pattern := range resPatterns {
		regex, err := regexp.Compile(pattern.URLPattern)
		if err != nil {
			return err
		}
		patterns = append(patterns, &patternRegex{pattern: pattern, regex: regex})
	}

	for toolId, tool := range branch.Tools {
		found := false
		for _, pattern := range patterns {
			if pattern.pattern.ToolId == toolId {
				found = true
				break
			}
		}

		if !found {
			continue
		}

		for _, rg := range tool {
			for _, pattern := range patterns {
				if pattern.pattern.ToolId == toolId &&
					pattern.pattern.ResourceGroupURL == rg.URL {
					for _, res := range rg.Resources {
						if !includeDeleted && res.Deleted {
							continue
						}
						if pattern.regex.Match([]byte(res.URL)) {
							stream(&model.ResourceGroupAndResource{
								ResourceGroup: rg,
								Resource:      res,
							})
						}
					}

				}
			}
		}
	}
	return nil
}

type linkPatternRegex struct {
	pattern   *model.ResourceLinkPattern
	fromRegex *regexp.Regexp
	toRegex   *regexp.Regexp
}

func (branch *MemBranch) GetLinks(linkPatterns []*model.ResourceLinkPattern) ([]*model.LinkWithResources, error) {
	links := []*model.LinkWithResources{}

	patterns := []*linkPatternRegex{}
	for _, pattern := range linkPatterns {
		fromRegex, err := regexp.Compile(pattern.FromRes.URLPattern)
		if err != nil {
			return nil, err
		}
		toRegex, err := regexp.Compile(pattern.ToRes.URLPattern)
		if err != nil {
			return nil, err
		}
		patterns = append(patterns, &linkPatternRegex{
			pattern:   pattern,
			fromRegex: fromRegex,
			toRegex:   toRegex,
		})
	}

	for _, link := range branch.Links {
		if link.Deleted {
			continue
		}

		for _, pattern := range patterns {
			if link.FromRes.ToolId != pattern.pattern.FromRes.ToolId ||
				link.FromRes.ResourceGroupURL != pattern.pattern.FromRes.ResourceGroupURL ||
				link.ToRes.ToolId != pattern.pattern.ToRes.ToolId ||
				link.ToRes.ResourceGroupURL != pattern.pattern.ToRes.ResourceGroupURL {
				continue
			}

			if pattern.fromRegex.Match([]byte(link.FromRes.URL)) &&
				pattern.toRegex.Match([]byte(link.ToRes.URL)) {
				linkWithResources, err := branch.linkToLinkWithResources(link)
				if err != nil {
					return nil, err
				}
				links = append(links, linkWithResources)
			}
		}
	}
	return links, nil
}

func (branch *MemBranch) GetLinksAsStream(linkPatterns []*model.ResourceLinkPattern, stream LinkStream) error {
	patterns := []*linkPatternRegex{}
	for _, pattern := range linkPatterns {
		fromRegex, err := regexp.Compile(pattern.FromRes.URLPattern)
		if err != nil {
			return err
		}
		toRegex, err := regexp.Compile(pattern.ToRes.URLPattern)
		if err != nil {
			return err
		}
		patterns = append(patterns, &linkPatternRegex{
			pattern:   pattern,
			fromRegex: fromRegex,
			toRegex:   toRegex,
		})
	}

	for _, link := range branch.Links {
		if link.Deleted {
			continue
		}

		for _, pattern := range patterns {
			if link.FromRes.ToolId != pattern.pattern.FromRes.ToolId ||
				link.FromRes.ResourceGroupURL != pattern.pattern.FromRes.ResourceGroupURL ||
				link.ToRes.ToolId != pattern.pattern.ToRes.ToolId ||
				link.ToRes.ResourceGroupURL != pattern.pattern.ToRes.ResourceGroupURL {
				continue
			}

			if pattern.fromRegex.Match([]byte(link.FromRes.URL)) &&
				pattern.toRegex.Match([]byte(link.ToRes.URL)) {
				linkWithResources, err := branch.linkToLinkWithResources(link)
				if err != nil {
					return err
				}
				stream(linkWithResources)
			}
		}
	}
	return nil
}

func (branch *MemBranch) ExpandLinks(linkPatterns []*model.Link) ([]*model.LinkWithResources, error) {
	links := make([]*model.LinkWithResources, len(linkPatterns))
	for _, link := range linkPatterns {
		linkWithResources, err := branch.linkToLinkWithResources(link)
		if err != nil {
			return nil, err
		}
		links = append(links, linkWithResources)
	}
	return links, nil
}

func (branch *MemBranch) GetAllLinks(includeDeleted bool) ([]*model.LinkWithResources, error) {
	links := []*model.LinkWithResources{}
	for _, link := range branch.Links {
		if link.Deleted && !includeDeleted {
			continue
		}
		linkWithResources, err := branch.linkToLinkWithResources(link)
		if err != nil {
			return nil, err
		}
		links = append(links, linkWithResources)
	}
	return links, nil
}

func (branch *MemBranch) GetAllLinksAsStream(includeDeleted bool, stream LinkStream) error {
	for _, link := range branch.Links {
		if link.Deleted && !includeDeleted {
			continue
		}
		linkWithResources, err := branch.linkToLinkWithResources(link)
		if err != nil {
			fmt.Printf("Error trying to expand link %s %s %s -> %s %s %s\n",
				link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL,
				link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL)
			return err
		}
		stream(linkWithResources)
	}
	return nil
}

func (branch *MemBranch) GetDirtyLinks(resourceGroup *model.ResourceGroupKey, withInferred bool) (
	[]*model.LinkWithResources, error) {
	links := []*model.LinkWithResources{}
	for _, link := range branch.Links {
		if link.Deleted {
			continue
		}
		rgRes, err := branch.GetResource(link.ToRes, false)
		if err != nil {
			return nil, err
		}
		if rgRes.ResourceGroup.ToolId == resourceGroup.ToolId &&
			rgRes.ResourceGroup.URL == resourceGroup.URL &&
			(link.Dirty || (withInferred && len(link.InferredDirtiness) > 0)) {
			linkWithResources, err := branch.linkToLinkWithResources(link)
			if err != nil {
				return nil, err
			}
			links = append(links, linkWithResources)
		}
	}
	return links, nil
}

func (branch *MemBranch) GetDirtyLinksAsStream(resourceGroup *model.ResourceGroup, withInferred bool,
	stream LinkStream) error {
	for _, link := range branch.Links {
		if link.Deleted {
			continue
		}
		rgRes, err := branch.GetResource(link.ToRes, false)
		if err != nil {
			return err
		}
		if rgRes.ResourceGroup.ToolId == resourceGroup.ToolId &&
			rgRes.ResourceGroup.URL == resourceGroup.URL &&
			(link.Dirty || (withInferred && len(link.InferredDirtiness) > 0)) {
			linkWithResources, err := branch.linkToLinkWithResources(link)
			if err != nil {
				return err
			}
			stream(linkWithResources)
		}
	}
	return nil
}

func (branch *MemBranch) SaveBranchState() error {
	return branch.DB.saveBranch(branch)
}
