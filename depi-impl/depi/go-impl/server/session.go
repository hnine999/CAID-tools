package server

import (
	"fmt"
	"go-impl/depi_grpc"
	"go-impl/model"
	"go-impl/server/db"
	"google.golang.org/protobuf/encoding/prototext"
	"google.golang.org/protobuf/proto"
	"log"
	"reflect"
	"strings"
	"time"
)

type Session struct {
	WatchedGroups      map[model.ResourceGroupKey]bool
	WatchingResources  bool
	WatchingBlackboard bool
	WatchingDepi       bool
	LastRequest        time.Time
	ResourceUpdates    *Queue[*depi_grpc.ResourceUpdate]
	BlackboardUpdates  *Queue[*depi_grpc.BlackboardUpdate]
	DepiUpdates        *Queue[*depi_grpc.DepiUpdate]
	Branch             db.Branch
	User               *User
	SessionId          string
}

func NewSession(sessionId string, user *User, branch db.Branch) *Session {
	return &Session{
		Branch:            branch,
		User:              user,
		SessionId:         sessionId,
		ResourceUpdates:   NewQueue[*depi_grpc.ResourceUpdate](),
		BlackboardUpdates: NewQueue[*depi_grpc.BlackboardUpdate](),
		DepiUpdates:       NewQueue[*depi_grpc.DepiUpdate](),
		WatchedGroups:     map[model.ResourceGroupKey]bool{},
	}
}

func (session *Session) printGRPC(message proto.Message) proto.Message {
	messageType := reflect.TypeOf(message)
	parts := strings.Split(messageType.String(), ".")
	log.Printf("%s(%s): %s\n", parts[len(parts)-1], session.SessionId,
		prototext.Format(message))
	return message
}

func (session *Session) Close() {
	if session.WatchingResources {
		session.ResourceUpdates.Close()
	}
	if session.WatchingBlackboard {
		session.BlackboardUpdates.Close()
	}
	if session.WatchingDepi {
		session.DepiUpdates.Close()
	}
}

func (session *Session) successResponse() *depi_grpc.GenericResponse {
	return session.printGRPC(&depi_grpc.GenericResponse{
		Ok:  true,
		Msg: "",
	}).(*depi_grpc.GenericResponse)
}

func (session *Session) failureResponse(reason string) *depi_grpc.GenericResponse {
	return session.printGRPC(&depi_grpc.GenericResponse{
		Ok:  true,
		Msg: reason,
	}).(*depi_grpc.GenericResponse)
}

func (session *Session) errorResponse(reason string, err error) *depi_grpc.GenericResponse {
	return session.printGRPC(&depi_grpc.GenericResponse{
		Ok:  true,
		Msg: fmt.Sprintf("%s: %+v", reason, err),
	}).(*depi_grpc.GenericResponse)
}
