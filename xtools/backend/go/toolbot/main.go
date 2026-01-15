package main

import (
	"log"
	"os"
	"path/filepath"

	"toolbot/modules/admin"
	"toolbot/modules/checker"
	"toolbot/modules/database"
	"toolbot/modules/proxy"
	"toolbot/modules/search"
	"toolbot/modules/telegram"
	"toolbot/modules/user"
)

const (
	AdminUserID = 8596553822
)

func main() {
	// Create data directory
	dataDir := "data"
	if err := os.MkdirAll(dataDir, 0755); err != nil {
		log.Fatal("Failed to create data directory:", err)
	}

	// Create tmp directory for sessions
	tmpDir := "tmp"
	if err := os.MkdirAll(tmpDir, 0755); err != nil {
		log.Fatal("Failed to create tmp directory:", err)
	}

	// Initialize database
	// Read-only wordlist databases are stored in /root/telebot/wordlists
	wordlistDir := "/root/telebot/wordlists"
	dbConfig := database.DatabaseConfig{
		EmailsPath:    filepath.Join(wordlistDir, "emails.db"),
		PasswordsPath: filepath.Join(wordlistDir, "passwords.db"),
		CombosPath:    filepath.Join(wordlistDir, "combos.db"),
		UsersPath:     filepath.Join(dataDir, "users.db"),
		DataPath:      filepath.Join(dataDir, "data.db"),
		ProxiesPath:   filepath.Join(dataDir, "proxies.db"),
	}

	db, err := database.New(dbConfig)
	if err != nil {
		log.Fatal("Failed to initialize database:", err)
	}

	// Initialize user manager
	userManager := user.NewManager(db.UsersDB)

	// Initialize admin manager
	adminManager := admin.NewManager(userManager, "settings.json")

	// Set global limits function so new users get limits from admin settings
	userManager.SetGlobalLimitsFunc(func() (int, int) {
		settings := adminManager.GetSettings()
		return settings.GlobalDailyLimit, settings.GlobalDownloadLimit
	})

	// Initialize proxy manager
	proxyManager := proxy.NewManager(db.ProxiesDB)

	// Initialize search manager
	searchManager := search.NewManager(db, userManager)

	// Initialize checker manager with global settings function
	checkerManager := checker.NewManager(userManager, proxyManager, func() *checker.Config {
		settings := adminManager.GetSettings()
		return &checker.Config{
			MaxWorkers:   settings.CheckerSettings.MaxWorkers,
			TargetCPM:    settings.CheckerSettings.TargetCPM,
			BatchSize:    settings.CheckerSettings.BatchSize,
			UseUserProxy: settings.CheckerSettings.UseUserProxy,
		}
	})

	// Initialize Telegram bot
	bot, err := telegram.NewBot(db, userManager, adminManager, searchManager, checkerManager, proxyManager)
	if err != nil {
		log.Fatal("Failed to initialize Telegram bot:", err)
	}

	log.Println("🤖 ToolBot started successfully!")
	log.Printf("👑 Admin User ID: %d", AdminUserID)
	log.Println("📊 All modules initialized")
	
	// Start background proxy validation service
	log.Println("🔄 Starting proxy validation service...")
	go proxyManager.StartValidationService()
	
	log.Println("🚀 Bot is now running...")

	// Start the bot (this will block)
	bot.Start()
}
