package db

import (
	"database/sql"
	"errors"
	"github.com/go-sql-driver/mysql"
	"go-impl/config"
	"go-impl/model"
	"log"
	"regexp"
	"strconv"
	"strings"
	"sync"
)

type DoltDB struct {
	db          *sql.DB
	poolLock    sync.Mutex
	connections []*sql.DB
	database    string
	branches    map[string]*DoltDBBranch
}

type DoltDBBranch struct {
	name  string
	isTag bool
	db    *DoltDB
	conn  *sql.DB
	lock  sync.Mutex
}

func NewDoltDB() (*DoltDB, error) {
	conn, err := createDBConnection()
	if err != nil {
		return nil, err
	}
	poolSize := config.IntOrDefault(config.GlobalConfig.DBConfig.PoolSize, 10)
	pool := make([]*sql.DB, poolSize)
	for i := range poolSize {
		pool[i], err = createDBConnection()
		if err != nil {
			return nil, err
		}
	}

	db := &DoltDB{
		db:          conn,
		connections: pool,
		database:    config.StringOrDefault(config.GlobalConfig.DBConfig.Database, "depi"),
		branches:    map[string]*DoltDBBranch{},
	}
	mainBranch := NewDoltDBBranch("main", db, false)
	db.branches["main"] = mainBranch

	return db, nil
}

func createDBConnection() (*sql.DB, error) {
	cfg := mysql.NewConfig()
	cfg.Net = "tcp"
	cfg.Addr = config.StringOrDefault(config.GlobalConfig.DBConfig.Host, "127.0.0.1") + ":" +
		strconv.Itoa(config.IntOrDefault(config.GlobalConfig.DBConfig.Port, 3306))
	cfg.User = config.StringOrDefault(config.GlobalConfig.DBConfig.User, "depi")
	cfg.Passwd = config.StringOrDefault(config.GlobalConfig.DBConfig.Password, "depi")
	cfg.DBName = config.StringOrDefault(config.GlobalConfig.DBConfig.Database, "depi")

	db, err := sql.Open("mysql", cfg.FormatDSN())
	if err != nil {
		return nil, err
	}

	return db, nil
}

func (db *DoltDB) getDBConnection() (*sql.DB, error) {
	db.poolLock.Lock()
	defer db.poolLock.Unlock()

	for len(db.connections) > 0 {
		conn := db.connections[len(db.connections)-1]
		db.connections = db.connections[:len(db.connections)-1]

		err := conn.Ping()
		if err == nil {
			return conn, nil
		}
	}

	return db.getDBConnection()
}

func (db *DoltDB) releaseDBConnection(conn *sql.DB) {
	db.poolLock.Lock()
	defer db.poolLock.Unlock()

	db.connections = append(db.connections, conn)
}

func (db *DoltDB) IsTag(name string) (bool, string, error) {
	conn, err := db.getDBConnection()
	if err != nil {
		return false, "", err
	}
	defer db.releaseDBConnection(conn)
	rows, err := conn.Query("select tag_name from dolt_tags where tag_name like ?", name+"|%")
	if err != nil {
		return false, "", err
	}
	defer rows.Close()
	if rows.Next() {
		var tagName string
		err = rows.Scan(&tagName)
		if err != nil {
			return false, "", err
		}
		return true, tagName, nil
	}
	return false, "", nil
}

func (db *DoltDB) GetBranch(name string) (Branch, error) {
	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}
	defer db.releaseDBConnection(conn)

	isTag, _, err := db.IsTag(name)
	if isTag {
		return nil, errors.New("cannot check out a tag")
	}

	_, err = conn.Exec("CALL DOLT_CHECKOUT(?)", name)
	if err != nil {
		return nil, err
	}
	return NewDoltDBBranch(name, db, false), nil
}

func (db *DoltDB) GetTag(name string) (Branch, error) {
	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}
	defer db.releaseDBConnection(conn)

	isTag, _, err := db.IsTag(name)
	if !isTag {
		return nil, errors.New("cannot check out a branch as a tag")
	}

	_, err = conn.Exec("USE ?/?", db.database, name)
	if err != nil {
		return nil, err
	}
	return NewDoltDBBranch(name, db, true), nil
}

func (db *DoltDB) getBranchConn(name string) (*sql.DB, error) {
	isTag, _, err := db.IsTag(name)
	if err != nil {
		return nil, err
	}
	if isTag {
		return nil, errors.New("Cannot check out a tag")
	}

	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}

	_, err = conn.Exec("CALL DOLT_CHECKOUT(?)", name)

	return conn, nil
}

func (db *DoltDB) getTagConn(name string) (*sql.DB, error) {
	isTag, _, err := db.IsTag(name)
	if !isTag {
		return nil, errors.New("Cannot check out a branch as a tag")
	}

	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}

	_, err = conn.Exec("USE ?/?", db.database, name)
	if err != nil {
		return nil, err
	}
	return conn, nil
}

func (db *DoltDB) BranchExists(name string) bool {
	conn, err := db.getDBConnection()
	if err != nil {
		return false
	}
	defer db.releaseDBConnection(conn)

	rows, err := conn.Query("select name from dolt_branches where name=?", name)
	if err != nil {
		return false
	}
	defer rows.Close()
	return rows.Next()
}

func (db *DoltDB) TagExists(name string) bool {
	conn, err := db.getDBConnection()
	if err != nil {
		return false
	}
	defer db.releaseDBConnection(conn)

	rows, err := conn.Query("select tag_name from dolt_tags where tag_name=?", name)
	if err != nil {
		return false
	}
	defer rows.Close()
	return rows.Next()
}

func (db *DoltDB) CreateBranch(name string, fromBranch string) (Branch, error) {
	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}
	defer db.releaseDBConnection(conn)

	_, err = conn.Exec("CALL DOLT_BRANCH(?, ?)", name, fromBranch)
	if err != nil {
		return nil, err
	}
	return NewDoltDBBranch(name, db, false), nil
}

func (db *DoltDB) CreateBranchFromTag(name string, fromTag string) (Branch, error) {
	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}
	defer db.releaseDBConnection(conn)

	_, err = conn.Exec("CALL DOLT_BRANCH(?, ?)", name, fromTag)
	if err != nil {
		return nil, err
	}
	return NewDoltDBBranch(name, db, false), nil
}

func (db *DoltDB) CreateTag(name string, fromBranch string) (Branch, error) {
	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}
	defer db.releaseDBConnection(conn)

	_, err = conn.Exec("CALL DOLT_TAG(?, HEAD)", name)
	if err != nil {
		return nil, err
	}
	return NewDoltDBBranch(name, db, false), nil
}

func (db *DoltDB) GetBranchList() ([]string, error) {
	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}
	defer db.releaseDBConnection(conn)

	branches := []string{}
	rows, err := conn.Query("select name from dolt_branches")
	if err != nil {
		return branches, err
	}
	defer rows.Close()

	for rows.Next() {
		var branch string
		rows.Scan(&branch)
		branches = append(branches, branch)
	}
	return branches, nil
}

func (db *DoltDB) GetTagList() ([]string, error) {
	conn, err := db.getDBConnection()
	if err != nil {
		return nil, err
	}
	defer db.releaseDBConnection(conn)

	tags := []string{}
	rows, err := conn.Query("select tag_name from dolt_tags")
	if err != nil {
		return tags, err
	}
	defer rows.Close()

	for rows.Next() {
		var tag string
		rows.Scan(&tag)
		tags = append(tags, tag)
	}
	return tags, nil
}

func NewDoltDBBranch(name string, db *DoltDB, isTag bool) *DoltDBBranch {
	return &DoltDBBranch{
		name:  name,
		db:    db,
		conn:  nil,
		isTag: isTag,
	}
}

func (d *DoltDBBranch) Lock() {
	d.lock.Lock()
}

func (d *DoltDBBranch) Unlock() {
	d.lock.Unlock()
}

func (d *DoltDBBranch) getConnection() (*sql.DB, error) {
	if d.conn != nil {
		return d.conn, nil
	}

	conn, err := d.db.getBranchConn(d.name)
	if err != nil {
		return nil, err
	}
	return conn, nil
}

func (d *DoltDBBranch) getReadConnection() (*sql.DB, error) {
	return d.db.getBranchConn(d.name)
}

func (d *DoltDBBranch) GetName() string {
	return d.name
}

func (d *DoltDBBranch) commit() error {
	if d.conn == nil {
		return nil
	}

	_, err := d.conn.Exec("CALL DOLT_COMMIT('-a', '--skip-empty', '-m', ?, '--author', ?)",
		"committed", "Mark Wutka <mark.wutka@vanderbilt.edu>")

	defer d.db.releaseDBConnection(d.conn)
	d.conn = nil
	return err
}

func (d *DoltDBBranch) abort() error {
	if d.conn == nil {
		return nil
	}

	_, err := d.conn.Exec("CALL DOLT_REVERT('HEAD')")

	defer d.db.releaseDBConnection(d.conn)
	d.conn = nil
	return err
}

func (d *DoltDBBranch) MarkResourcesClean(resourceRefs []*model.ResourceRef, propagateCleanliness bool) error {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return err
	}
	defer d.db.releaseDBConnection(conn)

	for _, rr := range resourceRefs {
		_, err := conn.Exec("update link set dirty=false where to_tool_id=? and to_rg_url=? and to_url=?",
			rr.ToolId, rr.ResourceGroupURL, rr.URL)
		if err != nil {
			return err
		}
	}
	return d.commit()
}

func (d *DoltDBBranch) cleanDeleted(conn *sql.DB) error {
	_, err := conn.Exec("delete from link where deleted=true and dirty=false")
	if err != nil {
		return err
	}
	rows, err := conn.Query(`select r.tool_id as tool_id, r.rg_url as rg_url, r.url as url from resource r
            where r.deleted=true and not exists (select l.from_url from link l where l.from_tool_id=r.tool_id and
                l.from_rg_url=r.rg_url and l.from_url=r.url)`)
	if err != nil {
		return err
	}
	defer rows.Close()
	resourcesToDelete := []model.ResourceRef{}
	for rows.Next() {
		var toolId, rgURL, URL string
		rows.Scan(&toolId, &rgURL, &URL)
		resourcesToDelete = append(resourcesToDelete,
			model.ResourceRef{ToolId: toolId, ResourceGroupURL: rgURL, URL: URL})
	}

	for _, rr := range resourcesToDelete {
		_, err = conn.Exec("delete from resource where tool_id=? and rg_url=? and url=?",
			rr.ToolId, rr.ResourceGroupURL, rr.URL)
		if err != nil {
			return err
		}
	}
	return nil
}

func (d *DoltDBBranch) MarkLinksClean(links []*model.Link, propagateCleanliness bool) error {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return err
	}
	defer d.db.releaseDBConnection(conn)

	for _, link := range links {
		_, err := conn.Exec("update link set dirty=false where from_tool_id=? and from_rg_url=? and from_url=? and to_tool_id=? and to_rg_url=? and to_url=?",
			link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL,
			link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL)
		if err != nil {
			return err
		}
		if propagateCleanliness {
			_, err = d.markInferredDirtinessCleanEx(link, link.FromRes, propagateCleanliness, conn)
			if err != nil {
				return err
			}
		}
		err = d.cleanDeleted(conn)
		if err != nil {
			return err
		}
	}
	return d.commit()
}

func (d *DoltDBBranch) MarkInferredDirtinessClean(link *model.Link, dirtinessSource *model.ResourceRef, propagateCleanliness bool) ([]LinkResourceRef, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return []LinkResourceRef{}, err
	}
	defer d.db.releaseDBConnection(conn)

	result, err := d.markInferredDirtinessCleanEx(link, dirtinessSource, propagateCleanliness, conn)
	if err != nil {
		d.commit()
	}
	return result, err
}

type simpleLink struct {
	fromToolId, fromRgURL, fromURL string
	toToolId, toRgURL, toURL       string
}

func (d *DoltDBBranch) markInferredDirtinessCleanEx(link *model.Link, dirtinessSource *model.ResourceRef, propagateCleanliness bool,
	conn *sql.DB) ([]LinkResourceRef, error) {

	linksCleaned := []LinkResourceRef{}

	_, err := conn.Exec(`delete from inferred_dirtiness where from_tool_id=? and from_rg_url=? and
		from_url=? and to_tool_id=? and to_rg_url=? and to_url=? and
		source_tool_id=? and source_rg_url=? and source_url=?`,
		link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL,
		link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL,
		dirtinessSource.ToolId, dirtinessSource.ResourceGroupURL, dirtinessSource.URL)
	if err != nil {
		return nil, err
	}
	linksCleaned = append(linksCleaned,
		LinkResourceRef{Link: link, ResourceRef: dirtinessSource})

	if !propagateCleanliness {
		return linksCleaned, nil
	}

	workQueue := []simpleLink{
		simpleLink{
			fromToolId: link.FromRes.ToolId,
			fromRgURL:  link.FromRes.ResourceGroupURL,
			fromURL:    link.FromRes.URL,
			toToolId:   link.ToRes.ToolId,
			toRgURL:    link.ToRes.ResourceGroupURL,
			toURL:      link.ToRes.URL,
		},
	}

	processed := map[simpleLink]bool{}

	for len(workQueue) > 0 {
		currLink := workQueue[0]
		workQueue = workQueue[1:]
		processed[currLink] = true

		rows, err := conn.Query(`select to_tool_id, to_rg_url, to_url from link where
                from_tool_id=? and from_rg_url=? and from_url=?`,
			currLink.toToolId, currLink.toRgURL, currLink.toURL)

		if err != nil {
			return nil, err
		}

		for rows.Next() {
			var toolId, rgURL, URL string
			rows.Scan(&toolId, &rgURL, &URL)
			nextLink := simpleLink{
				fromToolId: currLink.toToolId,
				fromRgURL:  currLink.toRgURL,
				fromURL:    currLink.toURL,
				toToolId:   toolId,
				toRgURL:    rgURL,
				toURL:      URL,
			}

			_, ok := processed[nextLink]
			if !ok {
				workQueue = append(workQueue, nextLink)
			}

			if err != nil {
				rows.Close()
				return nil, err
			}

		}
		rows.Close()

		_, err = conn.Exec(`delete from inferred_dirtiness where from_tool_id=? and from_rg_url=? and
			from_url=? and to_tool_id=? and to_rg_url=? and to_url=? and
			source_tool_id=? and source_rg_url=? and source_url=?`,
			currLink.fromToolId, currLink.fromRgURL, currLink.fromURL,
			currLink.toToolId, currLink.toRgURL, currLink.toURL,
			dirtinessSource.ToolId, dirtinessSource.ResourceGroupURL, dirtinessSource.URL)

		if err != nil {
			return nil, err
		}

		linksCleaned = append(linksCleaned,
			LinkResourceRef{
				Link: &model.Link{
					FromRes: &model.ResourceRef{
						ToolId:           currLink.fromToolId,
						ResourceGroupURL: currLink.fromRgURL,
						URL:              currLink.fromURL,
					},
					ToRes: &model.ResourceRef{
						ToolId:           currLink.toToolId,
						ResourceGroupURL: currLink.toRgURL,
						URL:              currLink.toURL,
					},
				},
				ResourceRef: dirtinessSource,
			})
	}
	return linksCleaned, nil
}

func (d *DoltDBBranch) addResourceExt(rg *model.ResourceGroup, res *model.Resource, conn *sql.DB) (bool, error) {
	_, err := conn.Exec("insert into resource_group (tool_id, url, name, version) values (?,?,?,?) on duplicate key update url=url",
		rg.ToolId, rg.URL, rg.Name, rg.Version)
	if err != nil {
		return false, err
	}
	if res != nil {
		result, err := conn.Exec("insert into resource (tool_id, rg_url, url, name, id, deleted) values (?,?,?,?,?,false) on duplicate key update deleted=false",
			rg.ToolId, rg.URL, res.URL, res.Name, res.Id)
		if err == nil {
			n, _ := result.RowsAffected()
			return n > 0, nil
		}
	}
	return false, err
}
func (d *DoltDBBranch) AddResource(rg *model.ResourceGroup, res *model.Resource) (bool, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return false, err
	}
	defer d.db.releaseDBConnection(conn)

	return d.addResourceExt(rg, res, conn)
}

func (d *DoltDBBranch) AddResourceGroups(resourceGroups []*model.ResourceGroup) (bool, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return false, err
	}
	defer d.db.releaseDBConnection(conn)

	queryBuilder := strings.Builder{}
	lastQueryBuilder := strings.Builder{}
	queryBuilder.WriteString("insert into resource_group (tool_id, url, name, version) values ")
	lastQueryBuilder.WriteString("insert into resource_group (tool_id, url, name, version) values ")

	var lastQuery *sql.Stmt

	numLastResourceGroups := len(resourceGroups) % 1000
	if numLastResourceGroups > 0 {
		for i := range numLastResourceGroups {
			lastQueryBuilder.WriteString("(?,?,?,?)")
			if i < numLastResourceGroups-1 {
				lastQueryBuilder.WriteString(",")
			}
		}
		lastQueryBuilder.WriteString(" on duplicate key update name=name")
		lastQuery, err = conn.Prepare(lastQueryBuilder.String())
		if err != nil {
			return false, err
		}
		defer lastQuery.Close()
	}

	for i := 0; i < 1000; i++ {
		queryBuilder.WriteString("(?,?,?,?)")
		if i < 999 {
			queryBuilder.WriteString(",")
		}
	}
	queryBuilder.WriteString(" on duplicate key update name=name")

	query, err := conn.Prepare(queryBuilder.String())
	if err != nil {
		return false, err
	}
	defer query.Close()

	currAdded := false
	lastVal := 0
	if len(resourceGroups) >= 1000 {
		for i := 0; i < len(resourceGroups); i += 1000 {
			values := []any{}
			for j := 0; j < 1000; j++ {
				values = append(values, resourceGroups[lastVal].ToolId)
				values = append(values, resourceGroups[lastVal].URL)
				values = append(values, resourceGroups[lastVal].Name)
				values = append(values, resourceGroups[lastVal].Version)
				lastVal += 1
			}

			result, err := query.Exec(values...)
			if err != nil {
				return false, err
			}
			n, err := result.RowsAffected()
			currAdded = currAdded || (n > 0)
		}
	}

	if lastQuery != nil {
		values := []any{}
		for i := 0; i < numLastResourceGroups; i++ {
			values = append(values, resourceGroups[lastVal].ToolId)
			values = append(values, resourceGroups[lastVal].URL)
			values = append(values, resourceGroups[lastVal].Name)
			values = append(values, resourceGroups[lastVal].Version)
			lastVal += 1
		}
		result, err := lastQuery.Exec(values...)
		if err != nil {
			return false, err
		}
		n, err := result.RowsAffected()
		currAdded = currAdded || (n > 0)
	}
	return currAdded, nil
}

func (d *DoltDBBranch) AddResources(resources []*model.ResourceGroupAndResource) (bool, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return false, err
	}
	defer d.db.releaseDBConnection(conn)

	queryBuilder := strings.Builder{}
	lastQueryBuilder := strings.Builder{}
	queryBuilder.WriteString("insert into resource (tool_id, rg_url, url, name, id, deleted) values ")
	lastQueryBuilder.WriteString("insert into resource (tool_id, rg_url, url, name, id, deleted) values ")

	var lastQuery *sql.Stmt

	rgs := map[model.ResourceGroupKey]bool{}
	rgsToAdd := []*model.ResourceGroup{}
	for _, rgAndRes := range resources {
		key := rgAndRes.ResourceGroup.GetKey()
		_, ok := rgs[key]
		if !ok {
			rgs[key] = true
			rgsToAdd = append(rgsToAdd, rgAndRes.ResourceGroup)
		}
	}

	_, err = d.AddResourceGroups(rgsToAdd)
	if err != nil {
		return false, err
	}

	numLastResources := len(resources) % 1000
	if numLastResources > 0 {
		for i := range numLastResources {
			lastQueryBuilder.WriteString("(?,?,?,?,?,false)")
			if i < numLastResources-1 {
				lastQueryBuilder.WriteString(",")
			}
		}
		lastQueryBuilder.WriteString(" on duplicate key update name=name ")

		lastQuery, err = conn.Prepare(lastQueryBuilder.String())
		if err != nil {
			return false, err
		}
		defer lastQuery.Close()
	}

	for i := 0; i < 1000; i++ {
		queryBuilder.WriteString("(?,?,?,?,?,false)")
		if i < 999 {
			queryBuilder.WriteString(",")
		}
	}
	queryBuilder.WriteString(" on duplicate key update name=name ")

	query, err := conn.Prepare(queryBuilder.String())
	if err != nil {
		return false, err
	}
	defer query.Close()

	currAdded := false
	lastVal := 0
	if len(resources) >= 1000 {
		for i := 0; i < len(resources); i += 1000 {
			values := []any{}
			for j := 0; j < 1000; j++ {
				values = append(values, resources[lastVal].ResourceGroup.ToolId)
				values = append(values, resources[lastVal].ResourceGroup.URL)
				values = append(values, resources[lastVal].Resource.URL)
				values = append(values, resources[lastVal].Resource.Name)
				values = append(values, resources[lastVal].Resource.Id)
				lastVal += 1
			}

			result, err := query.Exec(values...)
			if err != nil {
				return false, err
			}
			n, err := result.RowsAffected()
			currAdded = currAdded || (n > 0)
		}
	}

	if lastQuery != nil {
		values := []any{}
		for i := 0; i < numLastResources; i++ {
			values = append(values, resources[lastVal].ResourceGroup.ToolId)
			values = append(values, resources[lastVal].ResourceGroup.URL)
			values = append(values, resources[lastVal].Resource.URL)
			values = append(values, resources[lastVal].Resource.Name)
			values = append(values, resources[lastVal].Resource.Id)
			lastVal += 1
		}
		result, err := lastQuery.Exec(values...)
		if err != nil {
			return false, err
		}
		n, err := result.RowsAffected()
		currAdded = currAdded || (n > 0)
	}
	return currAdded, nil
}

func (d *DoltDBBranch) AddLink(newLink *model.LinkWithResources) (bool, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return false, err
	}
	defer d.db.releaseDBConnection(conn)

	_, err = d.addResourceExt(newLink.FromResourceGroup, newLink.FromRes, conn)
	if err != nil {
		return false, err
	}
	_, err = d.addResourceExt(newLink.ToResourceGroup, newLink.ToRes, conn)
	if err != nil {
		return false, err
	}
	result, err := conn.Exec("insert into link (from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url, dirty, deleted, last_clean_version) values (?,?,?,?,?,?,false,false,?) on duplicate key update deleted=false",
		newLink.FromResourceGroup.ToolId, newLink.FromResourceGroup.URL,
		newLink.FromRes.URL, newLink.ToResourceGroup.ToolId, newLink.ToResourceGroup.URL,
		newLink.ToRes.URL, newLink.LastCleanVersion)
	if err == nil {
		n, _ := result.RowsAffected()
		return n > 0, nil
	}
	return false, err
}

func (d *DoltDBBranch) AddLinks(links []*model.LinkWithResources) (bool, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return false, err
	}
	defer d.db.releaseDBConnection(conn)

	currAdded := false

	var lastQuery *sql.Stmt
	numLastLinks := len(links) % 1000

	queryBuilder := strings.Builder{}
	lastQueryBuilder := strings.Builder{}

	queryBuilder.WriteString("insert into link (from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url, dirty, deleted, last_clean_version) values ")
	lastQueryBuilder.WriteString("insert into link (from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url, dirty, deleted, last_clean_version) values ")

	for i := 0; i < 1000; i++ {
		queryBuilder.WriteString("(?,?,?,?,?,?,?,?,?)")
		if i < 999 {
			queryBuilder.WriteString(",")
		}
	}
	queryBuilder.WriteString(" on duplicate key update deleted=false")

	for i := 0; i < numLastLinks; i++ {
		lastQueryBuilder.WriteString("(?,?,?,?,?,?,?,?,?)")
		if i < numLastLinks-1 {
			lastQueryBuilder.WriteString(",")
		}
	}
	lastQueryBuilder.WriteString(" on duplicate key update deleted=false")

	query, err := conn.Prepare(queryBuilder.String())
	if err != nil {
		return false, err
	}
	defer query.Close()

	if numLastLinks > 0 {
		lastQuery, err = conn.Prepare(lastQueryBuilder.String())
		if err != nil {
			return false, err
		}
		defer lastQuery.Close()
	}

	addedResourceGroups := map[model.ResourceGroupKey]bool{}
	resourceGroups := []*model.ResourceGroup{}

	addedResources := map[model.ResourceRef]bool{}
	resources := []*model.ResourceGroupAndResource{}
	for _, newLink := range links {
		key := newLink.FromResourceGroup.GetKey()
		_, ok := addedResourceGroups[key]
		if !ok {
			addedResourceGroups[key] = true
			resourceGroups = append(resourceGroups, newLink.FromResourceGroup)
		}

		key = newLink.ToResourceGroup.GetKey()
		_, ok = addedResourceGroups[key]
		if !ok {
			addedResourceGroups[key] = true
			resourceGroups = append(resourceGroups, newLink.ToResourceGroup)
		}

		rr := *model.NewResourceRefFromRGAndRes(newLink.FromResourceGroup, newLink.FromRes)
		_, ok = addedResources[rr]
		if !ok {
			resources = append(resources, &model.ResourceGroupAndResource{
				ResourceGroup: newLink.FromResourceGroup,
				Resource:      newLink.FromRes,
			})
		}
		rr = *model.NewResourceRefFromRGAndRes(newLink.ToResourceGroup, newLink.ToRes)
		_, ok = addedResources[rr]
		if !ok {
			resources = append(resources, &model.ResourceGroupAndResource{
				ResourceGroup: newLink.ToResourceGroup,
				Resource:      newLink.ToRes,
			})
		}
	}

	if len(resourceGroups) > 0 {
		_, err = d.AddResourceGroups(resourceGroups)
		if err != nil {
			return false, err
		}
	}
	if len(resources) > 0 {
		_, err = d.AddResources(resources)
		if err != nil {
			return false, err
		}
	}

	lastLink := 0
	if len(links) >= 1000 {
		for i := 0; i < len(links); i += 1000 {
			values := []any{}
			for j := 0; j < 1000; j++ {
				values = append(values, links[lastLink].FromResourceGroup.ToolId)
				values = append(values, links[lastLink].FromResourceGroup.URL)
				values = append(values, links[lastLink].FromRes.URL)
				values = append(values, links[lastLink].ToResourceGroup.ToolId)
				values = append(values, links[lastLink].ToResourceGroup.URL)
				values = append(values, links[lastLink].ToRes.URL)
				values = append(values, false)
				values = append(values, false)
				values = append(values, links[lastLink].LastCleanVersion)
				lastLink += 1
			}

			result, err := query.Exec(values...)
			if err != nil {
				return false, err
			}
			n, err := result.RowsAffected()
			if err != nil {
				currAdded = currAdded || (n > 0)
			}
		}
	}

	if numLastLinks > 0 {
		values := []any{}
		for i := 0; i < numLastLinks; i++ {
			values = append(values, links[lastLink].FromResourceGroup.ToolId)
			values = append(values, links[lastLink].FromResourceGroup.URL)
			values = append(values, links[lastLink].FromRes.URL)
			values = append(values, links[lastLink].ToResourceGroup.ToolId)
			values = append(values, links[lastLink].ToResourceGroup.URL)
			values = append(values, links[lastLink].ToRes.URL)
			values = append(values, false)
			values = append(values, false)
			values = append(values, links[lastLink].LastCleanVersion)
			lastLink += 1
		}

		result, err := lastQuery.Exec(values...)
		if err != nil {
			return false, err
		}
		n, err := result.RowsAffected()
		if err != nil {
			currAdded = currAdded || (n > 0)
		}
	}
	return currAdded, nil
}

func (d *DoltDBBranch) RemoveResourceRef(rr *model.ResourceRef) (bool, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return false, err
	}
	defer d.db.releaseDBConnection(conn)

	_, err = conn.Exec("update link set deleted=true where (from_tool_id=? and from_rg_url=? and from_url=?) or (to_tool_id=? and to_rg_url=? and to_url=?)",
		rr.ToolId, rr.ResourceGroupURL, rr.URL,
		rr.ToolId, rr.ResourceGroupURL, rr.URL)

	_, err = conn.Exec(`delete from inferred_link where (from_tool_id=? and from_rg_url=? and from_url=?) or 
		(to_tool_id=? and to_rg_url=? and to_url=?)`,
		rr.ToolId, rr.ResourceGroupURL, rr.URL,
		rr.ToolId, rr.ResourceGroupURL, rr.URL)

	result, err := conn.Exec("update resource set deleted=true where tool_id=? and rg_url=? and url=? and deleted=false",
		rr.ToolId, rr.ResourceGroupURL, rr.URL)
	if err == nil {
		n, _ := result.RowsAffected()
		return n > 0, nil
	}
	return false, err
}

func (d *DoltDBBranch) GetResourceGroup(toolId string, URL string) (*model.ResourceGroup, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	rows, err := conn.Query("select name, version from resource_group where tool_id=? and url=?",
		toolId, URL)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	if rows.Next() {
		var name, version string
		rows.Scan(&name, &version)
		return &model.ResourceGroup{ToolId: toolId, URL: URL, Name: name, Version: version}, nil
	}
	return nil, nil
}

func (d *DoltDBBranch) GetResource(rr *model.ResourceRef, includeDeleted bool) (*model.ResourceGroupAndResource, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	rows, err := conn.Query("select rg.name as rg_name, rg.version as rg_version, r.name as name, id as id from resource r, resource_group rg where r.tool_id=? and r.rg_url=? and r.url=? and r.deleted=false and r.tool_id=rg.tool_id and r.rg_url=rg.url",
		rr.ToolId, rr.ResourceGroupURL, rr.URL)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	if rows.Next() {
		var rgName, rgVersion, name, id string
		rows.Scan(&rgName, &rgVersion, &name, &id)
		return &model.ResourceGroupAndResource{
			ResourceGroup: &model.ResourceGroup{
				ToolId: rr.ToolId, URL: rr.ResourceGroupURL, Name: rgName, Version: rgVersion,
			},
			Resource: &model.Resource{
				URL: rr.URL, Name: name, Id: id,
			},
		}, nil
	}
	return nil, nil
}

func (d *DoltDBBranch) getInferredLinks(fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string) ([]model.InferredDirtinessExt, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	links := []model.InferredDirtinessExt{}
	rows, err := conn.Query(
		"select infd.source_tool_id as source_tool_id, infd.source_rg_url as source_rg_url, "+
			" infd.source_url as source_url, "+
			" infd.source_last_clean_version as source_last_clean_version, "+
			" rg.name as rg_name, rg.version as rg_version, "+
			" res.name as name, res.id as id "+
			" from inferred_dirtiness infd, resource res, resource_group rg "+
			" where infd.from_tool_id=? and infd.from_rg_url=? and "+
			" infd.from_url=? and infd.to_tool_id=? and infd.to_rg_url=? and infd.to_url=? and "+
			" res.tool_id=infd.source_tool_id and res.rg_url=infd.source_rg_url and "+
			" res.url=infd.source_url and rg.tool_id=source_tool_id and rg.url=source_rg_url",
		fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL)
	if err != nil {
		return links, err
	}
	defer rows.Close()

	for rows.Next() {
		var sourceToolId, sourceRgURL, sourceURL, sourceLastCleanVersion string
		var rgName, rgVersion, name, id string

		rows.Scan(&sourceToolId, &sourceRgURL, &sourceURL, &sourceLastCleanVersion,
			&rgName, &rgVersion, &name, &id)

		links = append(links,
			model.InferredDirtinessExt{
				ResourceGroup: &model.ResourceGroup{
					ToolId:  sourceToolId,
					URL:     sourceRgURL,
					Name:    rgName,
					Version: rgVersion,
				},
				Resource: &model.Resource{
					URL:  sourceURL,
					Name: name,
					Id:   id,
				},
				LastCleanVersion: sourceLastCleanVersion,
			})
	}
	return links, nil
}

func (d *DoltDBBranch) getLinksFromResource(rr *model.ResourceRef) ([]*model.LinkWithResources, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	links := []*model.LinkWithResources{}

	rows, err := conn.Query(
		"select l.from_url as from_url, l.to_url as to_url, l.dirty as dirty, "+
			" l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, "+
			" l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
			" l.last_clean_version as last_clean_version, "+
			" fr.name as from_name, fr.id as from_id, "+
			" tr.name as to_name, tr.id as to_id, "+
			" frg.name as from_rg_name, frg.version as from_version, "+
			" trg.name as to_rg_name, trg.version as to_version "+
			" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
			"where from_tool_id=? and from_rg_url=? and from_url=? and "+
			"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
			"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
			"  l.deleted=false and l.from_tool_id=fr.tool_id and "+
			"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
			"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
		rr.ToolId, rr.ResourceGroupURL, rr.URL)
	if err != nil {
		return links, err
	}
	defer rows.Close()

	fetched := map[model.LinkKey]bool{}

	for rows.Next() {
		var fromToolId, fromRgURL, fromURL, fromRgName, fromRgVersion, fromName, fromId string
		var toToolId, toRgURL, toURL, toRgName, toRgVersion, toName, toId string
		var lastCleanVersion string
		var dirty bool
		rows.Scan(&fromURL, &toURL, &dirty, &fromToolId, &fromRgURL, &toToolId, &toRgURL,
			&lastCleanVersion, &fromName, &fromId, &toName, &toId,
			&fromRgName, &fromRgVersion,
			&toRgName, &toRgVersion)

		linkKey := model.LinkKey{
			FromRes: model.ResourceRef{ToolId: fromToolId, ResourceGroupURL: fromRgURL, URL: fromURL},
			ToRes:   model.ResourceRef{ToolId: toToolId, ResourceGroupURL: toRgURL, URL: toURL},
		}

		_, ok := fetched[linkKey]
		if ok {
			continue
		}
		fetched[linkKey] = true

		inferred, err := d.getInferredLinks(fromToolId, fromRgURL, fromURL,
			toToolId, toRgURL, toURL)
		if err != nil {
			return links, err
		}

		links = append(links,
			&model.LinkWithResources{
				FromResourceGroup: &model.ResourceGroup{
					ToolId: fromToolId, URL: fromRgURL, Name: fromRgName, Version: fromRgVersion,
				},
				FromRes: &model.Resource{URL: fromURL, Name: fromName, Id: fromId},
				ToResourceGroup: &model.ResourceGroup{
					ToolId: toToolId, URL: toRgURL, Name: toRgName, Version: toRgVersion,
				},
				ToRes:             &model.Resource{URL: toURL, Name: toName, Id: toId},
				Dirty:             dirty,
				InferredDirtiness: inferred,
			})
	}
	return links, nil

}

func (d *DoltDBBranch) getLinksToResource(rr *model.ResourceRef) ([]*model.LinkWithResources, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	links := []*model.LinkWithResources{}

	rows, err := conn.Query(
		"select l.from_url as from_url, l.to_url as to_url, l.dirty as dirty, "+
			" l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, "+
			" l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
			" l.last_clean_version as last_clean_version, "+
			" fr.name as from_name, fr.id as from_id, "+
			" tr.name as to_name, tr.id as to_id, "+
			" frg.name as from_rg_name, frg.version as from_version, "+
			" trg.name as to_rg_name, trg.version as to_version "+
			" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
			"where to_tool_id=? and to_rg_url=? and to_url=? and "+
			"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
			"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
			"  l.deleted=false and l.from_tool_id=fr.tool_id and "+
			"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
			"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
		rr.ToolId, rr.ResourceGroupURL, rr.URL)
	if err != nil {
		return links, err
	}
	defer rows.Close()

	fetched := map[model.LinkKey]bool{}

	for rows.Next() {
		var fromToolId, fromRgURL, fromURL, fromRgName, fromRgVersion, fromName, fromId string
		var toToolId, toRgURL, toURL, toRgName, toRgVersion, toName, toId string
		var lastCleanVersion string
		var dirty bool
		rows.Scan(&fromURL, &toURL, &dirty, &fromToolId, &fromRgURL, &toToolId, &toRgURL,
			&lastCleanVersion, &fromName, &fromId, &toName, &toId,
			&fromRgName, &fromRgVersion,
			&toRgName, &toRgVersion)

		linkKey := model.LinkKey{
			FromRes: model.ResourceRef{ToolId: fromToolId, ResourceGroupURL: fromRgURL, URL: fromURL},
			ToRes:   model.ResourceRef{ToolId: toToolId, ResourceGroupURL: toRgURL, URL: toURL},
		}

		_, ok := fetched[linkKey]
		if ok {
			continue
		}
		fetched[linkKey] = true

		inferred, err := d.getInferredLinks(fromToolId, fromRgURL, fromURL,
			toToolId, toRgURL, toURL)
		if err != nil {
			return links, err
		}

		links = append(links,
			&model.LinkWithResources{
				FromResourceGroup: &model.ResourceGroup{
					ToolId: fromToolId, URL: fromRgURL, Name: fromRgName, Version: fromRgVersion,
				},
				FromRes: &model.Resource{URL: fromURL, Name: fromName, Id: fromId},
				ToResourceGroup: &model.ResourceGroup{
					ToolId: toToolId, URL: toRgURL, Name: toRgName, Version: toRgVersion,
				},
				ToRes:             &model.Resource{URL: toURL, Name: toName, Id: toId},
				Dirty:             dirty,
				InferredDirtiness: inferred,
			})
	}
	return links, nil

}

type linkAndDepth struct {
	link  *model.LinkWithResources
	depth int
}

func (d *DoltDBBranch) GetDependencyGraph(rr *model.ResourceRef, upstream bool, maxDepth int) ([]*model.LinkWithResources, error) {
	processedLinks := map[model.LinkKey]bool{}

	var workLinks []linkAndDepth
	resourceLinks := []*model.LinkWithResources{}
	var err error

	if upstream {
		resourceLinks, err = d.getLinksToResource(rr)
		if err != nil {
			return nil, err
		}
	} else {
		resourceLinks, err = d.getLinksFromResource(rr)
		if err != nil {
			return nil, err
		}
	}

	for _, link := range resourceLinks {
		workLinks = append(workLinks,
			linkAndDepth{link: link, depth: 1})
	}

	links := []*model.LinkWithResources{}
	for len(workLinks) > 0 {
		newWorkLinks := []linkAndDepth{}
		for _, linkDepth := range workLinks {
			key := model.GetLinkWithResourcesKey(linkDepth.link)
			_, ok := processedLinks[key]
			if !ok && (maxDepth <= 0 || linkDepth.depth <= maxDepth) {
				processedLinks[key] = true
				links = append(links, linkDepth.link)
				if maxDepth <= 0 || linkDepth.depth < maxDepth {
					var dependencies []*model.LinkWithResources
					if upstream {
						searchRes := model.NewResourceRefFromRGAndRes(linkDepth.link.FromResourceGroup,
							linkDepth.link.FromRes)
						dependencies, err = d.getLinksToResource(searchRes)
						if err != nil {
							return nil, err
						}
					} else {
						searchRes := model.NewResourceRefFromRGAndRes(linkDepth.link.ToResourceGroup,
							linkDepth.link.ToRes)
						dependencies, err = d.getLinksFromResource(searchRes)
						if err != nil {
							return nil, err
						}
					}

					for _, link := range dependencies {
						key := model.GetLinkWithResourcesKey(link)
						if _, ok := processedLinks[key]; !ok {
							newWorkLinks = append(newWorkLinks,
								linkAndDepth{link: link, depth: linkDepth.depth + 1})
						}
					}
				}
			}
		}
		workLinks = newWorkLinks
	}
	return links, nil
}

func (d *DoltDBBranch) RemoveLink(delLink *model.Link) (bool, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return false, err
	}
	defer d.db.releaseDBConnection(conn)

	_, err = conn.Exec("update link set deleted=true where from_tool_id=? and from_rg_url=? and from_url=? and to_tool_id=? and to_rg_url=? and to_url=? and deleted=false",
		delLink.FromRes.ToolId, delLink.FromRes.ResourceGroupURL, delLink.FromRes.URL,
		delLink.ToRes.ToolId, delLink.ToRes.ResourceGroupURL, delLink.ToRes.URL)

	if err != nil {
		return false, err
	}

	response, err := conn.Exec("delete inferred_link where (from_tool_id=? and from_rg_url=? and from_url=? and "+
		"to_tool_id=? and to_rg_url=? and to_url=?",
		delLink.FromRes.ToolId, delLink.FromRes.ResourceGroupURL, delLink.FromRes.URL,
		delLink.ToRes.ToolId, delLink.ToRes.ResourceGroupURL, delLink.ToRes.URL)

	if err != nil {
		return false, err
	}
	n, _ := response.RowsAffected()
	return n > 0, nil
}

func (d *DoltDBBranch) GetResourceGroupVersion(toolId string, URL string) (string, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return "", err
	}
	defer d.db.releaseDBConnection(conn)

	rows, err := conn.Query("select version from resource_group where tool_id=? and url=?",
		toolId, URL)
	if err != nil {
		return "", err
	}
	defer rows.Close()
	if rows.Next() {
		var version string
		rows.Scan(&version)
		return version, nil
	}
	return "", nil
}

func (d *DoltDBBranch) GetResourceGroups() ([]*model.ResourceGroup, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	groups := []*model.ResourceGroup{}
	rows, err := conn.Query("select tool_id, url, name, version from resource_group")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	for rows.Next() {
		var toolId, url, name, version string
		rows.Scan(&toolId, &url, &name, &version)
		groups = append(groups, &model.ResourceGroup{
			ToolId: toolId, URL: url, Name: name, Version: version,
		})
	}
	return groups, nil
}

func (d *DoltDBBranch) GetResourceByRef(rr *model.ResourceRef) (*model.Resource, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	rows, err := conn.Query("select name, id, deleted from resource where toolId=? and rg_url=? and url=?",
		rr.ToolId, rr.ResourceGroupURL, rr.URL)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	if rows.Next() {
		var name, id string
		var deleted bool
		rows.Scan(&name, &id, &deleted)
		return &model.Resource{
			URL: rr.URL, Name: name, Id: id, Deleted: deleted,
		}, nil
	}
	return nil, nil
}

func (d *DoltDBBranch) IsResourceDeleted(rr *model.ResourceRef) (bool, error) {
	res, err := d.GetResourceByRef(rr)
	if err != nil {
		return false, err
	}
	return res.Deleted, nil
}

func (d *DoltDBBranch) GetResources(resPatterns []*model.ResourceRefPattern, includeDeleted bool) ([]*model.ResourceGroupAndResource, error) {
	tools := map[string]map[string]bool{}
	patterns := []patternRegex{}

	for _, pattern := range resPatterns {
		tool, ok := tools[pattern.ToolId]
		if !ok {
			tool = map[string]bool{}
			tools[pattern.ToolId] = tool
		}
		tool[pattern.ResourceGroupURL] = true
		regex, err := regexp.Compile(pattern.URLPattern)
		if err != nil {
			return nil, err
		}
		patterns = append(patterns,
			patternRegex{pattern: pattern, regex: regex})
	}

	resources := []*model.ResourceGroupAndResource{}

	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	for toolId, tool := range tools {
		for rg, _ := range tool {
			var rows *sql.Rows
			if includeDeleted {
				rows, err = conn.Query("select r.url as url, r.name as name, r.id as id, rg.name as rg_name, rg.version as version, r.deleted as deleted from resource r, resource_group rg where rg.tool_id=? and rg.url=? and r.tool_id=rg.tool_id and rg.url=r.rg_url ",
					toolId, rg)
				if err != nil {
					return nil, err
				}
			} else {
				rows, err = conn.Query("select r.url as url, r.name as name, r.id as id, rg.name as rg_name, rg.version as version, r.deleted as deleted from resource r, resource_group rg where rg.tool_id=? and rg.url=? and r.tool_id=rg.tool_id and rg.url=r.rg_url and deleted=false",
					toolId, rg)
				if err != nil {
					return nil, err
				}
			}
			defer rows.Close()

			for rows.Next() {
				var url, name, id, rgName, rgVersion string
				var deleted bool
				rows.Scan(&url, &name, &id, &rgName, &rgVersion, &deleted)

				for _, pattern := range patterns {
					if pattern.pattern.ToolId != toolId || pattern.pattern.ResourceGroupURL != rg {
						continue
					}
					if pattern.regex.Match([]byte(url)) {
						resources = append(resources, &model.ResourceGroupAndResource{
							ResourceGroup: &model.ResourceGroup{
								ToolId: toolId, URL: rg, Name: rgName, Version: rgVersion,
							},
							Resource: &model.Resource{
								URL: url, Name: name, Id: id, Deleted: deleted,
							},
						})
					}
				}
			}
		}
	}
	return resources, nil
}

func (d *DoltDBBranch) GetResourcesAsStream(resPatterns []*model.ResourceRefPattern, includeDeleted bool, stream ResourceGroupAndResourceStream) error {
	tools := map[string]map[string]bool{}
	patterns := []patternRegex{}

	for _, pattern := range resPatterns {
		tool, ok := tools[pattern.ToolId]
		if !ok {
			tool = map[string]bool{}
			tools[pattern.ToolId] = tool
		}
		tool[pattern.ResourceGroupURL] = true
		regex, err := regexp.Compile(pattern.URLPattern)
		if err != nil {
			return err
		}
		patterns = append(patterns,
			patternRegex{pattern: pattern, regex: regex})
	}

	conn, err := d.getReadConnection()
	if err != nil {
		return err
	}
	defer d.db.releaseDBConnection(conn)

	for toolId, tool := range tools {
		for rg, _ := range tool {
			var rows *sql.Rows
			if includeDeleted {
				rows, err = conn.Query("select r.url as url, r.name as name, r.id as id, rg.name as rg_name, rg.version as version, r.deleted as deleted from resource r, resource_group rg where rg.tool_id=? and rg.url=? and r.tool_id=rg.tool_id and rg.url=r.rg_url ",
					toolId, rg)
				if err != nil {
					return err
				}
			} else {
				rows, err = conn.Query("select r.url as url, r.name as name, r.id as id, rg.name as rg_name, rg.version as version, r.deleted as deleted from resource r, resource_group rg where rg.tool_id=? and rg.url=? and r.tool_id=rg.tool_id and rg.url=r.rg_url and deleted=false",
					toolId, rg)
				if err != nil {
					return err
				}
			}
			defer rows.Close()

			for rows.Next() {
				var url, name, id, rgName, rgVersion string
				var deleted bool
				rows.Scan(&url, &name, &id, &rgName, &rgVersion, &deleted)

				for _, pattern := range patterns {
					if pattern.pattern.ToolId != toolId || pattern.pattern.ResourceGroupURL != rg {
						continue
					}
					if pattern.regex.Match([]byte(url)) {
						stream(&model.ResourceGroupAndResource{
							ResourceGroup: &model.ResourceGroup{
								ToolId: toolId, URL: rg, Name: rgName, Version: rgVersion,
							},
							Resource: &model.Resource{
								URL: url, Name: name, Id: id, Deleted: deleted,
							},
						})
					}
				}
			}
		}
	}
	return nil
}

func (d *DoltDBBranch) GetLinks(linkPatterns []*model.ResourceLinkPattern) ([]*model.LinkWithResources, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	fetched := map[model.LinkKey]bool{}
	links := []*model.LinkWithResources{}

	for _, pattern := range linkPatterns {
		fromRegex, err := regexp.Compile(pattern.FromRes.URLPattern)
		if err != nil {
			return nil, err
		}
		toRegex, err := regexp.Compile(pattern.ToRes.URLPattern)
		if err != nil {
			return nil, err
		}

		rows, err := conn.Query(
			"select l.from_url as from_url, l.to_url as to_url, l.dirty as dirty, "+
				" l.last_clean_version as last_clean_version, "+
				" fr.name as from_name, fr.id as from_id, "+
				" tr.name as to_name, tr.id as to_id, "+
				" frg.name as from_rg_name, frg.version as from_version, "+
				" trg.name as to_rg_name, trg.version as to_version "+
				" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
				"where from_tool_id=? and from_rg_url=? and to_tool_id=? and "+
				"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
				"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
				"  to_rg_url=? and l.deleted=false and l.from_tool_id=fr.tool_id and "+
				"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
				"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
			pattern.FromRes.ToolId, pattern.FromRes.ResourceGroupURL,
			pattern.ToRes.ToolId, pattern.ToRes.ResourceGroupURL)

		if err != nil {
			return nil, err
		}

		for rows.Next() {
			var fromURL, toURL, lastCleanVersion, fromName, fromId, toName, toId string
			var fromRgName, fromRgVersion, toRgName, toRgVersion string
			var dirty bool

			rows.Scan(&fromURL, &toURL, &dirty, &lastCleanVersion, &fromName, &fromId,
				&toName, &toId, &fromRgName, &fromRgVersion, &toRgName, &toRgVersion)

			key := model.LinkKey{
				FromRes: model.ResourceRef{
					ToolId:           pattern.FromRes.ToolId,
					ResourceGroupURL: pattern.FromRes.ResourceGroupURL,
					URL:              fromURL,
				},
				ToRes: model.ResourceRef{
					ToolId:           pattern.ToRes.ToolId,
					ResourceGroupURL: pattern.ToRes.ResourceGroupURL,
					URL:              toURL,
				},
			}

			_, ok := fetched[key]
			if ok {
				continue
			}
			fetched[key] = true

			if fromRegex.Match([]byte(fromURL)) && toRegex.Match([]byte(toURL)) {
				inferred, err := d.getInferredLinks(pattern.FromRes.ToolId, pattern.FromRes.ResourceGroupURL,
					fromURL, pattern.ToRes.ToolId, pattern.ToRes.ResourceGroupURL, toURL)
				if err != nil {
					rows.Close()
					return nil, err
				}

				links = append(links, &model.LinkWithResources{
					FromResourceGroup: &model.ResourceGroup{
						ToolId: pattern.FromRes.ToolId,
						URL:    pattern.FromRes.ResourceGroupURL,
						Name:   fromRgName, Version: fromRgVersion,
					},
					FromRes: &model.Resource{
						URL: fromURL, Name: fromName, Id: fromId,
					},
					ToResourceGroup: &model.ResourceGroup{
						ToolId: pattern.ToRes.ToolId,
						URL:    pattern.ToRes.ResourceGroupURL,
						Name:   toRgName, Version: fromRgVersion,
					},
					ToRes: &model.Resource{
						URL: toURL, Name: fromName, Id: toId,
					},
					Dirty:             dirty,
					InferredDirtiness: inferred,
				})
			}
		}
		rows.Close()
	}
	return links, nil
}

func (d *DoltDBBranch) GetLinksAsStream(linkPatterns []*model.ResourceLinkPattern, stream LinkStream) error {
	conn, err := d.getReadConnection()
	if err != nil {
		return err
	}
	defer d.db.releaseDBConnection(conn)

	fetched := map[model.LinkKey]bool{}

	for _, pattern := range linkPatterns {
		fromRegex, err := regexp.Compile(pattern.FromRes.URLPattern)
		if err != nil {
			return err
		}
		toRegex, err := regexp.Compile(pattern.ToRes.URLPattern)
		if err != nil {
			return err
		}

		rows, err := conn.Query(
			"select l.from_url as from_url, l.to_url as to_url, l.dirty as dirty, "+
				" l.last_clean_version as last_clean_version, "+
				" fr.name as from_name, fr.id as from_id, "+
				" tr.name as to_name, tr.id as to_id, "+
				" frg.name as from_rg_name, frg.version as from_version, "+
				" trg.name as to_rg_name, trg.version as to_version "+
				" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
				"where from_tool_id=? and from_rg_url=? and to_tool_id=? and "+
				"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
				"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
				"  to_rg_url=? and l.deleted=false and l.from_tool_id=fr.tool_id and "+
				"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
				"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
			pattern.FromRes.ToolId, pattern.FromRes.ResourceGroupURL,
			pattern.ToRes.ToolId, pattern.ToRes.ResourceGroupURL)

		if err != nil {
			return err
		}

		for rows.Next() {
			var fromURL, toURL, lastCleanVersion, fromName, fromId, toName, toId string
			var fromRgName, fromRgVersion, toRgName, toRgVersion string
			var dirty bool

			rows.Scan(&fromURL, &toURL, &dirty, &lastCleanVersion, &fromName, &fromId,
				&toName, &toId, &fromRgName, &fromRgVersion, &toRgName, &toRgVersion)

			key := model.LinkKey{
				FromRes: model.ResourceRef{
					ToolId:           pattern.FromRes.ToolId,
					ResourceGroupURL: pattern.FromRes.ResourceGroupURL,
					URL:              fromURL,
				},
				ToRes: model.ResourceRef{
					ToolId:           pattern.ToRes.ToolId,
					ResourceGroupURL: pattern.ToRes.ResourceGroupURL,
					URL:              toURL,
				},
			}

			_, ok := fetched[key]
			if ok {
				continue
			}
			fetched[key] = true

			if fromRegex.Match([]byte(fromURL)) && toRegex.Match([]byte(toURL)) {
				inferred, err := d.getInferredLinks(pattern.FromRes.ToolId, pattern.FromRes.ResourceGroupURL,
					fromURL, pattern.ToRes.ToolId, pattern.ToRes.ResourceGroupURL, toURL)
				if err != nil {
					rows.Close()
					return err
				}

				stream(&model.LinkWithResources{
					FromResourceGroup: &model.ResourceGroup{
						ToolId: pattern.FromRes.ToolId,
						URL:    pattern.FromRes.ResourceGroupURL,
						Name:   fromRgName, Version: fromRgVersion,
					},
					FromRes: &model.Resource{
						URL: fromURL, Name: fromName, Id: fromId,
					},
					ToResourceGroup: &model.ResourceGroup{
						ToolId: pattern.ToRes.ToolId,
						URL:    pattern.ToRes.ResourceGroupURL,
						Name:   toRgName, Version: fromRgVersion,
					},
					ToRes: &model.Resource{
						URL: toURL, Name: fromName, Id: toId,
					},
					Dirty:             dirty,
					InferredDirtiness: inferred,
				})
			}
		}
		rows.Close()
	}
	return nil
}

func (d *DoltDBBranch) ExpandLinks(linksToExpand []*model.Link) ([]*model.LinkWithResources, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	links := []*model.LinkWithResources{}
	for _, link := range linksToExpand {
		rows, err := conn.Query(
			"select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url,"+
				" l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url,"+
				" l.to_url as to_url, l.dirty as dirty, "+
				" l.last_clean_version as last_clean_version, "+
				" fr.name as from_name, fr.id as from_id, "+
				" tr.name as to_name, tr.id as to_id, "+
				" frg.name as from_rg_name, frg.version as from_version, "+
				" trg.name as to_rg_name, trg.version as to_version "+
				" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
				"where from_tool_id=? and from_rg_url=? and from_url=? and to_tool_id=? and "+
				"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
				"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
				"  to_rg_url=? and to_url=? and l.deleted=false and l.from_tool_id=fr.tool_id and "+
				"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and"+
				"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
			link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL,
			link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL)
		if err != nil {
			return nil, err
		}

		for rows.Next() {
			var fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string
			var dirty bool
			var lastCleanVersion, fromName, fromId, toName, toId string
			var fromRgName, fromRgVersion, toRgName, toRgVersion string

			rows.Scan(&fromToolId, &fromRgURL, &fromURL, &toToolId, &toRgURL, &toURL,
				&dirty, &lastCleanVersion, &fromName, &fromId, &toName, &toId,
				&fromRgName, &fromRgVersion, &toRgName, &toRgVersion)

			inferred, err := d.getInferredLinks(fromToolId, fromRgURL, fromURL,
				toToolId, toRgURL, toURL)
			if err != nil {
				rows.Close()
				return nil, err
			}

			links = append(links, &model.LinkWithResources{
				FromResourceGroup: &model.ResourceGroup{
					ToolId: fromToolId, URL: fromRgURL, Name: fromRgName, Version: fromRgVersion,
				},
				FromRes: &model.Resource{
					URL: fromURL, Name: fromName, Id: fromId,
				},
				ToResourceGroup: &model.ResourceGroup{
					ToolId: toToolId, URL: fromRgURL, Name: toRgName, Version: toRgVersion,
				},
				ToRes: &model.Resource{
					URL: toURL, Name: fromName, Id: toId,
				},
				Dirty: dirty, InferredDirtiness: inferred,
			})
		}
		rows.Close()
	}
	return links, nil
}

func (d *DoltDBBranch) GetAllLinks(includeDeleted bool) ([]*model.LinkWithResources, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	deletedPart := ""
	if !includeDeleted {
		deletedPart = " and l.deleted=False"
	}

	rows, err := conn.Query(
		"select rg1.tool_id as from_tool_id, rg1.name as from_rg_name, rg1.url as from_rg_url, " +
			"   rg1.version as from_rg_version, r1.name as from_name, " +
			"   r1.id as from_id, r1.url as from_url, r1.deleted as from_deleted, " +
			"   rg2.tool_id as to_tool_id, rg2.name as to_rg_name, rg2.url as to_rg_url, " +
			"   rg2.version as to_rg_version, r2.name as to_name, r2.id as to_id, r2.url as to_url, " +
			"   r2.deleted as to_deleted, l.dirty as dirty, l.last_clean_version as last_clean_version, " +
			"   l.deleted as deleted " +
			"   from link l, resource_group rg1, resource_group rg2, " +
			"   resource r1, resource r2  " +
			" where l.from_tool_id = rg1.tool_id and l.from_rg_url=rg1.url " +
			"   and l.from_tool_id=r1.tool_id and l.from_rg_url=r1.rg_url " +
			"   and l.from_url=r1.url and l.to_tool_id=rg2.tool_id " +
			deletedPart +
			"   and l.to_rg_url=rg2.url and l.to_tool_id=r2.tool_id " +
			"   and l.to_rg_url=r2.rg_url and l.to_url=r2.url ")

	if err != nil {
		return nil, err
	}
	defer rows.Close()

	fetched := map[model.LinkKey]bool{}
	links := []*model.LinkWithResources{}

	for rows.Next() {
		var fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string
		var dirty, deleted, fromDeleted, toDeleted bool
		var lastCleanVersion, fromName, fromId, toName, toId string
		var fromRgName, fromRgVersion, toRgName, toRgVersion string

		rows.Scan(&fromToolId, &fromRgName, &fromRgURL, &fromRgVersion,
			&fromName, &fromId, &fromURL, &fromDeleted, &toToolId, &toRgName,
			&toRgURL, &toRgVersion, &toName, &toId, &toURL,
			&toDeleted, &dirty, &lastCleanVersion, &deleted)
		key := model.LinkKey{
			FromRes: model.ResourceRef{
				ToolId:           fromToolId,
				ResourceGroupURL: fromRgURL,
				URL:              fromURL,
			},
			ToRes: model.ResourceRef{
				ToolId:           toToolId,
				ResourceGroupURL: toRgURL,
				URL:              toURL,
			},
		}

		_, ok := fetched[key]
		if ok {
			continue
		}
		fetched[key] = true
		inferred, err := d.getInferredLinks(fromToolId, fromRgURL, fromURL,
			toToolId, toRgURL, toURL)
		if err != nil {
			return nil, err
		}

		links = append(links, &model.LinkWithResources{
			FromResourceGroup: &model.ResourceGroup{
				ToolId: fromToolId,
				URL:    fromRgURL,
				Name:   fromRgName, Version: fromRgVersion,
			},
			FromRes: &model.Resource{
				URL: fromURL, Name: fromName, Id: fromId, Deleted: fromDeleted,
			},
			ToResourceGroup: &model.ResourceGroup{
				ToolId: toToolId,
				URL:    toRgURL,
				Name:   toRgName, Version: fromRgVersion,
			},
			ToRes: &model.Resource{
				URL: toURL, Name: fromName, Id: toId, Deleted: toDeleted,
			},
			Dirty:             dirty,
			Deleted:           deleted,
			InferredDirtiness: inferred,
		})
	}
	return links, nil
}

func (d *DoltDBBranch) GetAllLinksAsStream(includeDeleted bool, stream LinkStream) error {
	conn, err := d.getReadConnection()
	if err != nil {
		return err
	}
	defer d.db.releaseDBConnection(conn)

	deletedPart := ""
	if !includeDeleted {
		deletedPart = " and l.deleted=False"
	}

	rows, err := conn.Query(
		"select rg1.tool_id as from_tool_id, rg1.name as from_rg_name, rg1.url as from_rg_url, " +
			"   rg1.version as from_rg_version, r1.name as from_name, " +
			"   r1.id as from_id, r1.url as from_url, r1.deleted as from_deleted, " +
			"   rg2.tool_id as to_tool_id, rg2.name as to_rg_name, rg2.url as to_rg_url, " +
			"   rg2.version as to_rg_version, r2.name as to_name, r2.id as to_id, r2.url as to_url, " +
			"   r2.deleted as to_deleted, l.dirty as dirty, l.last_clean_version as last_clean_version, " +
			"   l.deleted as deleted " +
			"   from link l, resource_group rg1, resource_group rg2, " +
			"   resource r1, resource r2  " +
			" where l.from_tool_id = rg1.tool_id and l.from_rg_url=rg1.url " +
			"   and l.from_tool_id=r1.tool_id and l.from_rg_url=r1.rg_url " +
			"   and l.from_url=r1.url and l.to_tool_id=rg2.tool_id " +
			deletedPart +
			"   and l.to_rg_url=rg2.url and l.to_tool_id=r2.tool_id " +
			"   and l.to_rg_url=r2.rg_url and l.to_url=r2.url ")

	if err != nil {
		log.Printf("Error reading links: %+v", err)
		return err
	}
	defer rows.Close()

	fetched := map[model.LinkKey]bool{}

	for rows.Next() {
		var fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string
		var dirty, deleted, fromDeleted, toDeleted bool
		var lastCleanVersion, fromName, fromId, toName, toId string
		var fromRgName, fromRgVersion, toRgName, toRgVersion string

		rows.Scan(&fromToolId, &fromRgName, &fromRgURL, &fromRgVersion,
			&fromName, &fromId, &fromURL, &fromDeleted, &toToolId, &toRgName,
			&toRgURL, &toRgVersion, &toName, &toId, &toURL,
			&toDeleted, &dirty, &lastCleanVersion, &deleted)
		key := model.LinkKey{
			FromRes: model.ResourceRef{
				ToolId:           fromToolId,
				ResourceGroupURL: fromRgURL,
				URL:              fromURL,
			},
			ToRes: model.ResourceRef{
				ToolId:           toToolId,
				ResourceGroupURL: toRgURL,
				URL:              toURL,
			},
		}

		_, ok := fetched[key]
		if ok {
			continue
		}
		fetched[key] = true
		inferred, err := d.getInferredLinks(fromToolId, fromRgURL, fromURL,
			toToolId, toRgURL, toURL)
		if err != nil {
			return err
		}

		stream(&model.LinkWithResources{
			FromResourceGroup: &model.ResourceGroup{
				ToolId: fromToolId,
				URL:    fromRgURL,
				Name:   fromRgName, Version: fromRgVersion,
			},
			FromRes: &model.Resource{
				URL: fromURL, Name: fromName, Id: fromId, Deleted: fromDeleted,
			},
			ToResourceGroup: &model.ResourceGroup{
				ToolId: toToolId,
				URL:    toRgURL,
				Name:   toRgName, Version: fromRgVersion,
			},
			ToRes: &model.Resource{
				URL: toURL, Name: fromName, Id: toId, Deleted: toDeleted,
			},
			Dirty:             dirty,
			InferredDirtiness: inferred,
			Deleted:           deleted,
		})
	}
	return nil
}

func (d *DoltDBBranch) GetDirtyLinks(resourceGroup *model.ResourceGroupKey, withInferred bool) ([]*model.LinkWithResources, error) {
	conn, err := d.getReadConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	var rows *sql.Rows
	if !withInferred {
		rows, err = conn.Query(
			"select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, "+
				" l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
				" l.to_url as to_url, l.dirty as dirty, "+
				" l.last_clean_version as last_clean_version, "+
				" fr.name as from_name, fr.id as from_id, "+
				" tr.name as to_name, tr.id as to_id, "+
				" frg.name as from_rg_name, frg.version as from_version, "+
				" trg.name as to_rg_name, trg.version as to_version "+
				" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
				"where to_tool_id=? and to_rg_url=? and "+
				"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
				"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
				"  l.deleted=false and l.from_tool_id=fr.tool_id and "+
				"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and "+
				"  l.dirty=true and "+
				"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
			resourceGroup.ToolId, resourceGroup.URL)
	} else {
		rows, err = conn.Query(
			"select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, "+
				" l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
				" l.to_url as to_url, l.dirty as dirty, "+
				" l.last_clean_version as last_clean_version, "+
				" fr.name as from_name, fr.id as from_id, "+
				" tr.name as to_name, tr.id as to_id, "+
				" frg.name as from_rg_name, frg.version as from_version, "+
				" trg.name as to_rg_name, trg.version as to_version "+
				" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
				"where to_tool_id=? and to_rg_url=? and "+
				"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
				"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
				"  l.deleted=false and l.from_tool_id=fr.tool_id and "+
				"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and "+
				"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url and "+
				"  (l.dirty=true or "+
				"  exists(select infd.from_tool_id from inferred_dirtiness infd where "+
				"  infd.from_tool_id=l.from_tool_id and infd.from_rg_url=l.from_rg_url and "+
				"  infd.from_url=l.from_url and infd.to_tool_id=l.to_tool_id and "+
				"  infd.to_rg_url=l.to_rg_url and infd.to_url=l.to_url))",
			resourceGroup.ToolId, resourceGroup.URL)

	}
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	fetched := map[model.LinkKey]bool{}
	links := []*model.LinkWithResources{}

	for rows.Next() {
		var fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string
		var dirty, deleted bool
		var lastCleanVersion, fromName, fromId, toName, toId string
		var fromRgName, fromRgVersion, toRgName, toRgVersion string

		rows.Scan(&fromToolId, &fromRgURL, &fromURL, &toToolId, &toRgURL, &toURL,
			&deleted, &lastCleanVersion, &fromName, &fromId, &toName, &toId,
			&fromRgName, &fromRgVersion, &toRgName, &toRgVersion)

		key := model.LinkKey{
			FromRes: model.ResourceRef{
				ToolId:           fromToolId,
				ResourceGroupURL: fromRgURL,
				URL:              fromURL,
			},
			ToRes: model.ResourceRef{
				ToolId:           toToolId,
				ResourceGroupURL: toRgURL,
				URL:              toURL,
			},
		}

		_, ok := fetched[key]
		if ok {
			continue
		}
		fetched[key] = true
		inferred, err := d.getInferredLinks(fromToolId, fromRgURL, fromURL,
			toToolId, toRgURL, toURL)
		if err != nil {
			return nil, err
		}

		links = append(links, &model.LinkWithResources{
			FromResourceGroup: &model.ResourceGroup{
				ToolId: fromToolId,
				URL:    fromRgURL,
				Name:   fromRgName, Version: fromRgVersion,
			},
			FromRes: &model.Resource{
				URL: fromURL, Name: fromName, Id: fromId,
			},
			ToResourceGroup: &model.ResourceGroup{
				ToolId: toToolId,
				URL:    toRgURL,
				Name:   toRgName, Version: toRgVersion,
			},
			ToRes: &model.Resource{
				URL: toURL, Name: toName, Id: toId,
			},
			Dirty:             dirty,
			InferredDirtiness: inferred,
		})
	}
	return links, nil
}

func (d *DoltDBBranch) GetDirtyLinksAsStream(resourceGroup *model.ResourceGroup, withInferred bool, stream LinkStream) error {
	conn, err := d.getReadConnection()
	if err != nil {
		return err
	}
	defer d.db.releaseDBConnection(conn)

	var rows *sql.Rows
	if withInferred {
		rows, err = conn.Query(
			"select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, "+
				" l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
				" l.to_url as to_url, l.dirty as dirty, "+
				" l.last_clean_version as last_clean_version, "+
				" fr.name as from_name, fr.id as from_id, "+
				" tr.name as to_name, tr.id as to_id, "+
				" frg.name as from_rg_name, frg.version as from_version, "+
				" trg.name as to_rg_name, trg.version as to_version "+
				" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
				"where to_tool_id=? and to_rg_url=? and "+
				"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
				"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
				"  l.deleted=false and l.from_tool_id=fr.tool_id and "+
				"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and "+
				"  l.dirty=true and "+
				"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url",
			resourceGroup.ToolId, resourceGroup.URL)
	} else {
		rows, err = conn.Query(
			"select l.from_tool_id as from_tool_id, l.from_rg_url as from_rg_url, "+
				" l.from_url as from_url, l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url, "+
				" l.to_url as to_url, l.dirty as dirty, "+
				" l.last_clean_version as last_clean_version, "+
				" fr.name as from_name, fr.id as from_id, "+
				" tr.name as to_name, tr.id as to_id, "+
				" frg.name as from_rg_name, frg.version as from_version, "+
				" trg.name as to_rg_name, trg.version as to_version "+
				" from link l, resource_group frg, resource_group trg, resource fr, resource tr "+
				"where to_tool_id=? and to_rg_url=? and "+
				"  l.from_tool_id = frg.tool_id and l.from_rg_url = frg.url and "+
				"  l.to_tool_id = trg.tool_id and l.to_rg_url = trg.url and "+
				"  l.deleted=false and l.from_tool_id=fr.tool_id and "+
				"  l.from_rg_url=fr.rg_url and l.from_url=fr.url and "+
				"  l.dirty=true and "+
				"  l.to_tool_id=tr.tool_id and l.to_rg_url=tr.rg_url and l.to_url=tr.url and "+
				"  exists(select infd.from_tool_id from inferred_dirtiness infd where "+
				"  infd.from_tool_id=l.from_tool_id and infd.from_rg_url=l.from_rg_url and "+
				"  infd.from_url=l.from_url and infd.to_tool_id=l.to_tool_id and "+
				"  infd.to_rg_url=l.to_rg_url and infd.to_url=l.to_url)",
			resourceGroup.ToolId, resourceGroup.URL)

	}
	if err != nil {
		return err
	}
	defer rows.Close()

	fetched := map[model.LinkKey]bool{}

	for rows.Next() {
		var fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string
		var dirty, deleted bool
		var lastCleanVersion, fromName, fromId, toName, toId string
		var fromRgName, fromRgVersion, toRgName, toRgVersion string

		rows.Scan(&fromToolId, &fromRgURL, &fromURL, &toToolId, &toRgURL, &toURL,
			&deleted, &lastCleanVersion, &fromName, &fromId, &toName, &toId,
			&fromRgName, &fromRgVersion, &toRgName, &toRgVersion)

		key := model.LinkKey{
			FromRes: model.ResourceRef{
				ToolId:           fromToolId,
				ResourceGroupURL: fromRgURL,
				URL:              fromURL,
			},
			ToRes: model.ResourceRef{
				ToolId:           toToolId,
				ResourceGroupURL: toRgURL,
				URL:              toURL,
			},
		}

		_, ok := fetched[key]
		if ok {
			continue
		}
		fetched[key] = true
		inferred, err := d.getInferredLinks(fromToolId, fromRgURL, fromURL,
			toToolId, toRgURL, toURL)
		if err != nil {
			return err
		}

		stream(&model.LinkWithResources{
			FromResourceGroup: &model.ResourceGroup{
				ToolId: fromToolId,
				URL:    fromRgURL,
				Name:   fromRgName, Version: fromRgVersion,
			},
			FromRes: &model.Resource{
				URL: fromURL, Name: fromName, Id: fromId,
			},
			ToResourceGroup: &model.ResourceGroup{
				ToolId: toToolId,
				URL:    toRgURL,
				Name:   toRgName, Version: toRgVersion,
			},
			ToRes: &model.Resource{
				URL: toURL, Name: toName, Id: toId,
			},
			Dirty:             dirty,
			InferredDirtiness: inferred,
		})
	}
	return nil
}

func makePathMatch(toolId, url, fieldName string) (string, []any) {
	tool, ok := config.GlobalConfig.ToolConfig[toolId]
	if !ok {
		return "", nil
	}
	pathSep := tool.PathSeparator
	parts := strings.Split(url, pathSep)
	partsAcc := ""
	paramsPos := []string{}
	params := []any{}
	for i, p := range parts {
		if len(p) == 0 {
			continue
		}
		paramsPos = append(paramsPos, fieldName+"=?")
		partsAcc = partsAcc + pathSep + p
		if i < len(parts)-1 {
			params = append(params, partsAcc+pathSep)
		} else {
			params = append(params, partsAcc)
		}
	}
	return "(" + strings.Join(paramsPos, " or ") + ")", params
}

func (d *DoltDBBranch) addInferredDirtiness(startingToToolId, startingToRgURL, startingToURL string,
	sourceToolId, sourceRgURL, sourceURL, lastCleanVersion string, conn *sql.DB) error {
	workingSet := []model.ResourceRef{
		model.ResourceRef{ToolId: startingToToolId, ResourceGroupURL: startingToRgURL, URL: startingToURL},
	}
	processed := map[model.ResourceRef]bool{}

	for len(workingSet) > 0 {
		rr := workingSet[len(workingSet)-1]
		workingSet = workingSet[:len(workingSet)-1]

		processed[rr] = true

		rows, err := conn.Query("select to_tool_id, to_rg_url, to_url from link where "+
			" from_tool_id=? and from_rg_url=? and from_url=?",
			rr.ToolId, rr.ResourceGroupURL, rr.URL)

		if err != nil {
			return err
		}

		inserts := [][]any{}

		for rows.Next() {
			var toToolId, toRgURL, toURL string
			rows.Scan(&toToolId, &toRgURL, &toURL)

			nextRR := model.ResourceRef{ToolId: toToolId, ResourceGroupURL: toRgURL, URL: toURL}
			_, ok := processed[nextRR]
			if !ok {
				workingSet = append(workingSet, nextRR)
				inserts = append(inserts,
					[]any{rr.ToolId, rr.ResourceGroupURL, rr.URL, toToolId, toRgURL, toURL, sourceToolId, sourceRgURL,
						sourceURL, lastCleanVersion})
			}
		}
		rows.Close()

		for _, insert := range inserts {
			_, err = conn.Exec("insert into inferred_dirtiness (from_tool_id, from_rg_url, from_url, "+
				" to_tool_id, to_rg_url, to_url, source_tool_id, source_rg_url, source_url,"+
				" source_last_clean_version) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "+
				" on duplicate key update from_tool_id=from_tool_id",
				insert...)
			if err != nil {
				return err
			}
		}
	}
	return nil
}

func (d *DoltDBBranch) UpdateResourceGroup(resourceGroupChange *model.ResourceGroupChange) ([]*model.Link, error) {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return nil, err
	}
	defer d.db.releaseDBConnection(conn)

	rows, err := conn.Query("select version as last_clean_version from resource_group where tool_id=? and url=?",
		resourceGroupChange.ToolId, resourceGroupChange.URL)
	if err != nil {
		return nil, err
	}

	if !rows.Next() {
		rows.Close()
		return []*model.Link{}, nil
	}

	var lastCleanVersion string

	rows.Scan(&lastCleanVersion)
	rows.Close()

	_, err = conn.Exec("update resource_group set version=? where tool_id=? and url=?",
		resourceGroupChange.Version, resourceGroupChange.ToolId, resourceGroupChange.URL)
	if err != nil {
		return nil, err
	}

	groupsToUpdate := []*model.Link{}

	for _, resChange := range resourceGroupChange.Resources {
		if resChange.ChangeType == model.ChangeType_Added || resChange.ChangeType == model.ChangeType_Modified {
			pathMatchStr, pathParams := makePathMatch(resourceGroupChange.ToolId, resChange.URL, "from_url")
			sqlParamList := append([]any{resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL},
				pathParams...)

			rows, err := conn.Query(
				"select from_tool_id, from_rg_url, from_url, to_tool_id, to_rg_url, to_url  "+
					"    from link "+
					"where "+
					"   from_tool_id=? and from_rg_url=? and dirty=false and (from_url = ? or "+
					pathMatchStr+")", sqlParamList...)

			if err != nil {
				log.Printf("Error searching for updated links: %+v\n", err)
				return nil, err
			}
			added := map[model.LinkKey]bool{}
			for rows.Next() {
				var fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string
				rows.Scan(&fromToolId, &fromRgURL, &fromURL, &toToolId, &toRgURL, &toURL)

				link := &model.Link{
					FromRes: &model.ResourceRef{ToolId: fromToolId, ResourceGroupURL: fromRgURL, URL: fromURL},
					ToRes:   &model.ResourceRef{ToolId: toToolId, ResourceGroupURL: toRgURL, URL: toURL},
					Dirty:   true,
				}
				key := model.GetLinkKey(link)

				_, ok := added[key]
				if ok {
					continue
				}
				added[key] = true

				groupsToUpdate = append(groupsToUpdate, link)
				err = d.addInferredDirtiness(link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL,
					resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL,
					lastCleanVersion, conn)
				if err != nil {
					rows.Close()
					return nil, err
				}
			}
			rows.Close()
			if len(added) > 0 {
				for key := range added {
					log.Printf("Marking link as dirty %+v", key)
					_, err = conn.Exec("update link set dirty=true where from_tool_id=? and from_rg_url=? and from_url=?",
						key.FromRes.ToolId, key.FromRes.ResourceGroupURL, key.FromRes.URL)
					if err != nil {
						return nil, err
					}
				}
			}
		}

		if resChange.ChangeType == model.ChangeType_Renamed ||
			(resChange.ChangeType == model.ChangeType_Modified &&
				(resChange.URL != resChange.NewURL ||
					resChange.Name != resChange.NewName ||
					resChange.Id != resChange.NewId)) {

			pathMatchStr, pathParams := makePathMatch(resourceGroupChange.ToolId, resChange.URL, "from_url")
			resPathMatchStr, resPathParams := makePathMatch(resourceGroupChange.ToolId, resChange.URL, "res.url")
			sqlParamList := append([]any{resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL},
				pathParams...)
			sqlParamList = append(sqlParamList, resPathParams...)

			rows, err := conn.Query("select l.from_tool_id as from_tool_id,"+
				"l.from_rg_url as from_rg_url, l.from_url as from_url,"+
				"l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url,"+
				"l.to_url as to_url from link l, resource res where l.dirty=false and "+
				"l.from_tool_id=? and l.from_rg_url=? and (l.from_url = ? or "+
				pathMatchStr+
				") and "+
				"res.tool_id = l.from_tool_id and res.rg_url = l.from_rg_url and "+
				"(res.url = l.from_url or "+resPathMatchStr+")",
				sqlParamList...)
			if err != nil {
				return nil, err
			}
			for rows.Next() {
				var fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string
				rows.Scan(&fromToolId, &fromRgURL, &fromURL, &toToolId, &toRgURL, &toURL)

				link := &model.Link{
					FromRes: &model.ResourceRef{ToolId: fromToolId, ResourceGroupURL: fromRgURL, URL: resChange.NewURL},
					ToRes:   &model.ResourceRef{ToolId: toToolId, ResourceGroupURL: toRgURL, URL: toURL},
					Dirty:   true,
				}

				groupsToUpdate = append(groupsToUpdate, link)
				if resChange.ChangeType == model.ChangeType_Renamed {
					err = d.addInferredDirtiness(link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL,
						resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL,
						lastCleanVersion, conn)
					if err != nil {
						rows.Close()
						return nil, err
					}
				}
			}
			rows.Close()

			_, err = conn.Exec("update link set from_url=? where from_tool_id=? and from_rg_url=? and from_url=?",
				resChange.NewURL, resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL)
			if err != nil {
				return nil, err
			}

			_, err = conn.Exec("update link set to_url=? where to_tool_id=? and to_rg_url=? and to_url=?",
				resChange.NewURL, resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL)
			if err != nil {
				return nil, err
			}

			_, err = conn.Exec("update resource set id=?, name=?, url=? where tool_id=? and rg_url=? and url=?",
				resChange.NewId, resChange.NewName, resChange.NewURL,
				resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL)
			if err != nil {
				return nil, err
			}
		} else if resChange.ChangeType == model.ChangeType_Removed {
			pathMatchStr, pathParams := makePathMatch(resourceGroupChange.ToolId, resChange.URL, "from_url")
			resPathMatchStr, resPathParams := makePathMatch(resourceGroupChange.ToolId, resChange.URL, "res.url")
			sqlParamList := append([]any{resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL},
				pathParams...)
			sqlParamList = append(sqlParamList, resPathParams...)

			rows, err := conn.Query("select l.from_tool_id as from_tool_id,"+
				"l.from_rg_url as from_rg_url, l.from_url as from_url,"+
				"l.to_tool_id as to_tool_id, l.to_rg_url as to_rg_url,"+
				"l.to_url as to_url from link l, resource res where l.dirty=false and "+
				"l.from_tool_id=? and l.from_rg_url=? and (l.from_url = ? or "+
				pathMatchStr+
				") and "+
				"res.tool_id = l.from_tool_id and res.rg_url = l.from_rg_url and "+
				"(res.url = l.from_url or "+resPathMatchStr+")",
				sqlParamList...)
			if err != nil {
				return nil, err
			}

			linkAndOld := [][]string{}

			for rows.Next() {
				var fromToolId, fromRgURL, fromURL, toToolId, toRgURL, toURL string
				rows.Scan(&fromToolId, &fromRgURL, &fromURL, &toToolId, &toRgURL, &toURL)

				link := &model.Link{
					FromRes: &model.ResourceRef{ToolId: fromToolId, ResourceGroupURL: fromRgURL, URL: resChange.NewURL},
					ToRes:   &model.ResourceRef{ToolId: toToolId, ResourceGroupURL: toRgURL, URL: toURL},
					Dirty:   true,
				}

				groupsToUpdate = append(groupsToUpdate, link)
				linkAndOld = append(linkAndOld, []string{link.FromRes.ToolId, link.FromRes.ResourceGroupURL, fromURL})

				err = d.addInferredDirtiness(link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL,
					resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL,
					lastCleanVersion, conn)
				if err != nil {
					return nil, err
				}
			}
			rows.Close()

			_, err = conn.Exec("update link set deleted=true, dirty=true where from_tool_id=? and from_rg_url=? and from_url=?",
				resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL)
			if err != nil {
				return nil, err
			}

			_, err = conn.Exec("delete from link where to_tool_id=? and to_rg_url=? and to_url=?",
				resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL)
			if err != nil {
				return nil, err
			}

			_, err = conn.Exec("update resource set deleted=true where tool_id=? and rg_url=? and url=?",
				resourceGroupChange.ToolId, resourceGroupChange.URL, resChange.URL)
			if err != nil {
				return nil, err
			}

			for _, oldLink := range linkAndOld {
				_, err = conn.Exec("update link set dirty=true where from_tool_id=? and from_rg_url=? and from_url=?",
					oldLink[0], oldLink[1], oldLink[2])
				if err != nil {
					return nil, err
				}
			}
		}
	}
	return groupsToUpdate, d.SaveBranchState()
}

func (d *DoltDBBranch) EditResourceGroup(oldResourceGroup *model.ResourceGroup, newResourceGroup *model.ResourceGroup) error {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return err
	}
	defer d.db.releaseDBConnection(conn)

	_, err = conn.Exec("update resource_group set tool_id=?, url=?, name=?, version=? where tool_id=? and url=?",
		newResourceGroup.ToolId, newResourceGroup.URL, newResourceGroup.Name,
		newResourceGroup.Version, oldResourceGroup.ToolId, oldResourceGroup.URL)
	return err
}

func (d *DoltDBBranch) RemoveResourceGroup(toolId string, URL string) error {
	conn, err := d.db.getDBConnection()
	if err != nil {
		return err
	}
	defer d.db.releaseDBConnection(conn)

	_, err = conn.Exec("delete from link where (from_tool_id=? and from_rg_url=?) or (to_tool_id=? and to_rg_url=?)",
		toolId, URL, toolId, URL)
	_, err = conn.Exec("delete from resource where tool_id=? and rg_url=?",
		toolId, URL)
	_, err = conn.Exec("delete from resource_group where tool_id=? and url=?",
		toolId, URL)

	return err
}

func (d *DoltDBBranch) SaveBranchState() error {
	return d.commit()
}
