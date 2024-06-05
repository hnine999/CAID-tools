package main

import (
	"context"
	"flag"
	"fmt"
	"go-client/depi_grpc"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"io"
	"log"
)

var (
	addr = flag.String("addr", "192.168.1.86:5150", "the address to connect to")
)

func main() {
	flag.Parse()
	// Set up a connection to the server.
	conn, err := grpc.Dial(*addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("did not connect: %v", err)
	}
	defer conn.Close()
	c := depi_grpc.NewDepiClient(conn)

	resp, err := c.Login(context.Background(), &depi_grpc.LoginRequest{
		User:     "mark",
		Password: "mark",
		ToolId:   "git",
		Project:  "depi",
	})

	if err != nil {
		fmt.Printf("Error logging in: %+v\n", err)
		return
	}

	if !resp.Ok {
		fmt.Printf("Login failed\n")
	} else {
		fmt.Printf("Login succeeded\n")
	}

	sessionId := resp.SessionId

	stream, err := c.GetAllLinksAsStream(context.Background(),
		&depi_grpc.GetAllLinksAsStreamRequest{SessionId: sessionId})
	if err != nil {
		fmt.Printf("Error getting all links\n")
		return
	}

	for {
		link, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			fmt.Printf("Error fetching links\n")
			return
		}

		if !link.Ok {
			fmt.Printf("Error fetching links: %s\n", link.Msg)
		}

		fmt.Printf("%s %s %s -> %s %s %s\n",
			link.ResourceLink.FromRes.ToolId,
			link.ResourceLink.FromRes.ResourceGroupURL,
			link.ResourceLink.FromRes.URL,
			link.ResourceLink.ToRes.ToolId,
			link.ResourceLink.ToRes.ResourceGroupURL,
			link.ResourceLink.ToRes.URL)
	}
}
