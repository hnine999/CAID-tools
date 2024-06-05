package main

import (
	"context"
	"flag"
	"fmt"
	"github.com/gdamore/tcell/v2"
	"go-client/depi_grpc"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"log"
	"os"
	"strings"

	"github.com/rivo/tview"
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
		return
	}

	sessionId := resp.SessionId

	rgs, err := c.GetResourceGroups(context.Background(),
		&depi_grpc.GetResourceGroupsRequest{SessionId: sessionId})

	if err != nil {
		fmt.Printf("Can't fetch resource groups.\n")
		return
	}

	if !rgs.Ok {
		fmt.Printf("Can't fetch resource groups: %s\n", rgs.Msg)
		return
	}

	root := tview.NewTreeNode("depi")
	tree := tview.NewTreeView().
		SetRoot(root).
		SetCurrentNode(root)

	tools := map[string]*tview.TreeNode{}
	for _, rg := range rgs.ResourceGroups {
		node, found := tools[rg.ToolId]
		if !found {
			node = tview.NewTreeNode(rg.ToolId).SetReference(rg.ToolId).SetSelectable(true)
			tools[rg.ToolId] = node
			root.AddChild(node)
		}

		urlNode := tview.NewTreeNode(rg.URL).SetReference(rg.ToolId + "|" + rg.URL).SetSelectable(true)
		node.AddChild(urlNode)
	}

	app := tview.NewApplication().SetRoot(tree, true)

	tree.SetSelectedFunc(func(node *tview.TreeNode) {
		ref := node.GetReference()
		if ref == nil {
			return
		}
		reference := ref.(string)
		children := node.GetChildren()
		if len(children) == 0 {
			parts := strings.Split(reference, "|")
			if len(parts) > 1 {
				resp, err := c.GetResources(context.Background(),
					&depi_grpc.GetResourcesRequest{
						SessionId: sessionId,
						Patterns: []*depi_grpc.ResourceRefPattern{
							{
								ToolId:           parts[0],
								ResourceGroupURL: parts[1],
								URLPattern:       ".*",
							},
						},
						IncludeDeleted: false,
					})
				if err != nil {
					app.Stop()
					fmt.Printf("Error fetching resources: %+v\n", err)
					os.Exit(1)
				}
				if !resp.Ok {
					app.Stop()
					fmt.Printf("Error fetching resources: %s\n", resp.Msg)
					os.Exit(1)
				}
				for _, res := range resp.Resources {
					pathNode := tview.NewTreeNode(res.URL).SetReference(nil).SetSelectable(true)
					node.AddChild(pathNode)
				}
			}
		} else {
			node.SetExpanded(!node.IsExpanded())
		}
	})
	app.SetInputCapture(func(event *tcell.EventKey) *tcell.EventKey {
		switch event.Key() {
		case tcell.KeyRune:
			switch event.Rune() {
			case 'q', 'Q':
				app.Stop()
				os.Exit(0)
				return nil
			default:
				return event
			}
		default:
			return event
		}
	})
	if err := app.Run(); err != nil {
		panic(err)
	}
}
