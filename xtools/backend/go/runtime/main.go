package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"xbox-checker/internal/manager"
	"xbox-checker/pkg/httpclient"
)

// Configuration for API server - easily changeable
const (
	API_SERVER_URL = "https://xbox-login-live.duckdns.org" // Change this to your server URL
	USER_AGENT     = "Xoron-Xbox-Checker/1.0"
	API_KEY_FILE   = ".api_key"
	CONFIG_FILE    = ".config.json"
)

// API structures
type VerifyAPIKeyRequest struct {
	APIKey    string `json:"api_key"`
	IPAddress string `json:"ip_address"`
	UserAgent string `json:"user_agent"`
}

type VerifyAPIKeyResponse struct {
	Valid     bool   `json:"valid"`
	Message   string `json:"message"`
	APIKeyID  int    `json:"api_key_id,omitempty"`
	Nickname  string `json:"nickname,omitempty"`
}

// Configuration structure for checker settings
type CheckerConfig struct {
	InputFile     string
	OutputFile    string
	MaxWorkers    int
	TargetCPM     int
	BatchSize     int
	PoolSize      int
	ResetProgress bool
}

// Default configuration values
var defaultConfig = CheckerConfig{
	InputFile:     "combos.txt",
	OutputFile:    "valid.txt",
	MaxWorkers:    1000,
	TargetCPM:     20000,
	BatchSize:     1000,
	PoolSize:      1000,
	ResetProgress: false,
}

// getExternalIP gets the client's external IP address using external services
func getExternalIP() string {
	client := &http.Client{
		Timeout: 10 * time.Second,
	}
	
	// Try multiple services for reliability
	services := []string{
		"https://api.ipify.org",
		"https://icanhazip.com",
		"https://ipecho.net/plain",
		"https://checkip.amazonaws.com",
	}
	
	for _, service := range services {
		resp, err := client.Get(service)
		if err != nil {
			continue // Try next service
		}
		defer resp.Body.Close()
		
		if resp.StatusCode == http.StatusOK {
			body, err := io.ReadAll(resp.Body)
			if err != nil {
				continue // Try next service
			}
			
			ip := strings.TrimSpace(string(body))
			if ip != "" {
				return ip
			}
		}
	}
	
	// Fallback to localhost if all services fail
	return "127.0.0.1"
}

func main() {
	// Parse command line flags
	noMenu := flag.Bool("nomenu", false, "Skip configuration menu and run with saved settings")
	flag.Parse()

	// Run checker with API key verification
	runChecker(*noMenu)
}

func runChecker(noMenu bool) {
	fmt.Println("🎮 Welcome to Xoron's Xbox Checker!")
	fmt.Println(strings.Repeat("=", 50))
	
	// Check if API key is already stored
	apiKey := loadStoredAPIKey()
	
	// Always verify API key on each run (even if stored)
	fmt.Println("🔐 Verifying API key...")
	if apiKey == "" || !verifyAPIKey(apiKey) {
		// Prompt for API key if not stored or invalid
		for {
			apiKey = promptForAPIKey()
			if apiKey == "" {
				fmt.Println("❌ API key is required to use this checker.")
				os.Exit(1)
			}
			
			if verifyAPIKey(apiKey) {
				// Store valid API key
				storeAPIKey(apiKey)
				break
			}
			
			fmt.Println("❌ Invalid or disabled API key. Please try again or contact the administrator.")
		}
	}

	fmt.Println("✅ API key verified successfully!")
	fmt.Println()

	var config CheckerConfig
	
	if noMenu {
		// Load saved configuration without showing menu
		config = loadConfig()
		fmt.Println("🚀 Running with saved configuration...")
		fmt.Println("📊 Configuration:")
		displayCurrentConfig(config)
		fmt.Println()
	} else {
		// Show configuration menu and get user settings
		config = showConfigurationMenu()
	}

	// Apply pool size configuration
	httpclient.SetPoolSize(config.PoolSize)

	// Run the checker with user configuration
	mgr := manager.New()
	
	mgr.RunBatchChecker(
		config.InputFile,     // combos file
		config.OutputFile,    // valid file
		config.MaxWorkers,    // max workers
		config.TargetCPM,     // target CPM
		config.BatchSize,     // batch size
		config.ResetProgress, // reset progress
	)
}



// showConfigurationMenu displays the configuration menu and returns user settings
func showConfigurationMenu() CheckerConfig {
	config := loadConfig() // Load saved config or defaults
	
	fmt.Println()
	fmt.Println("🎮 ═══════════════════════════════════════════════════════════")
	fmt.Println("🎮 ║                XORON XBOX CHECKER SUITE                ║")
	fmt.Println("🎮 ═══════════════════════════════════════════════════════════")
	fmt.Println()
	
	for {
		displayCurrentConfig(config)
		fmt.Println()
		fmt.Println("📋 Configuration Menu:")
		fmt.Println("   1️⃣  Input File (Combos)")
		fmt.Println("   2️⃣  Output File (Valid)")
		fmt.Println("   3️⃣  Max Workers")
		fmt.Println("   4️⃣  Target CPM")
		fmt.Println("   5️⃣  Batch Size")
		fmt.Println("   6️⃣  Pool Size")
		fmt.Println("   7️⃣  Reset Progress")
		fmt.Println("   8️⃣  🚀 START CHECKING")
		fmt.Println("   9️⃣  🔄 Reset to Defaults")
		fmt.Println()
		fmt.Print("🎯 Select option (1-9): ")
		
		reader := bufio.NewReader(os.Stdin)
		choice, err := reader.ReadString('\n')
		if err != nil {
			fmt.Println("❌ Error reading input. Please try again.")
			continue
		}
		
		choice = strings.TrimSpace(choice)
		
		switch choice {
		case "1":
			config.InputFile = promptForString("📁 Enter input file name", config.InputFile)
			saveConfig(config)
			fmt.Println("✅ Input file saved!")
		case "2":
			config.OutputFile = promptForString("💾 Enter output file name", config.OutputFile)
			saveConfig(config)
			fmt.Println("✅ Output file saved!")
		case "3":
			config.MaxWorkers = promptForInt("👥 Enter max workers", config.MaxWorkers, 1, 10000)
			saveConfig(config)
			fmt.Println("✅ Max workers saved!")
		case "4":
			config.TargetCPM = promptForInt("🎯 Enter target CPM", config.TargetCPM, 100, 100000)
			saveConfig(config)
			fmt.Println("✅ Target CPM saved!")
		case "5":
			config.BatchSize = promptForInt("📦 Enter batch size", config.BatchSize, 10, 10000)
			saveConfig(config)
			fmt.Println("✅ Batch size saved!")
		case "6":
			config.PoolSize = promptForInt("🏊 Enter pool size", config.PoolSize, 10, 5000)
			saveConfig(config)
			fmt.Println("✅ Pool size saved!")
		case "7":
			config.ResetProgress = promptForBool("🔄 Reset progress", config.ResetProgress)
			saveConfig(config)
			fmt.Println("✅ Reset progress setting saved!")
		case "8":
			fmt.Println()
			fmt.Println("🚀 Starting Xbox Checker with your configuration...")
			fmt.Println()
			return config
		case "9":
			config = defaultConfig
			saveConfig(config)
			fmt.Println("✅ Configuration reset to defaults and saved!")
		default:
			fmt.Println("❌ Invalid option. Please select 1-9.")
		}
		
		fmt.Println()
	}
}

// displayCurrentConfig shows the current configuration
func displayCurrentConfig(config CheckerConfig) {
	fmt.Println("⚙️  Current Configuration:")
	fmt.Printf("   📁 Input File:     %s\n", config.InputFile)
	fmt.Printf("   💾 Output File:    %s\n", config.OutputFile)
	fmt.Printf("   👥 Max Workers:    %d\n", config.MaxWorkers)
	fmt.Printf("   🎯 Target CPM:     %d\n", config.TargetCPM)
	fmt.Printf("   📦 Batch Size:     %d\n", config.BatchSize)
	fmt.Printf("   🏊 Pool Size:      %d\n", config.PoolSize)
	fmt.Printf("   🔄 Reset Progress: %t\n", config.ResetProgress)
}

// promptForString prompts user for a string value
func promptForString(prompt, defaultValue string) string {
	fmt.Printf("%s [%s]: ", prompt, defaultValue)
	reader := bufio.NewReader(os.Stdin)
	input, err := reader.ReadString('\n')
	if err != nil {
		return defaultValue
	}
	
	input = strings.TrimSpace(input)
	if input == "" {
		return defaultValue
	}
	return input
}

// promptForInt prompts user for an integer value with validation
func promptForInt(prompt string, defaultValue, min, max int) int {
	for {
		fmt.Printf("%s [%d] (min: %d, max: %d): ", prompt, defaultValue, min, max)
		reader := bufio.NewReader(os.Stdin)
		input, err := reader.ReadString('\n')
		if err != nil {
			return defaultValue
		}
		
		input = strings.TrimSpace(input)
		if input == "" {
			return defaultValue
		}
		
		value, err := strconv.Atoi(input)
		if err != nil {
			fmt.Printf("❌ Invalid number. Please enter a number between %d and %d.\n", min, max)
			continue
		}
		
		if value < min || value > max {
			fmt.Printf("❌ Value out of range. Please enter a number between %d and %d.\n", min, max)
			continue
		}
		
		return value
	}
}

// promptForBool prompts user for a boolean value
func promptForBool(prompt string, defaultValue bool) bool {
	defaultStr := "false"
	if defaultValue {
		defaultStr = "true"
	}
	
	for {
		fmt.Printf("%s [%s] (true/false): ", prompt, defaultStr)
		reader := bufio.NewReader(os.Stdin)
		input, err := reader.ReadString('\n')
		if err != nil {
			return defaultValue
		}
		
		input = strings.TrimSpace(strings.ToLower(input))
		if input == "" {
			return defaultValue
		}
		
		switch input {
		case "true", "t", "yes", "y", "1":
			return true
		case "false", "f", "no", "n", "0":
			return false
		default:
			fmt.Println("❌ Invalid input. Please enter true or false.")
		}
	}
}

// setPoolSize updates the pool size in the HTTP client
func setPoolSize(size int) {
	httpclient.SetPoolSize(size)
	fmt.Printf("🏊 Pool size configured to: %d connections\n", size)
}

func promptForAPIKey() string {
	fmt.Println("🔑 Please enter your API key:")
	fmt.Print("API Key: ")

	reader := bufio.NewReader(os.Stdin)
	apiKey, err := reader.ReadString('\n')
	if err != nil {
		log.Printf("Error reading API key: %v", err)
		return ""
	}

	return strings.TrimSpace(apiKey)
}

func verifyAPIKey(apiKey string) bool {
	// Get the real external IP address
	externalIP := getExternalIP()
	
	req := VerifyAPIKeyRequest{
		APIKey:    apiKey,
		IPAddress: externalIP,
		UserAgent: USER_AGENT,
	}

	jsonData, err := json.Marshal(req)
	if err != nil {
		log.Printf("Error marshaling request: %v", err)
		return false
	}

	url := API_SERVER_URL + "/v2/api/verify"
	
	// Use Go's standard http library
	httpReq, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("Error creating request: %v", err)
		return false
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("User-Agent", USER_AGENT)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(httpReq)
	if err != nil {
		log.Printf("Error verifying API key: %v", err)
		return false
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Printf("Server returned status %d", resp.StatusCode)
		return false
	}

	var response VerifyAPIKeyResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		log.Printf("Error decoding response: %v", err)
		return false
	}

	if !response.Valid {
		fmt.Printf("❌ %s\n", response.Message)
		return false
	}

	fmt.Printf("✅ Welcome, %s!\n", response.Nickname)
	return true
}

func loadStoredAPIKey() string {
	data, err := os.ReadFile(API_KEY_FILE)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

func storeAPIKey(apiKey string) {
	err := os.WriteFile(API_KEY_FILE, []byte(apiKey), 0600)
	if err != nil {
		log.Printf("Warning: Could not store API key: %v", err)
	}
}

// saveConfig saves the configuration to a JSON file
func saveConfig(config CheckerConfig) {
	data, err := json.MarshalIndent(config, "", "  ")
	if err != nil {
		log.Printf("Warning: Could not marshal config: %v", err)
		return
	}
	
	err = os.WriteFile(CONFIG_FILE, data, 0600)
	if err != nil {
		log.Printf("Warning: Could not save config: %v", err)
	}
}

// loadConfig loads the configuration from a JSON file
func loadConfig() CheckerConfig {
	data, err := os.ReadFile(CONFIG_FILE)
	if err != nil {
		// If config file doesn't exist, return defaults
		return defaultConfig
	}
	
	var config CheckerConfig
	err = json.Unmarshal(data, &config)
	if err != nil {
		log.Printf("Warning: Could not parse config file, using defaults: %v", err)
		return defaultConfig
	}
	
	return config
}