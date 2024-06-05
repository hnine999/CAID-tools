package main

import (
	"flag"
	"fmt"
	"go-impl/server"
	"log"
	"os"
)

func testHalt() {
	b := []byte{0}

	for {
		n, err := os.Stdin.Read(b)
		if err != nil {
			log.Printf("Test depi server halting because of error: %+v", err)
			os.Exit(0)
		}
		if n == 0 {
			log.Printf("Test depi server halting because of no characters read")
			os.Exit(0)
		}
	}
}

func main() {
	configFile := flag.String("config", "", "the name of the config file to use")
	configDefaultMem := flag.Bool("config-default-mem", false, "use the default in-memory config")
	configDefaultDolt := flag.Bool("config-default-dolt", false, "use the default dolt config")
	testMode := flag.Bool("test", false, "run the server in test mode for unit testing")

	flag.Parse()

	if !*testMode {

		configFilename := *configFile

		if configFilename == "" {
			if *configDefaultMem {
				configFilename = "configs/depi_config_mem.json"
			} else if *configDefaultDolt {
				configFilename = "configs/depi_config_dolt.json"
			}
		}

		server.LoadConfig(".", configFilename)
	} else {
		err := server.LoadConfigFromStdin()
		if err != nil {
			fmt.Printf("Error loading config from stdin: %+v\n", err)
		}
		go testHalt()

	}

	depiServer := server.NewServer()
	err := depiServer.Start()
	if err != nil {
		log.Printf("Error running server: %+v\n", err)
	}
}
