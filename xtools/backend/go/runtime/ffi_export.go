package main

/*
#include <stdlib.h>
*/
import "C"
import (
	"encoding/json"
	"os"
	"unsafe"

	"xbox-checker/internal/manager"
	"xbox-checker/pkg/httpclient"
)

// FFIResult represents the result of an FFI call
type FFIResult struct {
	Success bool        `json:"success"`
	Error   string      `json:"error,omitempty"`
	Data    interface{} `json:"data,omitempty"`
}

// CheckerConfig represents the configuration for the Xbox checker
type FFICheckerConfig struct {
	APIKey        string `json:"api_key"`
	ComboFile     string `json:"combo_file"`
	OutputFile    string `json:"output_file"`
	MaxWorkers    int    `json:"max_workers"`
	TargetCPM     int    `json:"target_cpm"`
	BatchSize     int    `json:"batch_size"`
	PoolSize      int    `json:"pool_size"`
	ResetProgress bool   `json:"reset_progress"`
}

func makeResult(success bool, err string, data interface{}) *C.char {
	result := FFIResult{
		Success: success,
		Error:   err,
		Data:    data,
	}
	jsonBytes, _ := json.Marshal(result)
	return C.CString(string(jsonBytes))
}

//export CheckXboxAccount
func CheckXboxAccount(configJSON *C.char) *C.char {
	configStr := C.GoString(configJSON)

	var config FFICheckerConfig
	if err := json.Unmarshal([]byte(configStr), &config); err != nil {
		return makeResult(false, "Invalid configuration JSON: "+err.Error(), nil)
	}

	// Validate required fields
	if config.APIKey == "" {
		return makeResult(false, "API key is required", nil)
	}
	if config.ComboFile == "" {
		return makeResult(false, "Combo file is required", nil)
	}

	// Check if combo file exists
	if _, err := os.Stat(config.ComboFile); os.IsNotExist(err) {
		return makeResult(false, "Combo file not found: "+config.ComboFile, nil)
	}

	// Set defaults
	if config.OutputFile == "" {
		config.OutputFile = "valid.txt"
	}
	if config.MaxWorkers <= 0 {
		config.MaxWorkers = 1000
	}
	if config.TargetCPM <= 0 {
		config.TargetCPM = 20000
	}
	if config.BatchSize <= 0 {
		config.BatchSize = 1000
	}
	if config.PoolSize <= 0 {
		config.PoolSize = 1000
	}

	// Create data directories
	os.MkdirAll("data", 0755)
	os.MkdirAll("tmp", 0755)

	// Store API key
	if err := os.WriteFile(".api_key", []byte(config.APIKey), 0600); err != nil {
		return makeResult(false, "Failed to store API key: "+err.Error(), nil)
	}

	// Verify API key
	if !verifyAPIKey(config.APIKey) {
		return makeResult(false, "Invalid or disabled API key", nil)
	}

	// Configure pool size
	httpclient.SetPoolSize(config.PoolSize)

	// Run the checker
	mgr := manager.New()
	mgr.RunBatchChecker(
		config.ComboFile,
		config.OutputFile,
		config.MaxWorkers,
		config.TargetCPM,
		config.BatchSize,
		config.ResetProgress,
	)

	// Return success with stats
	return makeResult(true, "", map[string]interface{}{
		"combo_file":  config.ComboFile,
		"output_file": config.OutputFile,
		"message":     "Xbox checker completed",
	})
}

//export GetCheckerStatus
func GetCheckerStatus() *C.char {
	return makeResult(true, "", map[string]interface{}{
		"available": true,
		"version":   "1.0.0",
	})
}

//export FreeString
func FreeString(s *C.char) {
	C.free(unsafe.Pointer(s))
}

func main() {}
