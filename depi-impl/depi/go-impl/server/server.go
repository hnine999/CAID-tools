package server

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"github.com/google/uuid"
	"go-impl/auth"
	"go-impl/config"
	"go-impl/depi_grpc"
	"go-impl/model"
	"go-impl/server/db"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/protobuf/encoding/prototext"
	"google.golang.org/protobuf/proto"
	"io"
	"log"
	"net"
	"os"
	"reflect"
	"strconv"
	"strings"
	"sync"
	"time"
)

const DEPI_CONFIG_ENV_VAR_NAME = "DEPI_CONFIG"

const CapBranchCreate = "CapBranchCreate"
const CapBranchTag = "CapBranchTag"
const CapBranchSwitch = "CapBranchSwitch"
const CapBranchList = "CapBranchList"
const CapResGroupAdd = "CapResGroupAdd"
const CapResGroupRead = "CapResGroupRead"
const CapResourceAdd = "CapResourceAdd"
const CapResourceRead = "CapResourceRead"
const CapResourceChange = "CapResourceChange"
const CapResourceRemove = "CapResourceRemove"
const CapLinkAdd = "CapLinkAdd"
const CapLinkRead = "CapLinkRead"
const CapLinkRemove = "CapLinkRemove"
const CapLinkMarkClean = "CapLinkMarkClean"
const CapResGroupChange = "CapResGroupChange"
const CapResGroupRemove = "CapResGroupRemove"

type User struct {
	Name          string
	Password      string
	Authorization *auth.Authorization
}

type Server struct {
	depi_grpc.UnimplementedDepiServer
	db                   db.DB
	sessions             map[string]*Session
	blackboards          map[string]*Blackboard
	blackboardAlwaysMain bool
	authorizationEnabled bool
	sessionLock          sync.Mutex
	sessionTimeout       time.Duration
	tokenTimeout         int
	auditDir             string
	auditLock            sync.Mutex
	currAuditDate        time.Time
	auditFile            io.WriteCloser
	logins               map[string]*User
	loginTokenKey        *cipher.Block
}

func LoadConfig(rootDir string, filename string) error {
	var configFilename string
	if len(filename) > 0 {
		configFilename = filename
	} else {
		found := false
		for _, e := range os.Environ() {
			parts := strings.SplitN(e, "=", 2)
			if parts[0] == DEPI_CONFIG_ENV_VAR_NAME {
				configFilename = fmt.Sprintf("%s/configs/depi_config_%s.json", rootDir, parts[1])
				found = true
			}
		}
		if !found {
			log.Printf("Using default config file, set env_var %s to load alternativeConfig.\n",
				DEPI_CONFIG_ENV_VAR_NAME)
			log.Printf("Example: $export %s=mem - would load depi_config.mem.json\n",
				DEPI_CONFIG_ENV_VAR_NAME)
			configFilename = rootDir + "/configs/depi_config_mem.json"
		}
	}

	log.Printf("Using config file: %s\n", configFilename)
	if _, err := os.Stat(configFilename); err == nil {
		err = config.LoadConfig(configFilename)
	}
	return nil
}

func LoadConfigFromStdin() error {
	log.Printf("Loading config from stdin\n")
	return config.LoadConfigFromStream(os.Stdin)
}

func LoadKey() ([]byte, error) {
	filename := ".depi_session_key"

	if _, err := os.Stat(filename); errors.Is(err, os.ErrNotExist) {
		randBytes := make([]byte, 32)
		_, err := io.ReadFull(rand.Reader, randBytes)
		if err != nil {
			return nil, err
		}
		os.WriteFile(filename, randBytes, 0700)
		return randBytes, nil
	}
	keyBytes, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}
	return keyBytes, nil
}

func NewServer() *Server {
	server := Server{}

	if config.GlobalConfig.DBConfig.Type == "memjson" {
		server.db = db.NewMemJsonDB()
	} else if config.GlobalConfig.DBConfig.Type == "dolt" {
		db, err := db.NewDoltDB()
		if err != nil {
			log.Printf("Error initializing Dolt interface: %+v\n", err)
			panic("Cannot proceed without database.")
		}
		server.db = db
	}

	server.loginTokenKey = nil

	key, err := LoadKey()
	if err != nil {
		log.Printf("Error loading token key: %+v\n", err)
	} else {
		block, err := aes.NewCipher(key)
		if err != nil {
			log.Printf("Error initializing token key: %+v\n", err)
		} else {
			server.loginTokenKey = &block
		}
	}

	server.sessions = map[string]*Session{}
	server.blackboards = map[string]*Blackboard{}
	server.logins = map[string]*User{}

	server.blackboardAlwaysMain = true
	server.authorizationEnabled = false
	server.sessionTimeout = time.Duration(config.GlobalConfig.ServerConfig.DefaultTimeout)
	if server.sessionTimeout == 0 {
		server.sessionTimeout = 3600 * time.Second
	}
	server.tokenTimeout = config.GlobalConfig.ServerConfig.TokenTimeout
	if server.tokenTimeout == 0 {
		server.tokenTimeout = 24 * 3600
	}

	server.auditDir = config.GlobalConfig.AuditConfig.Directory
	if server.auditDir != "" {
		os.MkdirAll(server.auditDir, 0666)
	}
	server.currAuditDate = time.Unix(0, 0)

	if config.GlobalConfig.ServerConfig.DefaultTimeout > 0 {
		server.sessionTimeout = time.Duration(config.GlobalConfig.ServerConfig.DefaultTimeout) * time.Second
	}

	for _, userConfig := range config.GlobalConfig.UserConfig {
		user := &User{Name: userConfig.Name, Password: userConfig.Password}
		server.logins[user.Name] = user
	}

	go server.checkSessionThread()
	return &server
}

func (server *Server) generateToken(sessionId string, userName string) string {
	userInfo := []byte(fmt.Sprintf("%s;%s;%d;", sessionId, userName, time.Now().Unix()))
	blockLen := aes.BlockSize + aes.BlockSize*(1+(len(userInfo)-1)/aes.BlockSize)
	iv := make([]byte, aes.BlockSize)
	padded := make([]byte, blockLen-aes.BlockSize)
	io.ReadFull(rand.Reader, iv)

	dst := make([]byte, blockLen)
	copy(dst, iv)
	copy(padded, userInfo)

	cbc := cipher.NewCBCEncrypter(*server.loginTokenKey, iv)
	cbc.CryptBlocks(dst[aes.BlockSize:], padded)

	return base64.StdEncoding.EncodeToString(dst)
}

func (server *Server) decodeToken(token string) (string, string, int64, error) {
	ciphertext, err := base64.StdEncoding.DecodeString(token)

	iv := ciphertext[:aes.BlockSize]
	ciphertext = ciphertext[aes.BlockSize:]
	cbc := cipher.NewCBCDecrypter(*server.loginTokenKey, iv)
	cbc.CryptBlocks(ciphertext, ciphertext)
	parts := strings.Split(string(ciphertext), ";")
	if len(parts) < 3 {
		return "", "", 0, errors.New("Corrupted token")
	}
	timestamp, err := strconv.ParseInt(parts[2], 10, 64)
	if err != nil {
		return "", "", 0, errors.New("Corrupted token")
	}
	return parts[0], parts[1], timestamp, nil
}

func (server *Server) refreshToken(token string) string {
	sessionId, user, _, err := server.decodeToken(token)
	if err != nil {
		log.Printf("Error decoding token: %+v\n", err)
		return token
	}
	return server.generateToken(sessionId, user)
}

func (server *Server) Start() error {
	var opts = []grpc.ServerOption{}
	port := config.GlobalConfig.ServerConfig.InsecurePort
	if config.GlobalConfig.ServerConfig.SecurePort > 0 {
		port = config.GlobalConfig.ServerConfig.SecurePort

		tlsCredentials, err := credentials.NewServerTLSFromFile(config.GlobalConfig.ServerConfig.CertPEM,
			config.GlobalConfig.ServerConfig.KeyPEM)
		if err != nil {
			return err
		}
		opts = append(opts, grpc.Creds(tlsCredentials))

	}
	lis, err := net.Listen("tcp",
		fmt.Sprintf("0.0.0.0:%d", port))
	if err != nil {
		return err
	}
	grpcServer := grpc.NewServer(opts...)
	depi_grpc.RegisterDepiServer(grpcServer, server)
	return grpcServer.Serve(lis)
}

func (server *Server) checkSessionThread() {
	for {
		server.checkSessions()
		time.Sleep(300 * time.Second)
	}
}

func (server *Server) checkSessions() {
	server.sessionLock.Lock()
	defer server.sessionLock.Unlock()

	expiredSessions := []string{}
	for sessionId, session := range server.sessions {
		if time.Now().After(session.LastRequest.Add(server.sessionTimeout)) {
			expiredSessions = append(expiredSessions, sessionId)
		}
	}
}

func (server *Server) getAuditFile() io.WriteCloser {
	server.auditLock.Lock()
	defer server.auditLock.Unlock()

	if server.auditDir == "" {
		return nil
	}
	now := time.Now()
	currDate := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
	if currDate == server.currAuditDate && server.auditFile != nil {
		return server.auditFile
	}
	if server.auditFile != nil {
		server.auditFile.Close()
	}
	logFilename := fmt.Sprintf("%04d%02d%02d", currDate.Year(), currDate.Month(), currDate.Day())
	var err error
	server.auditFile, err = os.Create(logFilename)
	if err != nil {
		server.auditFile = nil
		return nil
	}
	return server.auditFile
}

func (server *Server) writeAuditLogEntry(user string, operation string, data string) {
	server.auditLock.Lock()
	defer server.auditLock.Unlock()

	if server.auditFile == nil {
		return
	}

	currTime := time.Now()

	fmt.Fprintf(server.auditFile, "%02d:%02d:%02d.%03d|%s|%s|%s\n",
		currTime.Hour(), currTime.Minute(), currTime.Second(),
		currTime.Nanosecond()/1000000, user, operation, data)
}

func (server *Server) getSession(sessionId string) *Session {
	server.sessionLock.Lock()
	defer server.sessionLock.Unlock()

	session, ok := server.sessions[sessionId]
	if ok {
		session.LastRequest = time.Now()
		return session
	}
	return nil
}

func (server *Server) addSession(session *Session) {
	server.sessionLock.Lock()
	defer server.sessionLock.Unlock()

	server.sessions[session.SessionId] = session
}

func (server *Server) removeSession(sessionId string) {
	server.sessionLock.Lock()
	defer server.sessionLock.Unlock()

	delete(server.sessions, sessionId)
}

func (server *Server) printGRPC(message proto.Message) proto.Message {
	messageType := reflect.TypeOf(message)
	parts := strings.Split(messageType.String(), ".")
	formattedText := prototext.Format(message)
	lines := strings.Split(formattedText, "\n")
	for i, line := range lines {
		if strings.HasPrefix(line, "sessionId: ") {
			lines[i] = "sessionId: <sessionId>"
		} else if strings.HasPrefix(line, "loginToken: ") {
			lines[i] = "loginToken: <loginToken>"
		} else if strings.HasPrefix(line, "password: ") {
			lines[i] = "password: <password>"
		}
	}
	formattedText = strings.Join(lines, "\n")
	log.Printf("%s: %s\n", parts[len(parts)-1], formattedText)
	return message
}

func (server *Server) isAuthorized(user *User, capability string, args []string) bool {
	if !server.authorizationEnabled {
		return true
	}

	if user.Authorization == nil {
		return false
	}

	return user.Authorization.IsAuthorized(capability, args)
}

func (server *Server) hasCapability(user *User, capability string) bool {
	if !server.authorizationEnabled {
		return true
	}

	if user.Authorization == nil {
		return false
	}

	return user.Authorization.HasCapability(capability)
}

func (server *Server) numDepiWatchers(branchName string) int {
	server.sessionLock.Lock()
	defer server.sessionLock.Unlock()
	n := 0
	for _, session := range server.sessions {
		if branchName != "" && branchName != session.Branch.GetName() {
			continue
		}
		if session.WatchingDepi {
			n += 1
		}
	}
	return n
}

func (server *Server) invalidSession(sessionId string) *depi_grpc.GenericResponse {
	return server.printGRPC(&depi_grpc.GenericResponse{
		Ok:  false,
		Msg: fmt.Sprintf("Invalid session: %s", sessionId),
	}).(*depi_grpc.GenericResponse)
}

func (server *Server) successResponse() *depi_grpc.GenericResponse {
	return server.printGRPC(&depi_grpc.GenericResponse{
		Ok:  true,
		Msg: "",
	}).(*depi_grpc.GenericResponse)
}

func (server *Server) failureResponse(reason string) *depi_grpc.GenericResponse {
	return server.printGRPC(&depi_grpc.GenericResponse{
		Ok:  true,
		Msg: reason,
	}).(*depi_grpc.GenericResponse)
}

func (server *Server) errorResponse(reason string, err error) *depi_grpc.GenericResponse {
	return server.printGRPC(&depi_grpc.GenericResponse{
		Ok:  true,
		Msg: fmt.Sprintf("%s: %+v", reason, err),
	}).(*depi_grpc.GenericResponse)
}

func (server *Server) Login(ctx context.Context, request *depi_grpc.LoginRequest) (*depi_grpc.LoginResponse, error) {
	server.printGRPC(request)
	user, ok := server.logins[request.User]
	if ok {
		if user.Password == request.Password {
			sessionId := uuid.New().String()
			mainBranch, err := server.db.GetBranch("main")
			if err == nil {
				server.addSession(
					NewSession(sessionId, user, mainBranch))
				_, ok := server.blackboards[request.User]
				if !ok {
					server.blackboards[request.User] = NewBlackboard()
				}
				token := server.generateToken(sessionId, request.User)
				return server.printGRPC(
					&depi_grpc.LoginResponse{Ok: true, Msg: "", SessionId: sessionId, LoginToken: token, User: request.User}).(*depi_grpc.LoginResponse), nil
			} else {
				return nil, err
			}
		}
	}
	return server.printGRPC(
		&depi_grpc.LoginResponse{Ok: false, Msg: "Invalid login", SessionId: "", LoginToken: ""}).(*depi_grpc.LoginResponse), nil
}

func (server *Server) LoginWithToken(ctx context.Context, request *depi_grpc.LoginWithTokenRequest) (*depi_grpc.LoginResponse, error) {
	server.printGRPC(request)

	sessionId, userName, timeout, err := server.decodeToken(request.LoginToken)
	if err != nil {
		log.Printf("Error decoding token: %+v\n", err)
		return server.printGRPC(
			&depi_grpc.LoginResponse{Ok: false, Msg: "Invalid token", SessionId: "", LoginToken: ""}).(*depi_grpc.LoginResponse), nil
	}
	if time.Now().Unix()-int64(timeout) > int64(server.tokenTimeout) {
		return server.printGRPC(
			&depi_grpc.LoginResponse{Ok: false, Msg: "Token expired", SessionId: "", LoginToken: ""}).(*depi_grpc.LoginResponse), nil
	}
	user, ok := server.logins[userName]
	if ok {
		existingSession := server.getSession(sessionId)
		if existingSession == nil {
			sessionId = uuid.New().String()
			mainBranch, err := server.db.GetBranch("main")
			if err == nil {
				server.addSession(
					NewSession(sessionId, user, mainBranch))
				_, ok := server.blackboards[userName]
				if !ok {
					server.blackboards[userName] = NewBlackboard()
				}
			} else {
				return nil, err
			}
		}
		token := server.generateToken(sessionId, userName)
		return server.printGRPC(
			&depi_grpc.LoginResponse{Ok: true, Msg: "", SessionId: sessionId, LoginToken: token, User: userName}).(*depi_grpc.LoginResponse), nil
	}
	return server.printGRPC(
		&depi_grpc.LoginResponse{Ok: false, Msg: "Invalid token", SessionId: ""}).(*depi_grpc.LoginResponse), nil
}

func (server *Server) Logout(ctx context.Context, request *depi_grpc.LogoutRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}
	session.Close()
	server.removeSession(request.SessionId)
	return session.successResponse(), nil
}

func (server *Server) RegisterCallback(request *depi_grpc.RegisterCallbackRequest, server2 depi_grpc.Depi_RegisterCallbackServer) error {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		server2.Send(&depi_grpc.ResourcesUpdatedNotification{
			Ok:      false,
			Msg:     fmt.Sprintf("Invalid session: %s", request.SessionId),
			Updates: []*depi_grpc.ResourceUpdate{},
		})
		return nil
	}

	session.WatchingResources = true
	for session.WatchingResources {
		item, err := session.ResourceUpdates.PopWait()
		if err != nil {
			break
		}
		server2.Send(&depi_grpc.ResourcesUpdatedNotification{
			Ok:      true,
			Msg:     "",
			Updates: []*depi_grpc.ResourceUpdate{item},
		})
	}
	session.WatchingResources = false
	return nil
}

func (server *Server) WatchResourceGroup(ctx context.Context, request *depi_grpc.WatchResourceGroupRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)

	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}
	session.WatchingResources = true

	session.WatchedGroups[model.ResourceGroupKey{ToolId: request.ToolId,
		URL: request.URL}] = true

	return server.successResponse(), nil
}

func (server *Server) UnwatchResourceGroup(ctx context.Context, request *depi_grpc.UnwatchResourceGroupRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)

	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	key := model.ResourceGroupKey{ToolId: request.ToolId,
		URL: request.URL}

	_, ok := session.WatchedGroups[key]
	if ok {
		delete(session.WatchedGroups, key)
	}

	return server.successResponse(), nil
}

func (server *Server) CreateBranch(ctx context.Context, request *depi_grpc.CreateBranchRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	if server.db.BranchExists(request.BranchName) {
		return session.failureResponse("Branch already exists"), nil
	}

	isFromTag := false
	fromBranch := request.GetFromBranch()
	fromTag := request.GetFromTag()
	var fromName string

	if fromBranch != "" {
		if !server.db.BranchExists(fromBranch) {
			return session.failureResponse("Unknown branch"), nil
		}
		fromName = fromBranch
	} else if fromTag != "" {
		isFromTag = true
		if !server.db.TagExists(fromTag) {
			return session.failureResponse("Unknown tag"), nil
		}
		fromName = fromTag
	} else {
		fromBranch = session.Branch.GetName()
		fromName = fromBranch
	}

	if !server.hasCapability(session.User, CapBranchCreate) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to create a branch", session.User.Name)), nil
	}

	var op string
	if !isFromTag {
		_, err := server.db.CreateBranch(request.BranchName, fromBranch)
		if err != nil {
			return session.failureResponse(fmt.Sprintf("error creating branch: %+v", err)), nil
		}
		op = "CreateBranch"
	} else {
		_, err := server.db.CreateBranchFromTag(request.BranchName, fromTag)
		if err != nil {
			return session.failureResponse(fmt.Sprintf("error creating branch: %+v", err)), nil
		}
		op = "CreateBranchFromTag"
	}
	server.writeAuditLogEntry(session.User.Name, op, fmt.Sprintf("from=%s;to=%s", fromName, request.BranchName))
	return session.successResponse(), nil
}

func (server *Server) SetBranch(ctx context.Context, request *depi_grpc.SetBranchRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	if !server.hasCapability(session.User, CapBranchSwitch) {
		return server.failureResponse(fmt.Sprintf(
			"User %s is not authorized to switch branches", session.User.Name)), nil
	}

	if server.db.BranchExists(request.Branch) {
		var err error
		session.Branch, err = server.db.GetBranch(request.Branch)
		if err != nil {
			return session.errorResponse("Error fetching branch", err), nil
		}
		return session.successResponse(), nil
	} else {
		return session.failureResponse("Unknown branch"), nil
	}
}

func (server *Server) CreateTag(ctx context.Context, request *depi_grpc.CreateTagRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	fromBranch := request.FromBranch
	if fromBranch != "" {
		if !server.db.BranchExists(request.FromBranch) {
			return session.failureResponse("Unknown branch"), nil
		}
	} else {
		fromBranch = session.Branch.GetName()
	}

	if !server.hasCapability(session.User, CapBranchTag) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to tag a branch", session.User.Name)), nil
	}

	_, err := server.db.CreateTag(request.TagName, fromBranch)
	if err != nil {
		return session.errorResponse("Error creating tag", err), nil
	}
	server.writeAuditLogEntry(session.User.Name, "CreateTag",
		fmt.Sprintf("from=%s;to=%s", fromBranch, request.TagName))
	return session.successResponse(), nil
}

func (server *Server) GetLastKnownVersion(ctx context.Context, request *depi_grpc.GetLastKnownVersionRequest) (*depi_grpc.GetLastKnownVersionResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.printGRPC(
			&depi_grpc.GetLastKnownVersionResponse{
				Ok:      false,
				Msg:     fmt.Sprintf("Invalid session: %s", request.SessionId),
				Version: "",
			}).(*depi_grpc.GetLastKnownVersionResponse), nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()
	version, err := branch.GetResourceGroupVersion(request.ToolId, request.URL)
	if err != nil {
		return server.printGRPC(
			&depi_grpc.GetLastKnownVersionResponse{
				Ok:      false,
				Msg:     fmt.Sprintf("Error getting last known version: %+v", err),
				Version: "",
			}).(*depi_grpc.GetLastKnownVersionResponse), nil

	}
	return server.printGRPC(
		&depi_grpc.GetLastKnownVersionResponse{
			Ok:      true,
			Msg:     "",
			Version: version,
		}).(*depi_grpc.GetLastKnownVersionResponse), nil
}

func (server *Server) UpdateResourceGroup(ctx context.Context, request *depi_grpc.UpdateResourceGroupRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()
	if request.UpdateBranch != "" {
		if request.UpdateBranch != branch.GetName() {
			var err error
			branch, err = server.db.GetBranch(request.UpdateBranch)
			if err != nil {
				return server.errorResponse("Error retrieving branch", err), nil
			}
		}
	}

	if !server.hasCapability(session.User, CapResGroupChange) {
		return server.failureResponse(
			fmt.Sprintf("User %s is not authorized to change resource groups",
				session.User.Name)), nil
	}

	if !server.hasCapability(session.User, CapResourceChange) {
		return server.failureResponse(
			fmt.Sprintf("User %s is not authorized to change resources",
				session.User.Name)), nil
	}

	if !server.isAuthorized(session.User, CapResGroupChange,
		[]string{request.ResourceGroup.ToolId, request.ResourceGroup.URL}) {
		return server.failureResponse(
			fmt.Sprintf("User %s is not authorized to change this resource group",
				session.User.Name)), nil

	}

	resourceGroupChange := model.NewResourceGroupChangeFromGrpc(request.ResourceGroup)
	allowedResources := []*model.ResourceChange{}

	for _, resource := range resourceGroupChange.Resources {
		if resource.ChangeType == model.ChangeType_Added {
			if server.isAuthorized(session.User, CapResourceAdd, []string{
				resourceGroupChange.ToolId, resourceGroupChange.URL,
				resource.URL}) {
				allowedResources = append(allowedResources, resource)
			} else {
				log.Printf("User %s is not allowed to add resource %s %s %s\n",
					session.User.Name, resourceGroupChange.ToolId,
					resourceGroupChange.URL, resource.URL)
			}
		} else if resource.ChangeType == model.ChangeType_Modified ||
			resource.ChangeType == model.ChangeType_Renamed {
			if server.isAuthorized(session.User, CapResourceChange, []string{
				resourceGroupChange.ToolId, resourceGroupChange.URL,
				resource.URL}) {
				allowedResources = append(allowedResources, resource)
			} else {
				log.Printf("User %s is not allowed to change resource %s %s %s\n",
					session.User.Name, resourceGroupChange.ToolId,
					resourceGroupChange.URL, resource.URL)
			}
		} else if resource.ChangeType == model.ChangeType_Removed {
			if server.isAuthorized(session.User, CapResourceRemove, []string{
				resourceGroupChange.ToolId, resourceGroupChange.URL,
				resource.URL}) {
				allowedResources = append(allowedResources, resource)
			} else {
				log.Printf("User %s is not allowed to remove resource %s %s %s\n",
					session.User.Name, resourceGroupChange.ToolId,
					resourceGroupChange.URL, resource.URL)
			}
		}
	}

	resourceGroupChange.Resources = map[string]*model.ResourceChange{}
	depiUpdates := []*depi_grpc.Update{}

	for _, res := range allowedResources {
		resourceGroupChange.Resources[res.URL] = res
		depiUpdates = append(depiUpdates,
			&depi_grpc.Update{
				UpdateType: res.GetChangeAsUpdateType(),
				UpdateData: &depi_grpc.Update_Resource{
					Resource: res.ToResource().ToGrpc(resourceGroupChange.ToResourceGroup()),
				},
			})
	}

	linksToUpdate, err := branch.UpdateResourceGroup(resourceGroupChange)
	if err != nil {
		return session.errorResponse("Error updating resource group", err), nil
	}
	branch.SaveBranchState()

	if branch.GetName() == "main" {
		for blackboardUser, blackboard := range server.blackboards {

			updates := []*depi_grpc.Update{}

			for _, tool := range blackboard.Resources {
				for _, rg := range tool {
					if rg.ToolId == resourceGroupChange.ToolId &&
						rg.URL == resourceGroupChange.URL &&
						rg.Version != resourceGroupChange.Version {
						updates = append(updates, &depi_grpc.Update{
							UpdateType: depi_grpc.UpdateType_ResourceGroupVersionChanged,
							UpdateData: &depi_grpc.Update_VersionChange{
								VersionChange: &depi_grpc.ResourceGroupVersionChange{
									Name:       resourceGroupChange.Name,
									URL:        resourceGroupChange.URL,
									ToolId:     resourceGroupChange.ToolId,
									Version:    rg.Version,
									NewVersion: resourceGroupChange.Version,
								},
							},
						})
						rg.Version = resourceGroupChange.Version
						for URL, resourceChange := range resourceGroupChange.Resources {
							_, ok := rg.Resources[URL]
							if !ok {
								continue
							}

							if resourceChange.ChangeType == model.ChangeType_Removed {
								updates = append(updates, &depi_grpc.Update{
									UpdateType: depi_grpc.UpdateType_RemoveResource,
									UpdateData: &depi_grpc.Update_Resource{
										Resource: rg.Resources[URL].ToGrpc(rg),
									},
								})
								res := rg.Resources[URL]
								delete(rg.Resources, URL)

								newChanged := map[model.LinkKey]*model.LinkWithResources{}
								for key, link := range blackboard.ChangedLinks {
									if (link.FromResourceGroup.ToolId == rg.ToolId &&
										link.FromResourceGroup.URL == rg.URL &&
										link.FromRes.URL == res.URL) ||
										(link.ToResourceGroup.ToolId == rg.ToolId &&
											link.ToResourceGroup.URL == rg.URL &&
											link.ToRes.URL == res.URL) {
										updates = append(updates, &depi_grpc.Update{
											UpdateType: depi_grpc.UpdateType_RemoveLink,
											UpdateData: &depi_grpc.Update_Link{
												Link: link.ToGrpc(),
											},
										})
										_, ok := blackboard.DeletedLinks[key]
										if !ok {
											blackboard.DeletedLinks[key] = link
										}
									} else {
										newChanged[key] = link
									}
								}
								blackboard.ChangedLinks = newChanged
							} else if resourceChange.ChangeType == model.ChangeType_Renamed ||
								(resourceChange.ChangeType == model.ChangeType_Modified ||
									resourceChange.URL != resourceChange.NewURL) {
								for _, link := range blackboard.ChangedLinks {
									fromRes := link.FromRes.ToGrpc(link.FromResourceGroup)
									toRes := link.ToRes.ToGrpc(link.ToResourceGroup)
									changed := false

									if link.FromResourceGroup.ToolId == resourceGroupChange.ToolId &&
										link.FromResourceGroup.URL == resourceGroupChange.URL &&
										link.FromRes.URL == resourceChange.URL {
										changed = true
									} else if link.ToResourceGroup.ToolId == resourceGroupChange.ToolId &&
										link.ToResourceGroup.URL == resourceGroupChange.URL &&
										link.ToRes.URL == resourceChange.URL {
										changed = true
									}

									if changed {
										fromResNew := link.FromRes.ToGrpc(link.FromResourceGroup)
										fromResNew.URL = resourceChange.NewURL
										fromResNew.Name = resourceChange.NewName
										fromResNew.Id = resourceChange.NewId

										toResNew := link.ToRes.ToGrpc(link.ToResourceGroup)
										toResNew.URL = resourceChange.NewURL
										toResNew.Name = resourceChange.NewName
										toResNew.Id = resourceChange.NewId

										updates = append(updates, &depi_grpc.Update{
											UpdateType: depi_grpc.UpdateType_RenameLink,
											UpdateData: &depi_grpc.Update_RenameLink{
												RenameLink: &depi_grpc.ResourceLinkRename{
													FromRes:    fromRes,
													FromResNew: fromResNew,
													ToRes:      toRes,
													ToResNew:   toResNew,
												},
											},
										})
									}
								}

								res := rg.Resources[resourceChange.URL]
								delete(rg.Resources, resourceChange.URL)
								rg.Resources[resourceChange.NewURL] = res
								res.URL = resourceChange.NewURL
								res.Name = resourceChange.NewName
								res.Id = resourceChange.NewId

								updates = append(updates, &depi_grpc.Update{
									UpdateType: depi_grpc.UpdateType_RenameResource,
									UpdateData: &depi_grpc.Update_Rename{
										Rename: resourceChange.ToGrpc(),
									},
								})
							}
						}
					}
				}
			}
			if len(updates) > 0 {
				for _, session := range server.sessions {
					if session.User.Name == blackboardUser {
						session.BlackboardUpdates.Push(
							&depi_grpc.BlackboardUpdate{
								Ok:      true,
								Msg:     "",
								Updates: updates,
							})
					}
				}
			}
		}
	}

	for _, link := range linksToUpdate {
		upd := &depi_grpc.ResourceUpdate{
			WatchedResource: link.ToRes.ToGrpc(),
			UpdatedResource: link.FromRes.ToGrpc(),
		}
		depiUpdates = append(depiUpdates, &depi_grpc.Update{
			UpdateType: depi_grpc.UpdateType_MarkLinkDirty,
			UpdateData: &depi_grpc.Update_MarkLinkDirty{
				MarkLinkDirty: link.ToGrpc(),
			},
		})
		for _, session := range server.sessions {
			if session.Branch.GetName() != branch.GetName() {
				continue
			}

			_, ok := session.WatchedGroups[model.ResourceGroupKey{
				ToolId: link.ToRes.ToolId,
				URL:    link.ToRes.ResourceGroupURL,
			}]
			if ok {
				session.ResourceUpdates.Push(upd)
			}
		}
		depiUpdate := &depi_grpc.DepiUpdate{
			Ok:      true,
			Msg:     "",
			Updates: depiUpdates,
		}
		for _, session := range server.sessions {
			if session.Branch.GetName() != branch.GetName() {
				continue
			}
			if session.WatchingDepi {
				session.DepiUpdates.Push(depiUpdate)
			}
		}
	}

	for URL, resource := range resourceGroupChange.Resources {
		changeType := "add"
		if resource.ChangeType == model.ChangeType_Modified {
			changeType = "modify"
		} else if resource.ChangeType == model.ChangeType_Renamed {
			changeType = "rename"
		} else if resource.ChangeType == model.ChangeType_Removed {
			changeType = "remove"
		}

		server.writeAuditLogEntry(session.User.Name, "UpdateResourceGroupResource",
			fmt.Sprintf("toolId=%s;rgURL=%s;URL=%s;changeType=%s",
				request.ResourceGroup.ToolId,
				request.ResourceGroup.URL,
				URL, changeType))
	}

	return server.successResponse(), nil
}

func (server *Server) AddResourcesToBlackboard(ctx context.Context, request *depi_grpc.AddResourcesToBlackboardRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	updates := []*depi_grpc.Update{}
	blackboard := server.blackboards[session.User.Name]

	for _, res := range request.Resources {
		added := blackboard.AddResource(&model.ResourceGroup{
			ToolId: res.ToolId, URL: res.ResourceGroupURL,
			Name: res.ResourceGroupName, Version: res.ResourceGroupVersion,
		}, &model.Resource{
			Name: res.Name, Id: res.Id, URL: res.URL,
		})
		if added {
			update := &depi_grpc.Update{
				UpdateType: depi_grpc.UpdateType_AddResource,
				UpdateData: &depi_grpc.Update_Resource{
					Resource: res,
				},
			}
			updates = append(updates, update)
		}
	}

	if len(updates) > 0 {
		for _, sess := range server.sessions {
			if sess.User.Name != session.User.Name {
				continue
			}
			if sess.WatchingBlackboard {
				sess.BlackboardUpdates.Push(
					&depi_grpc.BlackboardUpdate{
						Ok: true, Msg: "",
						Updates: updates,
					})
			}
		}
	}

	return server.successResponse(), nil
}

func (server *Server) RemoveResourcesFromBlackboard(ctx context.Context, request *depi_grpc.RemoveResourcesFromBlackboardRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	updates := []*depi_grpc.Update{}
	blackboard := server.blackboards[session.User.Name]
	for _, refGrpc := range request.ResourceRefs {
		ref := model.NewResourceRefFromGrpc(refGrpc)
		expandedRes := blackboard.ExpandResource(ref.ToolId, ref.ResourceGroupURL, ref.URL)
		if blackboard.RemoveResource(ref) {
			update := &depi_grpc.Update{
				UpdateType: depi_grpc.UpdateType_RemoveResource,
				UpdateData: &depi_grpc.Update_Resource{
					Resource: expandedRes.Resource.ToGrpc(expandedRes.ResourceGroup),
				},
			}
			updates = append(updates, update)
		}
	}

	if len(updates) > 0 {
		for _, sess := range server.sessions {
			if sess.User.Name != session.User.Name {
				continue
			}
			sess.BlackboardUpdates.Push(&depi_grpc.BlackboardUpdate{
				Ok: true, Msg: "",
				Updates: updates,
			})
		}
	}

	return server.successResponse(), nil
}

func (server *Server) lookupLinkResource(blackboard *Blackboard, links []*model.Link) ([]*model.LinkWithResources, string) {
	result := []*model.LinkWithResources{}
	for _, link := range links {
		fromRes := blackboard.ExpandResource(link.FromRes.ToolId, link.FromRes.ResourceGroupURL,
			link.FromRes.URL)
		if fromRes == nil {
			log.Printf("Invalid from resource %s %s %s",
				link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL)
			continue
		}
		toRes := blackboard.ExpandResource(link.ToRes.ToolId, link.ToRes.ResourceGroupURL,
			link.ToRes.URL)
		if toRes == nil {
			log.Printf("Invalid to resource %s %s %s",
				link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL)
			continue
		}

		result = append(result, &model.LinkWithResources{
			FromResourceGroup: fromRes.ResourceGroup,
			FromRes:           fromRes.Resource,
			ToResourceGroup:   toRes.ResourceGroup,
			ToRes:             toRes.Resource,
		})
	}
	return result, ""
}

func (server *Server) LinkBlackboardResources(ctx context.Context, request *depi_grpc.LinkBlackboardResourcesRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	blackboard := server.blackboards[session.User.Name]

	reqLinks := make([]*model.Link, len(request.Links))
	for i, link := range request.Links {
		reqLinks[i] = model.NewLinkFromGrpcLinkRef(link)
	}

	links, resp := server.lookupLinkResource(blackboard, reqLinks)

	if resp != "" {
		return server.failureResponse(resp), nil
	}

	updates := blackboard.LinkResources(links)
	if len(updates) > 0 {
		for _, sess := range server.sessions {
			if sess.User.Name != session.User.Name {
				continue
			}
			if sess.WatchingBlackboard {
				sess.BlackboardUpdates.Push(&depi_grpc.BlackboardUpdate{
					Ok: true, Msg: "", Updates: updates,
				})
			}
		}
	}
	return server.successResponse(), nil
}

func (server *Server) UnlinkBlackboardResources(ctx context.Context, request *depi_grpc.UnlinkBlackboardResourcesRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	blackboard := server.blackboards[session.User.Name]

	reqLinks := make([]*model.Link, len(request.Links))
	for i, link := range request.Links {
		reqLinks[i] = model.NewLinkFromGrpcLinkRef(link)
	}

	links, resp := server.lookupLinkResource(blackboard, reqLinks)

	if resp != "" {
		return server.failureResponse(resp), nil
	}

	updates := blackboard.UnlinkResources(links)
	if len(updates) > 0 {
		for _, sess := range server.sessions {
			if sess.User.Name != session.User.Name {
				continue
			}
			if sess.WatchingBlackboard {
				sess.BlackboardUpdates.Push(&depi_grpc.BlackboardUpdate{
					Ok: true, Msg: "", Updates: updates,
				})
			}
		}
	}
	return server.successResponse(), nil
}

func GetResourcesAndLinks(links map[model.LinkKey]*model.LinkWithResources) map[model.ResourceRef]*model.ResourceGroupAndResource {
	rrSet := map[model.ResourceRef]*model.ResourceGroupAndResource{}
	for _, link := range links {
		if !link.Deleted {
			rrSet[*model.NewResourceRefFromRGAndRes(link.FromResourceGroup, link.FromRes)] =
				&model.ResourceGroupAndResource{
					ResourceGroup: link.FromResourceGroup,
					Resource:      link.FromRes,
				}
			rrSet[*model.NewResourceRefFromRGAndRes(link.ToResourceGroup, link.ToRes)] =
				&model.ResourceGroupAndResource{
					ResourceGroup: link.ToResourceGroup,
					Resource:      link.ToRes,
				}
		}
	}

	return rrSet
}

func (server *Server) GetBlackboardResources(ctx context.Context, request *depi_grpc.GetBlackboardResourcesRequest) (*depi_grpc.GetBlackboardResourcesResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.printGRPC(&depi_grpc.GetBlackboardResourcesResponse{Ok: false,
			Msg:       fmt.Sprintf("Invalid session: %s", request.SessionId),
			Resources: []*depi_grpc.Resource{},
			Links:     []*depi_grpc.ResourceLink{},
		}).(*depi_grpc.GetBlackboardResourcesResponse), nil
	}
	blackboard := server.blackboards[session.User.Name]

	links := make([]*depi_grpc.ResourceLink, len(blackboard.ChangedLinks))
	i := 0
	for _, link := range blackboard.ChangedLinks {
		links[i] = link.ToGrpc()
		i += 1
	}
	rrs := GetResourcesAndLinks(blackboard.ChangedLinks)
	bbrrs := blackboard.GetResources()
	for _, bbrr := range bbrrs {
		rrs[*model.NewResourceRefFromRGAndRes(bbrr.ResourceGroup, bbrr.Resource)] = bbrr
	}
	rrsGrpc := make([]*depi_grpc.Resource, len(rrs))
	i = 0
	for _, res := range rrs {
		rrsGrpc[i] = res.Resource.ToGrpc(res.ResourceGroup)
		i += 1
	}

	return session.printGRPC(&depi_grpc.GetBlackboardResourcesResponse{
		Ok: true, Msg: "",
		Resources: rrsGrpc, Links: links,
	}).(*depi_grpc.GetBlackboardResourcesResponse), nil
}

type RGKey struct {
	ToolId  string
	URL     string
	Version string
}

func (server *Server) SaveBlackboard(ctx context.Context, request *depi_grpc.SaveBlackboardRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	var branch db.Branch
	var err error

	if server.blackboardAlwaysMain {
		branch, err = server.db.GetBranch("main")
		if err != nil {
			return server.failureResponse(fmt.Sprintf("error fetching main branch: %+v", err)), nil
		}
	} else {
		branch = session.Branch
	}

	branch.Lock()
	defer branch.Unlock()

	blackboard := server.blackboards[session.User.Name]

	rs := blackboard.GetResources()
	if len(rs) > 0 && !server.hasCapability(session.User, CapResourceAdd) {
		return server.failureResponse(fmt.Sprintf("user %s is not authorized to add resources", session.User.Name)), nil
	}

	checkedVersions := map[RGKey]bool{}
	for _, rgAndRes := range rs {
		key := RGKey{
			ToolId:  rgAndRes.ResourceGroup.ToolId,
			URL:     rgAndRes.ResourceGroup.URL,
			Version: rgAndRes.ResourceGroup.Version,
		}

		_, ok := checkedVersions[key]
		if !ok {
			rgVersion, err := branch.GetResourceGroupVersion(rgAndRes.ResourceGroup.ToolId,
				rgAndRes.ResourceGroup.URL)
			if err != nil {
				return server.failureResponse(fmt.Sprintf(
					"error checking resource group version: %+v", err)), nil
			}
			if rgVersion != "" && rgVersion != rgAndRes.ResourceGroup.Version {
				return server.failureResponse(fmt.Sprintf(
					"resource version in blackboard {} does not match version in server {}",
					rgAndRes.ResourceGroup.Version, rgVersion)), nil
			}
			checkedVersions[key] = true

			toolConfig, ok := config.GlobalConfig.ToolConfig[rgAndRes.ResourceGroup.ToolId]
			if !ok {
				return server.failureResponse(fmt.Sprintf(
					"tool id %s not configured in the depi server", rgAndRes.ResourceGroup.ToolId)), nil
			}
			if !strings.HasPrefix(rgAndRes.Resource.URL, toolConfig.PathSeparator) {
				rgAndRes.Resource.URL = toolConfig.PathSeparator + rgAndRes.Resource.URL
			}

			if !server.isAuthorized(session.User, CapResourceAdd, []string{
				rgAndRes.ResourceGroup.ToolId, rgAndRes.ResourceGroup.URL, rgAndRes.Resource.URL,
			}) {
				return server.failureResponse(fmt.Sprintf("user %s is not authorized to add resource %s %s %s",
					session.User.Name, rgAndRes.ResourceGroup.ToolId, rgAndRes.ResourceGroup.URL,
					rgAndRes.Resource.URL)), nil

			}
		}
	}

	if len(rs) > 1000 {
		for i := 0; i < len(rs); i += 1000 {
			if len(rs)-i < 1000 {
				log.Println("Adding remaining resources\n")
				_, err = branch.AddResources(rs[i:])
				if err != nil {
					log.Printf("Error adding resources: %+v\n", err)
				}
			} else {
				log.Println("Adding 1000 resources\n")
				_, err = branch.AddResources(rs[i : i+1000])
				if err != nil {
					log.Printf("Error adding resources: %+v\n", err)
				}
			}
		}
	} else {
		_, err = branch.AddResources(rs)
		if err != nil {
			log.Printf("Error adding resources: %+v\n", err)
		}
	}

	links := make([]*model.LinkWithResources, len(blackboard.ChangedLinks))
	i := 0
	for _, link := range blackboard.ChangedLinks {
		links[i] = link
		i += 1
	}
	_, err = branch.AddLinks(links)
	if err != nil {
		log.Printf("Error adding links: %+v\n", err)
	}
	allUpdates := []*depi_grpc.Update{}
	for _, rgrs := range rs {
		allUpdates = append(allUpdates, &depi_grpc.Update{
			UpdateType: depi_grpc.UpdateType_AddResource,
			UpdateData: &depi_grpc.Update_Resource{
				Resource: rgrs.Resource.ToGrpc(rgrs.ResourceGroup),
			},
		})
	}
	for _, link := range blackboard.ChangedLinks {
		allUpdates = append(allUpdates, &depi_grpc.Update{
			UpdateType: depi_grpc.UpdateType_AddLink,
			UpdateData: &depi_grpc.Update_Link{
				Link: link.ToGrpc(),
			},
		})
	}

	err = branch.SaveBranchState()
	if err != nil {
		log.Printf("Error saving branch state: %+v\n", err)
	}

	server.clearBlackboard(session.User.Name)

	depiUpdate := &depi_grpc.DepiUpdate{
		Ok: true, Msg: "", Updates: allUpdates,
	}
	for _, session := range server.sessions {
		if session.WatchingDepi {
			session.DepiUpdates.Push(depiUpdate)
		}
	}

	for _, rgAndRes := range rs {
		server.writeAuditLogEntry(session.User.Name, "AddResource",
			fmt.Sprintf("toolId=%s;rgURL=%s;URL=%s", rgAndRes.ResourceGroup.ToolId,
				rgAndRes.ResourceGroup.URL, rgAndRes.Resource.URL))
	}

	for _, link := range blackboard.ChangedLinks {
		server.writeAuditLogEntry(session.User.Name, "LinkResources",
			fmt.Sprintf("fromToolId=%s;fromRgURL=%s;fromURL=%s;toToolId=%s;toRgURL=%s;toURL=%s",
				link.FromResourceGroup.ToolId, link.FromResourceGroup.URL,
				link.FromRes.URL, link.ToResourceGroup.ToolId,
				link.ToResourceGroup.URL, link.ToRes.URL))
	}
	return server.successResponse(), nil
}

func (server *Server) clearBlackboard(user string) {
	blackboard, ok := server.blackboards[user]
	if !ok {
		server.blackboards[user] = NewBlackboard()
		return
	}

	updates := []*depi_grpc.Update{}
	for _, tool := range blackboard.Resources {
		for _, rg := range tool {
			for _, res := range rg.Resources {
				updates = append(updates, &depi_grpc.Update{
					UpdateType: depi_grpc.UpdateType_RemoveResource,
					UpdateData: &depi_grpc.Update_Resource{
						Resource: res.ToGrpc(rg),
					},
				})
			}

			for _, link := range blackboard.DeletedLinks {
				updates = append(updates, &depi_grpc.Update{
					UpdateType: depi_grpc.UpdateType_AddLink,
					UpdateData: &depi_grpc.Update_Link{
						Link: link.ToGrpc(),
					},
				})
			}

			for _, link := range blackboard.ChangedLinks {
				updates = append(updates, &depi_grpc.Update{
					UpdateType: depi_grpc.UpdateType_RemoveLink,
					UpdateData: &depi_grpc.Update_Link{
						Link: link.ToGrpc(),
					},
				})
			}
		}
	}
	if len(updates) > 0 {
		blackboardUpdate := &depi_grpc.BlackboardUpdate{
			Ok: true, Msg: "", Updates: updates,
		}
		for _, session := range server.sessions {
			if session.User.Name != user {
				continue
			}
			if session.WatchingBlackboard {
				session.BlackboardUpdates.Push(blackboardUpdate)
			}

		}
	}

	server.blackboards[user] = NewBlackboard()
}

func (server *Server) ClearBlackboard(ctx context.Context, request *depi_grpc.ClearBlackboardRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	server.clearBlackboard(session.User.Name)

	return server.successResponse(), nil
}

func (server *Server) GetDirtyLinks(ctx context.Context, request *depi_grpc.GetDirtyLinksRequest) (*depi_grpc.GetDirtyLinksResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.GetDirtyLinksResponse{
			Ok: false, Msg: fmt.Sprintf("invalid session id: %s", request.SessionId),
			Links:     []*depi_grpc.ResourceLink{},
			Resources: []*depi_grpc.Resource{},
		}, nil
	}

	if !server.hasCapability(session.User, CapLinkRead) {
		return &depi_grpc.GetDirtyLinksResponse{
			Ok: false, Msg: fmt.Sprintf("user %s cannot read links", session.User.Name),
			Links:     []*depi_grpc.ResourceLink{},
			Resources: []*depi_grpc.Resource{},
		}, nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	resources := []*depi_grpc.Resource{}
	links := []*depi_grpc.ResourceLink{}

	dirtyLinks, err := branch.GetDirtyLinks(&model.ResourceGroupKey{
		ToolId: request.ToolId, URL: request.URL,
	}, request.WithInferred)

	if err != nil {
		return &depi_grpc.GetDirtyLinksResponse{
			Ok: false, Msg: fmt.Sprintf("error reading dirty links: %+v", err),
			Links:     []*depi_grpc.ResourceLink{},
			Resources: []*depi_grpc.Resource{},
		}, nil
	}

	for _, link := range dirtyLinks {
		if server.isAuthorized(session.User, CapLinkRead, []string{
			link.FromResourceGroup.ToolId, link.FromResourceGroup.URL,
			link.FromRes.URL, link.ToResourceGroup.ToolId,
			link.ToResourceGroup.URL, link.ToRes.URL,
		}) {
			resources = append(resources, link.ToRes.ToGrpc(link.ToResourceGroup))
			links = append(links, link.ToGrpc())
		} else {
			log.Printf("user %s is not authorized to read linke %s %s %s -> %s %s %s\n",
				link.FromResourceGroup.ToolId, link.FromResourceGroup.URL,
				link.FromRes.URL, link.ToResourceGroup.ToolId,
				link.ToResourceGroup.URL, link.ToRes.URL)
		}
	}

	return session.printGRPC(&depi_grpc.GetDirtyLinksResponse{
		Ok: true, Msg: "", Links: links, Resources: resources,
	}).(*depi_grpc.GetDirtyLinksResponse), nil
}

func (server *Server) GetDirtyLinksAsStream(request *depi_grpc.GetDirtyLinksRequest,
	stream depi_grpc.Depi_GetDirtyLinksAsStreamServer) error {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		stream.Send(&depi_grpc.GetDirtyLinksAsStreamResponse{
			Ok: false, Msg: fmt.Sprintf("invalid session id: %s", request.SessionId),
			Link:     &depi_grpc.ResourceLink{},
			Resource: &depi_grpc.Resource{},
		})
		return nil
	}

	if !server.hasCapability(session.User, CapLinkRead) {
		stream.Send(&depi_grpc.GetDirtyLinksAsStreamResponse{
			Ok: false, Msg: fmt.Sprintf("user %s cannot read links", session.User.Name),
			Link:     &depi_grpc.ResourceLink{},
			Resource: &depi_grpc.Resource{},
		})
		return nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	dirtyLinks, err := branch.GetDirtyLinks(&model.ResourceGroupKey{
		ToolId: request.ToolId, URL: request.URL,
	}, request.WithInferred)

	if err != nil {
		stream.Send(&depi_grpc.GetDirtyLinksAsStreamResponse{
			Ok: false, Msg: fmt.Sprintf("error reading dirty links: %+v", err),
			Link:     &depi_grpc.ResourceLink{},
			Resource: &depi_grpc.Resource{},
		})
		return nil
	}

	for _, link := range dirtyLinks {
		if server.isAuthorized(session.User, CapLinkRead, []string{
			link.FromResourceGroup.ToolId, link.FromResourceGroup.URL,
			link.FromRes.URL, link.ToResourceGroup.ToolId,
			link.ToResourceGroup.URL, link.ToRes.URL,
		}) {
			stream.Send(&depi_grpc.GetDirtyLinksAsStreamResponse{
				Ok: true, Msg: "",
				Link:     link.ToGrpc(),
				Resource: link.ToRes.ToGrpc(link.ToResourceGroup),
			})
		} else {
			log.Printf("user %s is not authorized to read linke %s %s %s -> %s %s %s\n",
				link.FromResourceGroup.ToolId, link.FromResourceGroup.URL,
				link.FromRes.URL, link.ToResourceGroup.ToolId,
				link.ToResourceGroup.URL, link.ToRes.URL)
		}
	}

	return nil
}

func (server *Server) MarkLinksClean(ctx context.Context, request *depi_grpc.MarkLinksCleanRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	if !server.hasCapability(session.User, CapLinkMarkClean) {
		return server.failureResponse(fmt.Sprintf(
			"user %s is not authorized to mark links clean", session.User.Name)), nil
	}

	for _, link := range request.Links {
		if !server.isAuthorized(session.User, CapLinkMarkClean, []string{
			link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL,
			link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL,
		}) {
			return server.failureResponse(fmt.Sprintf(
				"user %s is not authorized to mark link %s %s %s -> %s %s %s clean", session.User.Name,
				link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL,
				link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL,
			)), nil
		}
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	linksToClean := make([]*model.Link, len(request.Links))
	for i, link := range request.Links {
		linksToClean[i] = model.NewLinkFromGrpcLinkRef(link)
	}

	err := branch.MarkLinksClean(linksToClean, request.PropagateCleanliness)
	if err != nil {
		return server.failureResponse(fmt.Sprintf(
			"error cleaning links: %+v", err)), nil
	}

	branch.SaveBranchState()

	if len(linksToClean) > 0 {
		updates := make([]*depi_grpc.Update, len(linksToClean))
		for i, link := range linksToClean {
			updates[i] = &depi_grpc.Update{
				UpdateType: depi_grpc.UpdateType_MarkLinkClean,
				UpdateData: &depi_grpc.Update_Link{
					Link: link.ToGrpcResourceLink(),
				},
			}
		}
		depiUpdate := &depi_grpc.DepiUpdate{
			Ok: true, Msg: "", Updates: updates,
		}
		server.sessionLock.Lock()
		for _, session := range server.sessions {
			if session.Branch.GetName() != branch.GetName() {
				continue
			}
			if session.WatchingDepi {
				session.DepiUpdates.Push(depiUpdate)
			}
		}
		server.sessionLock.Unlock()

		for _, link := range linksToClean {
			server.writeAuditLogEntry(session.User.Name, "CleanedLink",
				fmt.Sprintf("fromToolId=%s;fromRgURL=%s;fromURL=%s;toToolId=%s;toRgURL=%s;toURL=%s",
					link.FromRes.ToolId, link.FromRes.ResourceGroupURL, link.FromRes.URL,
					link.ToRes.ToolId, link.ToRes.ResourceGroupURL, link.ToRes.URL))
		}
	}
	return server.successResponse(), nil
}

func (server *Server) MarkInferredDirtinessClean(ctx context.Context, request *depi_grpc.MarkInferredDirtinessCleanRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	if !server.hasCapability(session.User, CapLinkMarkClean) {
		return server.failureResponse(fmt.Sprintf(
			"user %s is not authorized to mark links clean", session.User.Name)), nil
	}

	targetLink := model.NewLinkFromGrpcLinkRef(request.Link)

	if !server.isAuthorized(session.User, CapLinkMarkClean, []string{
		targetLink.FromRes.ToolId, targetLink.FromRes.ResourceGroupURL, targetLink.FromRes.URL,
		targetLink.ToRes.ToolId, targetLink.ToRes.ResourceGroupURL, targetLink.ToRes.URL,
	}) {
		return server.failureResponse(fmt.Sprintf(
			"user %s is not authorized to mark link %s %s %s -> %s %s %s clean", session.User.Name,
			targetLink.FromRes.ToolId, targetLink.FromRes.ResourceGroupURL, targetLink.FromRes.URL,
			targetLink.ToRes.ToolId, targetLink.ToRes.ResourceGroupURL, targetLink.ToRes.URL,
		)), nil
	}

	dirtinessSource := model.NewResourceRefFromGrpc(request.DirtinessSource)

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	cleaned, err := branch.MarkInferredDirtinessClean(targetLink, dirtinessSource, request.PropagateCleanliness)
	if err != nil {
		return server.failureResponse(fmt.Sprintf(
			"error cleaning links: %+v", err)), nil
	}

	branch.SaveBranchState()

	if len(cleaned) > 0 {
		updates := make([]*depi_grpc.Update, len(cleaned))
		for i, link := range cleaned {
			updates[i] = &depi_grpc.Update{
				UpdateType: depi_grpc.UpdateType_MarkInferredLinkClean,
				UpdateData: &depi_grpc.Update_MarkInferredLinkClean{
					MarkInferredLinkClean: &depi_grpc.InferredLinkClean{
						Link:     link.Link.ToGrpc(),
						Resource: link.ResourceRef.ToGrpc(),
					},
				},
			}
		}
		depiUpdate := &depi_grpc.DepiUpdate{
			Ok: true, Msg: "", Updates: updates,
		}
		server.sessionLock.Lock()
		for _, session := range server.sessions {
			if session.Branch.GetName() != branch.GetName() {
				continue
			}
			if session.WatchingDepi {
				session.DepiUpdates.Push(depiUpdate)
			}
		}
		server.sessionLock.Unlock()

		for _, link := range cleaned {
			server.writeAuditLogEntry(session.User.Name, "CleanedInferredLink",
				fmt.Sprintf("fromToolId=%s;fromRgURL=%s;fromURL=%s;toToolId=%s;toRgURL=%s;toURL=%s;sourceToolId=%s;sourceRgURL=%s;sourceURL=%s;propagate=%t",
					link.Link.FromRes.ToolId, link.Link.FromRes.ResourceGroupURL, link.Link.FromRes.URL,
					link.Link.ToRes.ToolId, link.Link.ToRes.ResourceGroupURL, link.Link.ToRes.URL,
					link.ResourceRef.ToolId, link.ResourceRef.ResourceGroupURL, link.ResourceRef.URL,
					request.PropagateCleanliness))
		}
	}
	return server.successResponse(), nil
}

func (server *Server) GetBidirectionalChanges(ctx context.Context, request *depi_grpc.GetBidirectionalChangesRequest) (*depi_grpc.GetBidirectionalChangesResponse, error) {
	//TODO implement me
	panic("implement me")
}

func (server *Server) ApproveBidirectionalChange(ctx context.Context, request *depi_grpc.ApproveBidirectionalChangeRequest) (*depi_grpc.GenericResponse, error) {
	//TODO implement me
	panic("implement me")
}

func (server *Server) GetResourceGroups(ctx context.Context, request *depi_grpc.GetResourceGroupsRequest) (*depi_grpc.GetResourceGroupsResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.GetResourceGroupsResponse{
			Ok:             false,
			Msg:            fmt.Sprintf("invalid session id: %s", request.SessionId),
			ResourceGroups: []*depi_grpc.ResourceGroup{},
		}, nil
	}

	if !server.hasCapability(session.User, CapResGroupRead) {
		return &depi_grpc.GetResourceGroupsResponse{
			Ok:             false,
			Msg:            fmt.Sprintf("user %s not authorized to read any resource group", session.User.Name),
			ResourceGroups: []*depi_grpc.ResourceGroup{},
		}, nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	resourceGroups, err := branch.GetResourceGroups()
	if err != nil {
		return &depi_grpc.GetResourceGroupsResponse{
			Ok:             false,
			Msg:            fmt.Sprintf("error reading resource groups: %+v", err),
			ResourceGroups: []*depi_grpc.ResourceGroup{},
		}, nil
	}

	grpcResourceGroups := make([]*depi_grpc.ResourceGroup, len(resourceGroups))
	for i, rg := range resourceGroups {
		grpcResourceGroups[i] = rg.ToGrpc(false)
	}

	return &depi_grpc.GetResourceGroupsResponse{
		Ok: true, Msg: "",
		ResourceGroups: grpcResourceGroups,
	}, nil
}

func (server *Server) GetResourceGroupsForTag(ctx context.Context, request *depi_grpc.GetResourceGroupsForTagRequest) (*depi_grpc.GetResourceGroupsResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.GetResourceGroupsResponse{
			Ok:             false,
			Msg:            fmt.Sprintf("invalid session id: %s", request.SessionId),
			ResourceGroups: []*depi_grpc.ResourceGroup{},
		}, nil
	}

	if !server.hasCapability(session.User, CapResGroupRead) {
		return &depi_grpc.GetResourceGroupsResponse{
			Ok:             false,
			Msg:            fmt.Sprintf("user %s not authorized to read any resource group", session.User.Name),
			ResourceGroups: []*depi_grpc.ResourceGroup{},
		}, nil
	}

	branch, err := server.db.GetTag(request.Tag)
	if err != nil {
		return &depi_grpc.GetResourceGroupsResponse{
			Ok:             false,
			Msg:            fmt.Sprintf("unable to access tag %s: %+v", request.Tag, err),
			ResourceGroups: []*depi_grpc.ResourceGroup{},
		}, nil
	}

	branch.Lock()
	defer branch.Unlock()

	resourceGroups, err := branch.GetResourceGroups()
	if err != nil {
		return &depi_grpc.GetResourceGroupsResponse{
			Ok:             false,
			Msg:            fmt.Sprintf("error reading resource groups: %+v", err),
			ResourceGroups: []*depi_grpc.ResourceGroup{},
		}, nil
	}

	grpcResourceGroups := make([]*depi_grpc.ResourceGroup, len(resourceGroups))
	for i, rg := range resourceGroups {
		grpcResourceGroups[i] = rg.ToGrpc(false)
	}

	return &depi_grpc.GetResourceGroupsResponse{
		Ok: true, Msg: "",
		ResourceGroups: grpcResourceGroups,
	}, nil
}

func (server *Server) GetResources(ctx context.Context, request *depi_grpc.GetResourcesRequest) (*depi_grpc.GetResourcesResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.GetResourcesResponse{
			Ok:        false,
			Msg:       fmt.Sprintf("invalid session id: %s", request.SessionId),
			Resources: []*depi_grpc.Resource{},
		}, nil
	}

	if !server.hasCapability(session.User, CapResourceRead) {
		return &depi_grpc.GetResourcesResponse{
			Ok:        false,
			Msg:       fmt.Sprintf("user %s not authorized to read any resource", session.User.Name),
			Resources: []*depi_grpc.Resource{},
		}, nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	patterns := []*model.ResourceRefPattern{}
	for _, patternGrpc := range request.Patterns {
		pattern := model.NewResourceRefPatternFromGrpc(patternGrpc)
		if server.isAuthorized(session.User, CapResGroupRead, []string{
			pattern.ToolId, pattern.ResourceGroupURL,
		}) {
			patterns = append(patterns, pattern)
		}
	}

	respResources := []*depi_grpc.Resource{}
	resources, err := branch.GetResources(patterns, request.IncludeDeleted)
	if err != nil {
		return &depi_grpc.GetResourcesResponse{
			Ok:        false,
			Msg:       fmt.Sprintf("error reading resources: %+v", err),
			Resources: []*depi_grpc.Resource{},
		}, nil
	}

	for _, res := range resources {
		if server.isAuthorized(session.User, CapResourceRead, []string{
			res.ResourceGroup.ToolId, res.ResourceGroup.URL, res.Resource.URL,
		}) {
			respResources = append(respResources, res.Resource.ToGrpc(res.ResourceGroup))
		}
	}

	return &depi_grpc.GetResourcesResponse{
		Ok: true, Msg: "", Resources: respResources,
	}, nil
}

func (server *Server) GetResourcesAsStream(request *depi_grpc.GetResourcesRequest, server2 depi_grpc.Depi_GetResourcesAsStreamServer) error {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		server2.Send(&depi_grpc.GetResourcesAsStreamResponse{
			Ok:       false,
			Msg:      fmt.Sprintf("invalid session id: %s", request.SessionId),
			Resource: &depi_grpc.Resource{},
		})
		return nil
	}

	if !server.hasCapability(session.User, CapResourceRead) {
		server2.Send(&depi_grpc.GetResourcesAsStreamResponse{
			Ok:       false,
			Msg:      fmt.Sprintf("user %s not authorized to read any resource", session.User.Name),
			Resource: &depi_grpc.Resource{},
		})
		return nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	patterns := []*model.ResourceRefPattern{}
	for _, patternGrpc := range request.Patterns {
		pattern := model.NewResourceRefPatternFromGrpc(patternGrpc)
		if server.isAuthorized(session.User, CapResGroupRead, []string{
			pattern.ToolId, pattern.ResourceGroupURL,
		}) {
			patterns = append(patterns, pattern)
		}
	}

	resources, err := branch.GetResources(patterns, request.IncludeDeleted)
	if err != nil {
		server2.Send(&depi_grpc.GetResourcesAsStreamResponse{
			Ok:       false,
			Msg:      fmt.Sprintf("error reading resources: %+v", err),
			Resource: &depi_grpc.Resource{},
		})
		return nil
	}

	for _, res := range resources {
		if server.isAuthorized(session.User, CapResourceRead, []string{
			res.ResourceGroup.ToolId, res.ResourceGroup.URL, res.Resource.URL,
		}) {
			server2.Send(&depi_grpc.GetResourcesAsStreamResponse{
				Ok: true, Msg: "", Resource: res.Resource.ToGrpc(res.ResourceGroup),
			})
		}
	}
	return nil
}

func (server *Server) GetLinks(ctx context.Context, request *depi_grpc.GetLinksRequest) (*depi_grpc.GetLinksResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.GetLinksResponse{
			Ok:            false,
			Msg:           fmt.Sprintf("invalid session id: %s", request.SessionId),
			ResourceLinks: []*depi_grpc.ResourceLink{},
		}, nil
	}

	if !server.hasCapability(session.User, CapLinkRead) {
		return &depi_grpc.GetLinksResponse{
			Ok:            false,
			Msg:           fmt.Sprintf("user %s not authorized to read any link", session.User.Name),
			ResourceLinks: []*depi_grpc.ResourceLink{},
		}, nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	patterns := make([]*model.ResourceLinkPattern, len(request.Patterns))
	for i, pattern := range request.Patterns {
		patterns[i] = model.NewResourceLinkPatternFromGrpc(pattern)
	}

	respLinks := []*depi_grpc.ResourceLink{}
	links, err := branch.GetLinks(patterns)
	if err != nil {
		return &depi_grpc.GetLinksResponse{
			Ok:            false,
			Msg:           fmt.Sprintf("error fetching links: %+v", err),
			ResourceLinks: []*depi_grpc.ResourceLink{},
		}, nil
	}

	for _, link := range links {
		if server.isAuthorized(session.User, CapLinkRead, []string{
			link.FromResourceGroup.ToolId, link.FromResourceGroup.URL,
			link.FromRes.URL, link.ToResourceGroup.ToolId, link.ToResourceGroup.URL,
			link.ToRes.URL,
		}) {
			respLinks = append(respLinks, link.ToGrpc())
		}
	}
	return &depi_grpc.GetLinksResponse{
		Ok: true, Msg: "", ResourceLinks: respLinks,
	}, nil
}

func (server *Server) GetAllLinksAsStream(request *depi_grpc.GetAllLinksAsStreamRequest, server2 depi_grpc.Depi_GetAllLinksAsStreamServer) error {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		server2.Send(&depi_grpc.GetLinksAsStreamResponse{
			Ok:           false,
			Msg:          fmt.Sprintf("invalid session id: %s", request.SessionId),
			ResourceLink: &depi_grpc.ResourceLink{},
		})
		return nil
	}

	if !server.hasCapability(session.User, CapLinkRead) {
		server2.Send(&depi_grpc.GetLinksAsStreamResponse{
			Ok:           false,
			Msg:          fmt.Sprintf("user %s not authorized to read any link", session.User.Name),
			ResourceLink: &depi_grpc.ResourceLink{},
		})

		return nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	err := branch.GetAllLinksAsStream(request.IncludeDeleted, func(link *model.LinkWithResources) {

		if server.isAuthorized(session.User, CapLinkRead, []string{
			link.FromResourceGroup.ToolId, link.FromResourceGroup.URL,
			link.FromRes.URL, link.ToResourceGroup.ToolId, link.ToResourceGroup.URL,
			link.ToRes.URL,
		}) {
			server2.Send(&depi_grpc.GetLinksAsStreamResponse{
				Ok: true, Msg: "", ResourceLink: link.ToGrpc(),
			})
		} else {
			log.Printf("User is not authorized to read link: %+v\n", link)
		}
	})

	if err != nil {
		server2.Send(&depi_grpc.GetLinksAsStreamResponse{
			Ok:           false,
			Msg:          fmt.Sprintf("error reading links: %+v", err),
			ResourceLink: &depi_grpc.ResourceLink{},
		})
	}

	return nil
}

func (server *Server) GetLinksAsStream(request *depi_grpc.GetLinksRequest, server2 depi_grpc.Depi_GetLinksAsStreamServer) error {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		server2.Send(&depi_grpc.GetLinksAsStreamResponse{
			Ok:           false,
			Msg:          fmt.Sprintf("invalid session id: %s", request.SessionId),
			ResourceLink: &depi_grpc.ResourceLink{},
		})
		return nil
	}

	if !server.hasCapability(session.User, CapLinkRead) {
		server2.Send(&depi_grpc.GetLinksAsStreamResponse{
			Ok:           false,
			Msg:          fmt.Sprintf("user %s not authorized to read any link", session.User.Name),
			ResourceLink: &depi_grpc.ResourceLink{},
		})

		return nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	patterns := make([]*model.ResourceLinkPattern, len(request.Patterns))
	for i, pattern := range request.Patterns {
		patterns[i] = model.NewResourceLinkPatternFromGrpc(pattern)
	}

	err := branch.GetLinksAsStream(patterns, func(link *model.LinkWithResources) {
		if server.isAuthorized(session.User, CapLinkRead, []string{
			link.FromResourceGroup.ToolId, link.FromResourceGroup.URL,
			link.FromRes.URL, link.ToResourceGroup.ToolId, link.ToResourceGroup.URL,
			link.ToRes.URL,
		}) {
			server2.Send(&depi_grpc.GetLinksAsStreamResponse{
				Ok: true, Msg: "", ResourceLink: link.ToGrpc(),
			})
		}
	})

	if err != nil {
		server2.Send(&depi_grpc.GetLinksAsStreamResponse{
			Ok:           false,
			Msg:          fmt.Sprintf("error reading links: %+v", err),
			ResourceLink: &depi_grpc.ResourceLink{},
		})
	}

	return nil
}

func (server *Server) GetDependencyGraph(ctx context.Context, request *depi_grpc.GetDependencyGraphRequest) (*depi_grpc.GetDependencyGraphResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.GetDependencyGraphResponse{
			Ok:    false,
			Msg:   fmt.Sprintf("invalid session id: %s", request.SessionId),
			Links: []*depi_grpc.ResourceLink{},
		}, nil
	}

	if !server.hasCapability(session.User, CapLinkRead) {
		return &depi_grpc.GetDependencyGraphResponse{
			Ok:    false,
			Msg:   fmt.Sprintf("user %s not authorized to read any link", session.User.Name),
			Links: []*depi_grpc.ResourceLink{},
		}, nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	resourceRef := model.NewResourceRefFromGrpc(request.Resource)
	parentResource, err := branch.GetResource(resourceRef, false)

	if err != nil {
		return &depi_grpc.GetDependencyGraphResponse{
			Ok:    false,
			Msg:   fmt.Sprintf("parent resource not found"),
			Links: []*depi_grpc.ResourceLink{},
		}, nil
	}

	if parentResource == nil {
		return &depi_grpc.GetDependencyGraphResponse{
			Ok:    false,
			Msg:   fmt.Sprintf("parent resource not found"),
			Links: []*depi_grpc.ResourceLink{},
		}, nil
	}

	links, err := branch.GetDependencyGraph(resourceRef,
		request.DependenciesType == depi_grpc.DependenciesType_Dependencies, int(request.MaxDepth))
	if err != nil {
		return &depi_grpc.GetDependencyGraphResponse{
			Ok:    false,
			Msg:   fmt.Sprintf("error fetching dependency graph: %+v", err),
			Links: []*depi_grpc.ResourceLink{},
		}, nil
	}

	respLinks := []*depi_grpc.ResourceLink{}
	for _, link := range links {
		if server.isAuthorized(session.User, CapLinkRead, []string{
			link.FromResourceGroup.ToolId, link.FromResourceGroup.URL, link.FromRes.URL,
			link.ToResourceGroup.ToolId, link.ToResourceGroup.URL, link.ToRes.URL,
		}) {
			respLinks = append(respLinks, link.ToGrpc())
		}
	}

	return session.printGRPC(&depi_grpc.GetDependencyGraphResponse{
		Ok: true, Msg: "", Resource: parentResource.Resource.ToGrpc(parentResource.ResourceGroup),
		Links: respLinks,
	}).(*depi_grpc.GetDependencyGraphResponse), nil
}

func (server *Server) GetBranchList(ctx context.Context, request *depi_grpc.GetBranchListRequest) (*depi_grpc.GetBranchListResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.GetBranchListResponse{
			Ok:       false,
			Msg:      fmt.Sprintf("invalid session id: %s", request.SessionId),
			Branches: []string{},
			Tags:     []string{},
		}, nil
	}

	if !server.hasCapability(session.User, CapBranchList) {
		return &depi_grpc.GetBranchListResponse{
			Ok:       false,
			Msg:      fmt.Sprintf("user %s not authorized to read any link", session.User.Name),
			Branches: []string{},
			Tags:     []string{},
		}, nil
	}

	branches, err := server.db.GetBranchList()
	if err != nil {
		return &depi_grpc.GetBranchListResponse{
			Ok:       false,
			Msg:      fmt.Sprintf("error retrieving branch list: %+v", err),
			Branches: []string{},
			Tags:     []string{},
		}, nil
	}

	tags, err := server.db.GetTagList()
	if err != nil {
		return &depi_grpc.GetBranchListResponse{
			Ok:       false,
			Msg:      fmt.Sprintf("error retrieving tag list: %+v", err),
			Branches: []string{},
			Tags:     []string{},
		}, nil
	}
	return &depi_grpc.GetBranchListResponse{
		Ok: true, Msg: "", Branches: branches, Tags: tags,
	}, nil
}

func (server *Server) UpdateDepi(ctx context.Context, request *depi_grpc.UpdateDepiRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()
	updates := []*depi_grpc.Update{}

	for _, update := range request.Updates {
		if update.UpdateType == depi_grpc.UpdateType_AddResource {
			updateResource := update.GetResource()
			rg := model.NewResourceGroupFromGrpcResource(updateResource)
			res := model.NewResourceFromGrpc(updateResource)

			if server.isAuthorized(session.User, CapResourceAdd, []string{
				rg.ToolId, rg.URL, res.URL,
			}) {
				added, _ := branch.AddResource(rg, res)
				if added {
					updates = append(updates, update)
				}
				server.writeAuditLogEntry(session.User.Name, "AddResource",
					fmt.Sprintf("toolId=%s;rgURL=%s;URL=%s;name=%s;id=%s",
						rg.ToolId, rg.URL, res.URL, res.Name, res.Id))
			} else {
				log.Printf("User %s is not allowed to add resource {} {} {}\n",
					session.User.Name, rg.ToolId, rg.URL, res.URL)
			}
		} else if update.UpdateType == depi_grpc.UpdateType_RemoveResource {
			updateResource := update.GetResource()
			rg := model.NewResourceGroupFromGrpcResource(updateResource)
			res := model.NewResourceFromGrpc(updateResource)

			if server.isAuthorized(session.User, CapResourceRemove, []string{
				rg.ToolId, rg.URL, res.URL,
			}) {
				removed, _ := branch.RemoveResourceRef(
					model.NewResourceRefFromRGAndRes(rg, res))
				if removed {
					updates = append(updates, update)
				}
				server.writeAuditLogEntry(session.User.Name, "RemoveResource",
					fmt.Sprintf("toolId=%s;rgURL=%s;URL=%s;name=%s;id=%s",
						rg.ToolId, rg.URL, res.URL, res.Name, res.Id))
			} else {
				log.Printf("User %s is not allowed to remove resource {} {} {}\n",
					session.User.Name, rg.ToolId, rg.URL, res.URL)
			}
		} else if update.UpdateType == depi_grpc.UpdateType_AddLink {
			updateLink := update.GetLink()
			fromResourceGroup := model.NewResourceGroupFromGrpcResource(updateLink.FromRes)
			fromRes := model.NewResourceFromGrpc(updateLink.FromRes)
			toResourceGroup := model.NewResourceGroupFromGrpcResource(updateLink.ToRes)
			toRes := model.NewResourceFromGrpc(updateLink.ToRes)
			if server.isAuthorized(session.User, CapLinkAdd, []string{
				updateLink.FromRes.ToolId, updateLink.FromRes.ResourceGroupURL, updateLink.FromRes.URL,
				updateLink.ToRes.ToolId, updateLink.ToRes.ResourceGroupURL, updateLink.ToRes.URL,
			}) {
				branch.AddResource(fromResourceGroup, fromRes)

				branch.AddResource(toResourceGroup, toRes)

				added, _ := branch.AddLink(
					&model.LinkWithResources{
						FromResourceGroup: fromResourceGroup,
						FromRes:           fromRes,
						ToResourceGroup:   toResourceGroup,
						ToRes:             toRes,
						Dirty:             false,
						LastCleanVersion:  fromResourceGroup.Version,
					})
				if added {
					updates = append(updates, update)
					server.writeAuditLogEntry(session.User.Name, "LinkResources",
						fmt.Sprintf("fromToolId=%s;fromRgURL=%s;fromURL=%s;toToolId=%s;toRgUrl=%s;toURL=%s",
							fromResourceGroup.ToolId, fromResourceGroup.URL, fromRes.URL,
							toResourceGroup.ToolId, toResourceGroup.URL, toRes.URL))
				}
			} else {
				log.Printf("User %s not authorized to add link %s %s %s -> %s %s %s\n",
					fromResourceGroup.ToolId, fromResourceGroup.URL, fromRes.URL,
					toResourceGroup.ToolId, toResourceGroup.URL, toRes.URL)
			}
		} else if update.UpdateType == depi_grpc.UpdateType_RemoveLink {
			updateLink := update.GetLink()
			fromResourceGroup := model.NewResourceGroupFromGrpcResource(updateLink.FromRes)
			fromRes := model.NewResourceFromGrpc(updateLink.FromRes)
			toResourceGroup := model.NewResourceGroupFromGrpcResource(updateLink.ToRes)
			toRes := model.NewResourceFromGrpc(updateLink.ToRes)
			if server.isAuthorized(session.User, CapLinkRemove, []string{
				updateLink.FromRes.ToolId, updateLink.FromRes.ResourceGroupURL, updateLink.FromRes.URL,
				updateLink.ToRes.ToolId, updateLink.ToRes.ResourceGroupURL, updateLink.ToRes.URL,
			}) {
				removed, _ := branch.RemoveLink(
					&model.Link{
						FromRes: model.NewResourceRefFromRGAndRes(fromResourceGroup, fromRes),
						ToRes:   model.NewResourceRefFromRGAndRes(toResourceGroup, toRes),
					})
				if removed {
					updates = append(updates, update)
					server.writeAuditLogEntry(session.User.Name, "UnlinkResources",
						fmt.Sprintf("fromToolId=%s;fromRgURL=%s;fromURL=%s;toToolId=%s;toRgUrl=%s;toURL=%s",
							fromResourceGroup.ToolId, fromResourceGroup.URL, fromRes.URL,
							toResourceGroup.ToolId, toResourceGroup.URL, toRes.URL))
				}
			} else {
				log.Printf("User %s not authorized to remove link %s %s %s -> %s %s %s\n",
					fromResourceGroup.ToolId, fromResourceGroup.URL, fromRes.URL,
					toResourceGroup.ToolId, toResourceGroup.URL, toRes.URL)
			}
		}
	}
	branch.SaveBranchState()

	if len(updates) > 0 {
		depiUpdate := &depi_grpc.DepiUpdate{Ok: true, Msg: "", Updates: updates}
		for _, session := range server.sessions {
			if session.Branch.GetName() != branch.GetName() {
				continue
			}
			if session.WatchingDepi {
				session.DepiUpdates.Push(depiUpdate)
			}
		}
	}

	return server.successResponse(), nil
}

func (server *Server) WatchBlackboard(request *depi_grpc.WatchBlackboardRequest, server2 depi_grpc.Depi_WatchBlackboardServer) error {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		server2.Send(&depi_grpc.BlackboardUpdate{
			Ok: false, Msg: fmt.Sprintf("Invalid session id: %s", request.SessionId),
			Updates: []*depi_grpc.Update{},
		})
		return nil
	}
	session.WatchingBlackboard = true

	for session.WatchingBlackboard {
		item, err := session.BlackboardUpdates.PopWait()
		if err != nil {
			break
		}
		if !item.Ok && item.Msg == "timeout" {
			break
		}
		server2.Send(item)
	}

	session.WatchingBlackboard = false

	return nil

}

func (server *Server) WatchDepi(request *depi_grpc.WatchDepiRequest, server2 depi_grpc.Depi_WatchDepiServer) error {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		server2.Send(&depi_grpc.DepiUpdate{
			Ok: false, Msg: fmt.Sprintf("Invalid session id: %s", request.SessionId),
			Updates: []*depi_grpc.Update{},
		})
		return nil
	}

	session.WatchingDepi = true

	for session.WatchingDepi {
		item, err := session.DepiUpdates.PopWait()
		if err != nil {
			break
		}
		if !item.Ok && item.Msg == "timeout" {
			break
		}
		server2.Send(item)
	}

	session.WatchingDepi = false

	return nil
}

func (server *Server) UnwatchBlackboard(ctx context.Context, request *depi_grpc.UnwatchBlackboardRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	session.WatchingBlackboard = false
	session.BlackboardUpdates.Push(&depi_grpc.BlackboardUpdate{
		Ok: false, Msg: "timeout", Updates: []*depi_grpc.Update{},
	})
	return server.successResponse(), nil
}

func (server *Server) UnwatchDepi(ctx context.Context, request *depi_grpc.UnwatchDepiRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	session.WatchingDepi = false
	session.DepiUpdates.Push(&depi_grpc.DepiUpdate{
		Ok: false, Msg: "timeout", Updates: []*depi_grpc.Update{},
	})
	return server.successResponse(), nil

}

func (server *Server) AddResourceGroup(ctx context.Context, request *depi_grpc.AddResourceGroupRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	if !server.hasCapability(session.User, CapResGroupAdd) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to add a resource group", session.User.Name)), nil
	}

	if !server.isAuthorized(session.User, CapResGroupAdd, []string{
		request.ResourceGroup.ToolId, request.ResourceGroup.URL,
	}) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to add resource group %s %s", session.User.Name,
			request.ResourceGroup.ToolId, request.ResourceGroup.URL)), nil
	}

	_, err := branch.AddResource(model.NewResourceGroupFromGrpc(request.GetResourceGroup()), nil)
	if err != nil {
		return server.errorResponse("Error adding resource group", err), nil
	}

	branch.SaveBranchState()

	depiUpdate := &depi_grpc.DepiUpdate{
		Ok:  true,
		Msg: "",
		Updates: []*depi_grpc.Update{
			{
				UpdateType: depi_grpc.UpdateType_AddResourceGroup,
				UpdateData: &depi_grpc.Update_AddResourceGroup{
					AddResourceGroup: &depi_grpc.ResourceGroup{
						ToolId: request.GetResourceGroup().ToolId,
						URL:    request.GetResourceGroup().URL,
					},
				},
			},
		},
	}
	for _, session := range server.sessions {
		if session.Branch.GetName() != branch.GetName() {
			continue
		}
		if session.WatchingDepi {
			session.DepiUpdates.Push(depiUpdate)
		}
	}

	server.writeAuditLogEntry(session.User.Name, "EditResourceGroup",
		fmt.Sprintf("toolId=%s;URL=%s;name=%s;version=%s",
			request.ResourceGroup.ToolId,
			request.ResourceGroup.URL,
			request.ResourceGroup.Name,
			request.ResourceGroup.Version))
	return server.successResponse(), nil
}

func (server *Server) EditResourceGroup(ctx context.Context, request *depi_grpc.EditResourceGroupRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	if !server.hasCapability(session.User, CapResGroupChange) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to change a resource group", session.User.Name)), nil
	}

	if !server.isAuthorized(session.User, CapResGroupChange, []string{
		request.ResourceGroup.ToolId, request.ResourceGroup.URL,
	}) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to change resource group %s %s", session.User.Name,
			request.ResourceGroup.ToolId, request.ResourceGroup.URL)), nil
	}
	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	err := branch.EditResourceGroup(&model.ResourceGroup{
		ToolId: request.ResourceGroup.ToolId,
		URL:    request.ResourceGroup.URL,
	}, &model.ResourceGroup{
		ToolId:  request.ResourceGroup.NewToolId,
		URL:     request.ResourceGroup.New_URL,
		Name:    request.ResourceGroup.NewName,
		Version: request.ResourceGroup.NewVersion,
	})
	if err != nil {
		return server.errorResponse("error editing resource group", err), nil
	}

	branch.SaveBranchState()

	depiUpdate := &depi_grpc.DepiUpdate{
		Ok:  true,
		Msg: "",
		Updates: []*depi_grpc.Update{
			{
				UpdateType: depi_grpc.UpdateType_EditResourceGroup,
				UpdateData: &depi_grpc.Update_EditResourceGroup{
					EditResourceGroup: &depi_grpc.ResourceGroupEdit{
						ToolId:     request.ResourceGroup.ToolId,
						URL:        request.ResourceGroup.URL,
						NewToolId:  request.ResourceGroup.NewToolId,
						New_URL:    request.ResourceGroup.New_URL,
						NewName:    request.ResourceGroup.NewName,
						NewVersion: request.ResourceGroup.NewVersion,
					},
				},
			},
		},
	}
	for _, session := range server.sessions {
		if session.Branch.GetName() != branch.GetName() {
			continue
		}
		if session.WatchingDepi {
			session.DepiUpdates.Push(depiUpdate)
		}
	}

	server.writeAuditLogEntry(session.User.Name, "EditResourceGroup",
		fmt.Sprintf("toolId=%s;URL=%s;newToolId=%s;newURL=%s;newName=%s;newVersion=%s",
			request.ResourceGroup.ToolId,
			request.ResourceGroup.URL,
			request.ResourceGroup.NewToolId,
			request.ResourceGroup.New_URL,
			request.ResourceGroup.NewName,
			request.ResourceGroup.NewVersion))

	return server.successResponse(), nil
}

func (server *Server) RemoveResourceGroup(ctx context.Context, request *depi_grpc.RemoveResourceGroupRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	if !server.hasCapability(session.User, CapResGroupRemove) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to remove a resource group", session.User.Name)), nil
	}

	if !server.isAuthorized(session.User, CapResGroupRemove, []string{
		request.ResourceGroup.ToolId, request.ResourceGroup.URL,
	}) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to remove resource group %s %s", session.User.Name,
			request.ResourceGroup.ToolId, request.ResourceGroup.URL)), nil
	}
	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	err := branch.RemoveResourceGroup(request.ResourceGroup.ToolId, request.ResourceGroup.URL)
	if err != nil {
		return server.errorResponse("error removing resource group", err), nil
	}

	branch.SaveBranchState()

	depiUpdate := &depi_grpc.DepiUpdate{
		Ok:  true,
		Msg: "",
		Updates: []*depi_grpc.Update{
			{
				UpdateType: depi_grpc.UpdateType_RemoveResourceGroup,
				UpdateData: &depi_grpc.Update_RemoveResourceGroup{
					RemoveResourceGroup: &depi_grpc.ResourceGroupRef{
						ToolId: request.ResourceGroup.ToolId,
						URL:    request.ResourceGroup.URL,
					},
				},
			},
		},
	}
	for _, session := range server.sessions {
		if session.Branch.GetName() != branch.GetName() {
			continue
		}
		if session.WatchingDepi {
			session.DepiUpdates.Push(depiUpdate)
		}
	}

	server.writeAuditLogEntry(session.User.Name, "RemoveResourceGroup",
		fmt.Sprintf("toolId=%s;URL=%s",
			request.ResourceGroup.ToolId,
			request.ResourceGroup.URL))

	return server.successResponse(), nil
}

func (server *Server) AddResource(ctx context.Context, request *depi_grpc.AddResourceRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	if !server.hasCapability(session.User, CapResourceAdd) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to add a resource group", session.User.Name)), nil
	}

	if !server.isAuthorized(session.User, CapResourceAdd, []string{
		request.ToolId, request.ResourceGroupURL, request.URL, request.Name, request.Id,
	}) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to add resource %s %s", session.User.Name,
			request.ToolId, request.ResourceGroupURL, request.URL)), nil
	}

	rg, err := branch.GetResourceGroup(request.ToolId, request.ResourceGroupURL)
	if err != nil {
		return session.errorResponse("error retrieving resource group", err), nil
	}

	res := &model.Resource{
		URL:  request.URL,
		Name: request.Name,
		Id:   request.Id,
	}
	_, err = branch.AddResource(rg, res)
	if err != nil {
		return server.errorResponse("Error adding resource", err), nil
	}

	branch.SaveBranchState()

	depiUpdate := &depi_grpc.DepiUpdate{
		Ok:  true,
		Msg: "",
		Updates: []*depi_grpc.Update{
			{
				UpdateType: depi_grpc.UpdateType_AddResource,
				UpdateData: &depi_grpc.Update_Resource{
					Resource: &depi_grpc.Resource{
						ToolId:           request.ToolId,
						ResourceGroupURL: request.ResourceGroupURL,
						URL:              request.URL,
						Name:             request.Name,
						Id:               request.Id,
					},
				},
			},
		},
	}
	for _, session := range server.sessions {
		if session.Branch.GetName() != branch.GetName() {
			continue
		}
		if session.WatchingDepi {
			session.DepiUpdates.Push(depiUpdate)
		}
	}

	server.writeAuditLogEntry(session.User.Name, "AddResource",
		fmt.Sprintf("toolId=%s;rgURL=%s;URL=%s;name=%s;id=%s",
			request.ToolId,
			request.ResourceGroupURL,
			request.URL,
			request.Name,
			request.Id))
	return server.successResponse(), nil
}

func (server *Server) LinkResources(ctx context.Context, request *depi_grpc.LinkResourcesRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	if !server.hasCapability(session.User, CapLinkAdd) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to create links", session.User.Name)), nil
	}

	if !server.isAuthorized(session.User, CapLinkAdd, []string{
		request.Link.FromRes.ToolId,
		request.Link.FromRes.ResourceGroupURL,
		request.Link.FromRes.URL,
		request.Link.ToRes.ToolId,
		request.Link.ToRes.ResourceGroupURL,
		request.Link.ToRes.URL,
	}) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to create link %s %s %s -> %s %s %s", session.User.Name,
			request.Link.FromRes.ToolId,
			request.Link.FromRes.ResourceGroupURL,
			request.Link.FromRes.URL,
			request.Link.ToRes.ToolId,
			request.Link.ToRes.ResourceGroupURL,
			request.Link.ToRes.URL)), nil
	}

	fromRgAndRes, err := branch.GetResource(model.NewResourceRefFromGrpc(request.Link.FromRes), false)
	if err != nil {
		return session.errorResponse("error retrieving resource", err), nil
	}

	toRgAndRes, err := branch.GetResource(model.NewResourceRefFromGrpc(request.Link.ToRes), false)
	if err != nil {
		return session.errorResponse("error retrieving resource", err), nil
	}

	linkWithResources := &model.LinkWithResources{
		FromResourceGroup: fromRgAndRes.ResourceGroup,
		FromRes:           fromRgAndRes.Resource,
		ToResourceGroup:   toRgAndRes.ResourceGroup,
		ToRes:             toRgAndRes.Resource,
	}
	_, err = branch.AddLink(linkWithResources)
	if err != nil {
		return server.errorResponse("Error adding resource", err), nil
	}

	branch.SaveBranchState()

	depiUpdate := &depi_grpc.DepiUpdate{
		Ok:  true,
		Msg: "",
		Updates: []*depi_grpc.Update{
			{
				UpdateType: depi_grpc.UpdateType_AddLink,
				UpdateData: &depi_grpc.Update_Link{
					Link: linkWithResources.ToGrpc(),
				},
			},
		},
	}
	for _, session := range server.sessions {
		if session.Branch.GetName() != branch.GetName() {
			continue
		}
		if session.WatchingDepi {
			session.DepiUpdates.Push(depiUpdate)
		}
	}

	server.writeAuditLogEntry(session.User.Name, "AddLink",
		fmt.Sprintf("fromToolId=%s;fromRgURL=%s;fromURL=%s;toToolId=%s;toRgURL=%s;toURL=%s",
			request.Link.FromRes.ToolId,
			request.Link.FromRes.ResourceGroupURL,
			request.Link.FromRes.URL,
			request.Link.ToRes.ToolId,
			request.Link.ToRes.ResourceGroupURL,
			request.Link.ToRes.URL))
	return server.successResponse(), nil
}

func (server *Server) UnlinkResources(ctx context.Context, request *depi_grpc.UnlinkResourcesRequest) (*depi_grpc.GenericResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return server.invalidSession(request.SessionId), nil
	}

	branch := session.Branch
	branch.Lock()
	defer branch.Unlock()

	if !server.hasCapability(session.User, CapLinkRemove) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to remove links", session.User.Name)), nil
	}

	if !server.isAuthorized(session.User, CapLinkRemove, []string{
		request.Link.FromRes.ToolId,
		request.Link.FromRes.ResourceGroupURL,
		request.Link.FromRes.URL,
		request.Link.ToRes.ToolId,
		request.Link.ToRes.ResourceGroupURL,
		request.Link.ToRes.URL,
	}) {
		return session.failureResponse(fmt.Sprintf(
			"User %s is not authorized to remove link %s %s %s -> %s %s %s", session.User.Name,
			request.Link.FromRes.ToolId,
			request.Link.FromRes.ResourceGroupURL,
			request.Link.FromRes.URL,
			request.Link.ToRes.ToolId,
			request.Link.ToRes.ResourceGroupURL,
			request.Link.ToRes.URL)), nil
	}

	link := &model.Link{
		FromRes: model.NewResourceRefFromGrpc(request.Link.FromRes),
		ToRes:   model.NewResourceRefFromGrpc(request.Link.ToRes),
	}
	_, err := branch.RemoveLink(link)
	if err != nil {
		return server.errorResponse("Error removing resource", err), nil
	}

	branch.SaveBranchState()

	depiUpdate := &depi_grpc.DepiUpdate{
		Ok:  true,
		Msg: "",
		Updates: []*depi_grpc.Update{
			{
				UpdateType: depi_grpc.UpdateType_RemoveLink,
				UpdateData: &depi_grpc.Update_RemoveLink{
					RemoveLink: link.ToGrpc(),
				},
			},
		},
	}
	for _, session := range server.sessions {
		if session.Branch.GetName() != branch.GetName() {
			continue
		}
		if session.WatchingDepi {
			session.DepiUpdates.Push(depiUpdate)
		}
	}

	server.writeAuditLogEntry(session.User.Name, "AddLink",
		fmt.Sprintf("fromToolId=%s;fromRgURL=%s;fromURL=%s;toToolId=%s;toRgURL=%s;toURL=%s",
			request.Link.FromRes.ToolId,
			request.Link.FromRes.ResourceGroupURL,
			request.Link.FromRes.URL,
			request.Link.ToRes.ToolId,
			request.Link.ToRes.ResourceGroupURL,
			request.Link.ToRes.URL))
	return server.successResponse(), nil
}

func (server *Server) CurrentBranch(ctx context.Context, request *depi_grpc.CurrentBranchRequest) (*depi_grpc.CurrentBranchResponse, error) {
	server.printGRPC(request)
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.CurrentBranchResponse{
			Ok: false, Msg: fmt.Sprintf("invalid session: %s", request.SessionId),
			Branch: "",
		}, nil
	}

	branch := session.Branch

	return &depi_grpc.CurrentBranchResponse{
		Ok: true, Msg: "", Branch: branch.GetName(),
	}, nil
}

func (server *Server) Ping(ctx context.Context, request *depi_grpc.PingRequest) (*depi_grpc.PingResponse, error) {
	session := server.getSession(request.SessionId)
	if session == nil {
		return &depi_grpc.PingResponse{
			Ok: false, Msg: fmt.Sprintf("invalid session: %s", request.SessionId),
			LoginToken: "",
		}, nil
	}
	token := server.generateToken(session.SessionId, session.User.Name)
	return &depi_grpc.PingResponse{
		Ok: true, Msg: "", LoginToken: token,
	}, nil
}

func (server *Server) mustEmbedUnimplementedDepiServer() {
	//TODO implement me
	panic("implement me")
}
