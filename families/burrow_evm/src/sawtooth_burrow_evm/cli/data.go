/**
 * Copyright 2017 Intel Corporation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ------------------------------------------------------------------------------
 */

package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"path"
	"strings"
)

const (
	CONFIG_FILE = "config.json"
)

type Config struct {
	Url string
}

// -- Data Dir --

func getDataDir() string {
	return path.Join(os.Getenv("HOME"), ".seth")
}

func CreateDataDir() error {
	dataDir := getDataDir()
	if !pathExists(dataDir) {
		err := os.MkdirAll(dataDir, 0644)
		if err != nil {
			return err
		}
	}
	return nil
}

// -- Config --

func LoadConfig() (*Config, error) {
	configFilePath := path.Join(getDataDir(), CONFIG_FILE)

	if !pathExists(configFilePath) {
		return DefaultConfig(), nil
	}

	buf, err := ioutil.ReadFile(configFilePath)
	if err != nil {
		return nil, fmt.Errorf("Couldn't read config: %v", err)
	}

	config := &Config{}
	err = json.Unmarshal(buf, &config)
	if err != nil {
		return nil, fmt.Errorf("Couldn't parse config: %v", err)
	}

	return config, nil
}

func SaveConfig(config *Config) error {
	CreateDataDir()

	configFilePath := path.Join(getDataDir(), CONFIG_FILE)

	buf, err := json.Marshal(config)
	if err != nil {
		return fmt.Errorf("Couldn't marshal config: %v", err)
	}

	err = ioutil.WriteFile(configFilePath, buf, 0644)
	if err != nil {
		return fmt.Errorf("Couldn't save config: %v", err)
	}

	return nil
}

func DefaultConfig() *Config {
	return &Config{
		Url: "http://127.0.0.1:8080",
	}
}

// -- Alias --
func getKeyDir() string {
	return path.Join(getDataDir(), "keys")
}

func CreateKeyDir() error {
	keyDir := getKeyDir()
	if !pathExists(keyDir) {
		err := os.MkdirAll(keyDir, 0644)
		if err != nil {
			return err
		}
	}
	return nil
}

func SaveKey(alias, key string, overwrite bool) error {
	CreateKeyDir()

	keyFilePath := path.Join(getKeyDir(), alias+".priv")
	if pathExists(keyFilePath) {
		if !overwrite {
			return fmt.Errorf("Alias already in use")
		}
		fmt.Printf("Overwriting key with alias %v\n", alias)
	}

	err := ioutil.WriteFile(keyFilePath, []byte(key), 0600)
	if err != nil {
		return fmt.Errorf("Couldn't save key with alias %v: %v", alias, err)
	}

	return nil
}

func LoadKey(alias string) (string, error) {
	keyFilePath := path.Join(getKeyDir(), alias+".priv")
	if !pathExists(keyFilePath) {
		return "", fmt.Errorf("No key with alias %v", alias)
	}

	buf, err := ioutil.ReadFile(keyFilePath)
	if err != nil {
		return "", fmt.Errorf("Couldn't load key with alias %v: %v", alias, err)
	}

	return strings.TrimSpace(string(buf)), nil
}

// -- Utilities --
func pathExists(p string) bool {
	_, err := os.Stat(p)
	if os.IsNotExist(err) {
		return false
	}
	return true
}
