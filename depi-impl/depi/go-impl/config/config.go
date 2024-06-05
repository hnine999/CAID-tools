package config

import (
	"bytes"
	"encoding/json"
	"io"
	"os"
)

type ToolConfig struct {
	PathSeparator string `json:"pathSeparator"`
}

type DBConfig struct {
	Type     string `json:"type"`
	StateDir string `json:"stateDir"`
	Host     string `json:"host"`
	Port     int    `json:"port"`
	User     string `json:"user"`
	Password string `json:"password"`
	Database string `json:"database"`
	PoolSize int    `json:"poolSize"`
}

type LoggingConfig struct {
	File  string `json:"file"`
	Level string `json:"level"`
}

type AuditConfig struct {
	Directory string `json:"directory"`
}

type ServerConfig struct {
	AuthorizationEnabled bool   `json:"authorization_enabled"`
	DefaultTimeout       int    `json:"default_timeout"`
	TokenTimeout         int    `json:"tokenTimeout"`
	InsecurePort         int    `json:"insecure_port"`
	SecurePort           int    `json:"secure_port"`
	KeyPEM               string `json:"key_pem"`
	CertPEM              string `json:"cert_pem"`
}

type AuthorizationConfig struct {
	AuthDefFile string `json:"auth_def_file"`
}

type UserConfig struct {
	Name      string   `json:"name"`
	Password  string   `json:"password"`
	AuthRules []string `json:"auth_rules"`
}

type Config struct {
	ToolConfig          map[string]ToolConfig `json:"tools"`
	DBConfig            DBConfig              `json:"db"`
	LoggingConfig       LoggingConfig         `jsong:"logging"`
	AuditConfig         AuditConfig           `json:"audit"`
	ServerConfig        ServerConfig          `json:"server"`
	AuthorizationConfig AuthorizationConfig   `json:"authorization"`
	UserConfig          []UserConfig          `json:"users"`
}

var GlobalConfig *Config = &Config{}

func LoadConfig(filename string) error {
	configFile, err := os.Open(filename)
	if err != nil {
		return err
	}
	defer configFile.Close()

	dec := json.NewDecoder(configFile)
	return dec.Decode(GlobalConfig)
}

func LoadConfigFromStream(inStream io.Reader) error {
	buffer := bytes.NewBuffer(make([]byte, 0))
	ch := []byte{0}
	for {
		n, err := inStream.Read(ch)
		if err != nil {
			return err
		}
		if n == 0 {
			break
		}
		if ch[0] == 0 {
			break
		}
		buffer.Write(ch)
	}
	dec := json.NewDecoder(buffer)
	return dec.Decode(GlobalConfig)
}

func StringOrDefault(value string, def string) string {
	if value != "" {
		return value
	} else {
		return def
	}
}

func IntOrDefault(value int, def int) int {
	if value == 0 {
		return def
	} else {
		return value
	}
}
