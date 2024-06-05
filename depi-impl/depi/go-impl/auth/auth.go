package auth

import (
	"errors"
	"fmt"
	"regexp"
)

type Capability struct {
	Name     string
	Patterns []string
	Regexes  []*regexp.Regexp
}

type Authorization struct {
	Capabilities map[string][]*Capability
}

func (cap *Capability) Verify(args []string) (bool, error) {
	if len(args) != len(cap.Patterns) {
		return false, errors.New(fmt.Sprintf("can't verify capability %s, %d arguments given for %d patterns",
			cap.Name, len(args), len(cap.Patterns)))
	}

	for i := range len(args) {
		if !cap.Regexes[i].MatchString(args[i]) {
			return false, nil
		}
	}
	return true, nil
}

func NewAuthorization() *Authorization {
	return &Authorization{}
}

func (auth *Authorization) HasCapability(capName string) bool {
	return true
}

func (auth *Authorization) IsAuthorized(capName string, args []string) bool {
	return true
}
