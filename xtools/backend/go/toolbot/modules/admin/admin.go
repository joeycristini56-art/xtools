package admin

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"strconv"
	"strings"
	"time"

	tgbotapi "github.com/go-telegram-bot-api/telegram-bot-api/v5"
	"toolbot/modules/user"
)

const (
	AdminUserID = 8596553822 // Your Telegram user ID
)

type Settings struct {
	PublicMode          bool            `json:"public_mode"`
	GlobalDailyLimit    int             `json:"global_daily_limit"`
	GlobalDownloadLimit int             `json:"global_download_limit"`
	GlobalProxyLimit    int             `json:"global_proxy_limit"`
	RequireAPIKey       bool            `json:"require_api_key"`
	MaintenanceMode     bool            `json:"maintenance_mode"`
	CheckerSettings     CheckerSettings `json:"checker_settings"`
	DatabaseStats       DatabaseStats   `json:"database_stats"`
}

type DatabaseStats struct {
	TotalEmails    int64  `json:"total_emails"`
	TotalCombos    int64  `json:"total_combos"`
	TotalPasswords int64  `json:"total_passwords"`
	LastUpdated    string `json:"last_updated"`
}

type CheckerSettings struct {
	MaxWorkers   int  `json:"max_workers"`
	TargetCPM    int  `json:"target_cpm"`
	BatchSize    int  `json:"batch_size"`
	UseUserProxy bool `json:"use_user_proxy"`
}

type Manager struct {
	userManager  *user.Manager
	settings     *Settings
	settingsFile string
}

func NewManager(userManager *user.Manager, settingsFile string) *Manager {
	manager := &Manager{
		userManager:  userManager,
		settingsFile: settingsFile,
		settings: &Settings{
			PublicMode:          false,
			GlobalDailyLimit:    50000,
			GlobalDownloadLimit: 10000,
			GlobalProxyLimit:    5,
			RequireAPIKey:       true,
			MaintenanceMode:     false,
			CheckerSettings: CheckerSettings{
				MaxWorkers:   100,
				TargetCPM:    1000,
				BatchSize:    50,
				UseUserProxy: true,
			},
		},
	}

	manager.loadSettings()
	return manager
}

func (m *Manager) IsAdmin(userID int64) bool {
	return userID == AdminUserID
}

func (m *Manager) GetSettings() *Settings {
	return m.settings
}

func (m *Manager) UpdateDatabaseStats(emails, combos, passwords int64) {
	m.settings.DatabaseStats.TotalEmails = emails
	m.settings.DatabaseStats.TotalCombos = combos
	m.settings.DatabaseStats.TotalPasswords = passwords
	m.settings.DatabaseStats.LastUpdated = time.Now().Format("2006-01-02 15:04:05")
	m.SaveSettings()
}

func (m *Manager) GetDatabaseStats() DatabaseStats {
	return m.settings.DatabaseStats
}

func (m *Manager) SaveSettings() error {
	data, err := json.MarshalIndent(m.settings, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(m.settingsFile, data, 0600)
}

func (m *Manager) loadSettings() error {
	data, err := os.ReadFile(m.settingsFile)
	if err != nil {
		// File doesn't exist, use defaults
		return m.SaveSettings()
	}

	return json.Unmarshal(data, m.settings)
}

func (m *Manager) HandleAdminCommand(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	if !m.IsAdmin(update.Message.From.ID) {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Access denied. Admin only.")
		bot.Send(msg)
		return
	}

	command := strings.ToLower(strings.TrimSpace(update.Message.Text))

	switch {
	case command == "/admin":
		m.showAdminMenu(bot, update.Message.Chat.ID)
	case strings.HasPrefix(command, "/setuserapi"):
		m.handleSetUserAPI(bot, update)
	case strings.HasPrefix(command, "/banuser"):
		m.handleBanUser(bot, update)
	case strings.HasPrefix(command, "/unbanuser"):
		m.handleUnbanUser(bot, update)
	case strings.HasPrefix(command, "/setuserlimit"):
		m.handleSetUserLimit(bot, update)
	case strings.HasPrefix(command, "/setgloballimit"):
		m.handleSetGlobalLimit(bot, update)
	case command == "/togglepublic":
		m.handleTogglePublic(bot, update)
	case command == "/toggleapi":
		m.handleToggleAPI(bot, update)
	case command == "/togglemaintenance":
		m.handleToggleMaintenance(bot, update)
	case command == "/stats":
		m.showStats(bot, update.Message.Chat.ID)
	case command == "/users":
		m.showUsers(bot, update.Message.Chat.ID)
	default:
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Unknown admin command.")
		bot.Send(msg)
	}
}

func (m *Manager) getAdminMenuContent() (string, tgbotapi.InlineKeyboardMarkup) {
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📊 Statistics", "admin_stats"),
			tgbotapi.NewInlineKeyboardButtonData("👥 Users", "admin_users"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⚙️ Settings", "admin_settings"),
			tgbotapi.NewInlineKeyboardButtonData("🔧 Maintenance", "admin_maintenance"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🎯 Checker Settings", "admin_checker"),
			tgbotapi.NewInlineKeyboardButtonData("🔑 Bot Keys", "admin_api_keys"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "admin_menu"),
		),
	)

	text := fmt.Sprintf(`🔧 **Admin Panel**

**Current Settings:**
🌐 Public Mode: %s
🔑 Require Bot Key: %s
🚧 Maintenance Mode: %s
📊 Global Daily Limit: %d

**Quick Commands:**
/stats - View statistics
/users - View all users
/togglepublic - Toggle public mode
/toggleapi - Toggle API requirement
/togglemaintenance - Toggle maintenance mode

**User Management:**
/banuser \<user\_id\> - Ban a user
/unbanuser \<user\_id\> - Unban a user
/setuserlimit \<user\_id\> \<limit\> - Set user limit
/setgloballimit \<limit\> - Set global limit
/setuserapi \<user\_id\> \<api\_key\> - Set user Bot Key`,
		boolToEmoji(m.settings.PublicMode),
		boolToEmoji(m.settings.RequireAPIKey),
		boolToEmoji(m.settings.MaintenanceMode),
		m.settings.GlobalDailyLimit)

	return text, keyboard
}

func (m *Manager) showAdminMenu(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getAdminMenuContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editAdminMenu(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getAdminMenuContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) HandleAdminCallback(bot *tgbotapi.BotAPI, callback *tgbotapi.CallbackQuery) {
	if !m.IsAdmin(callback.From.ID) {
		return
	}

	chatID := callback.Message.Chat.ID
	messageID := callback.Message.MessageID
	userID := callback.From.ID

	switch callback.Data {
	case "admin_menu":
		m.editAdminMenu(bot, chatID, messageID)
	case "admin_stats":
		m.editStats(bot, chatID, messageID)
	case "admin_users":
		m.editUsers(bot, chatID, messageID)
	case "admin_settings":
		m.editSettings(bot, chatID, messageID)
	case "admin_maintenance":
		m.editMaintenance(bot, chatID, messageID)
	case "toggle_public":
		m.settings.PublicMode = !m.settings.PublicMode
		m.SaveSettings()
		m.editSettings(bot, chatID, messageID)
	case "toggle_api":
		m.settings.RequireAPIKey = !m.settings.RequireAPIKey
		m.SaveSettings()
		m.editSettings(bot, chatID, messageID)
	case "toggle_maintenance":
		m.settings.MaintenanceMode = !m.settings.MaintenanceMode
		m.SaveSettings()
		m.editMaintenance(bot, chatID, messageID)
	case "admin_checker":
		m.editCheckerSettings(bot, chatID, messageID)
	case "admin_api_keys":
		m.editAPIKeys(bot, chatID, messageID)
	case "admin_generate_key":
		m.handleGenerateKeyEdit(bot, chatID, messageID)
	case "admin_disable_user":
		m.handleDisableUserEdit(bot, chatID, messageID)
	case "admin_enable_user":
		m.handleEnableUserEdit(bot, chatID, messageID)
	case "config_workers":
		m.editConfigWorkers(bot, chatID, messageID)
	case "config_cpm":
		m.editConfigCPM(bot, chatID, messageID)
	case "config_batch":
		m.editConfigBatch(bot, chatID, messageID)
	case "config_proxies":
		m.editConfigProxies(bot, chatID, messageID)
	case "config_global_limits":
		m.editGlobalLimits(bot, chatID, messageID)
	case "config_search_limit":
		m.editConfigSearchLimit(bot, chatID, messageID)
	case "config_download_limit":
		m.editConfigDownloadLimit(bot, chatID, messageID)
	case "config_proxy_limit":
		m.editConfigProxyLimit(bot, chatID, messageID)
	case "custom_workers":
		m.promptCustomWorkers(bot, chatID, messageID, userID)
	case "custom_cpm":
		m.promptCustomCPM(bot, chatID, messageID, userID)
	case "custom_batch":
		m.promptCustomBatch(bot, chatID, messageID, userID)
	case "custom_search_limit":
		m.promptCustomSearchLimit(bot, chatID, messageID, userID)
	case "custom_download_limit":
		m.promptCustomDownloadLimit(bot, chatID, messageID, userID)
	case "custom_proxy_limit":
		m.promptCustomProxyLimit(bot, chatID, messageID, userID)
	default:
		// Handle setting value callbacks
		if strings.HasPrefix(callback.Data, "set_workers_") {
			valueStr := strings.TrimPrefix(callback.Data, "set_workers_")
			if value, err := strconv.Atoi(valueStr); err == nil {
				m.settings.CheckerSettings.MaxWorkers = value
				m.SaveSettings()
				m.editCheckerSettings(bot, chatID, messageID)
			}
		} else if strings.HasPrefix(callback.Data, "set_cpm_") {
			valueStr := strings.TrimPrefix(callback.Data, "set_cpm_")
			if value, err := strconv.Atoi(valueStr); err == nil {
				m.settings.CheckerSettings.TargetCPM = value
				m.SaveSettings()
				m.editCheckerSettings(bot, chatID, messageID)
			}
		} else if strings.HasPrefix(callback.Data, "set_batch_") {
			valueStr := strings.TrimPrefix(callback.Data, "set_batch_")
			if value, err := strconv.Atoi(valueStr); err == nil {
				m.settings.CheckerSettings.BatchSize = value
				m.SaveSettings()
				m.editCheckerSettings(bot, chatID, messageID)
			}
		} else if strings.HasPrefix(callback.Data, "set_global_search_") {
			valueStr := strings.TrimPrefix(callback.Data, "set_global_search_")
			if value, err := strconv.Atoi(valueStr); err == nil {
				m.settings.GlobalDailyLimit = value
				m.SaveSettings()
				m.editGlobalLimits(bot, chatID, messageID)
			}
		} else if strings.HasPrefix(callback.Data, "set_global_download_") {
			valueStr := strings.TrimPrefix(callback.Data, "set_global_download_")
			if value, err := strconv.Atoi(valueStr); err == nil {
				m.settings.GlobalDownloadLimit = value
				m.SaveSettings()
				m.editGlobalLimits(bot, chatID, messageID)
			}
		} else if strings.HasPrefix(callback.Data, "set_global_proxy_") {
			valueStr := strings.TrimPrefix(callback.Data, "set_global_proxy_")
			if value, err := strconv.Atoi(valueStr); err == nil {
				m.settings.GlobalProxyLimit = value
				m.SaveSettings()
				m.editGlobalLimits(bot, chatID, messageID)
			}
		} else if strings.HasPrefix(callback.Data, "user_limits_") {
			// Handle user limits menu
			targetUserIDStr := strings.TrimPrefix(callback.Data, "user_limits_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.editUserLimits(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "set_user_search_limit_") {
			// Format: set_user_search_limit_USERID_VALUE
			parts := strings.Split(strings.TrimPrefix(callback.Data, "set_user_search_limit_"), "_")
			if len(parts) >= 2 {
				if targetUserID, err := strconv.ParseInt(parts[0], 10, 64); err == nil {
					if value, err := strconv.Atoi(parts[1]); err == nil {
						m.userManager.SetUserLimit(targetUserID, value)
						m.editUserLimits(bot, chatID, messageID, targetUserID)
					}
				}
			}
		} else if strings.HasPrefix(callback.Data, "set_user_download_limit_") {
			// Format: set_user_download_limit_USERID_VALUE
			parts := strings.Split(strings.TrimPrefix(callback.Data, "set_user_download_limit_"), "_")
			if len(parts) >= 2 {
				if targetUserID, err := strconv.ParseInt(parts[0], 10, 64); err == nil {
					if value, err := strconv.Atoi(parts[1]); err == nil {
						m.userManager.SetUserDownloadLimit(targetUserID, value)
						m.editUserLimits(bot, chatID, messageID, targetUserID)
					}
				}
			}
		} else if strings.HasPrefix(callback.Data, "config_user_search_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "config_user_search_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.editConfigUserSearchLimit(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "config_user_download_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "config_user_download_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.editConfigUserDownloadLimit(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "custom_user_search_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "custom_user_search_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.promptCustomUserSearchLimit(bot, chatID, messageID, userID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "custom_user_download_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "custom_user_download_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.promptCustomUserDownloadLimit(bot, chatID, messageID, userID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "user_") {
			// Handle user-specific callbacks (user_123)
			targetUserIDStr := strings.TrimPrefix(callback.Data, "user_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.editUserDetails(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "ban_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "ban_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.userManager.BanUser(targetUserID)
				m.editUserDetails(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "unban_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "unban_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.userManager.UnbanUser(targetUserID)
				m.editUserDetails(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "remove_api_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "remove_api_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.userManager.SetAPIKey(targetUserID, "")
				m.editUserDetails(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "give_api_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "give_api_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				apiKey := m.generateAPIKey()
				m.userManager.SetAPIKey(targetUserID, apiKey)
				m.editUserDetails(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "reset_usage_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "reset_usage_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.userManager.ResetUserUsage(targetUserID)
				m.editUserDetails(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "api_key_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "api_key_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.editAPIKeyDetails(bot, chatID, messageID, targetUserID)
			}
		} else if callback.Data == "view_all_keys" {
			m.editAllAPIKeys(bot, chatID, messageID)
		} else if strings.HasPrefix(callback.Data, "regen_api_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "regen_api_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				apiKey := m.generateAPIKey()
				m.userManager.SetAPIKey(targetUserID, apiKey)
				m.editAPIKeyDetails(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "delete_api_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "delete_api_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.userManager.SetAPIKey(targetUserID, "")
				m.editAPIKeys(bot, chatID, messageID)
			}
		} else if strings.HasPrefix(callback.Data, "enable_api_user_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "enable_api_user_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.userManager.UnbanUser(targetUserID)
				m.editAPIKeyDetails(bot, chatID, messageID, targetUserID)
			}
		} else if strings.HasPrefix(callback.Data, "disable_api_user_") {
			targetUserIDStr := strings.TrimPrefix(callback.Data, "disable_api_user_")
			if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
				m.userManager.BanUser(targetUserID)
				m.editAPIKeyDetails(bot, chatID, messageID, targetUserID)
			}
		}
	}

	// Answer callback to remove loading state
	bot.Request(tgbotapi.NewCallback(callback.ID, ""))
}

// editMessage is a helper to edit an existing message with new text and keyboard
func (m *Manager) editMessage(bot *tgbotapi.BotAPI, chatID int64, messageID int, text string, keyboard *tgbotapi.InlineKeyboardMarkup) {
	editMsg := tgbotapi.NewEditMessageText(chatID, messageID, text)
	editMsg.ParseMode = "Markdown"
	if keyboard != nil {
		editMsg.ReplyMarkup = keyboard
	}
	bot.Send(editMsg)
}

func (m *Manager) getStatsContent() (string, tgbotapi.InlineKeyboardMarkup, error) {
	stats, err := m.userManager.GetUserStats()
	
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "admin_stats"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_menu"),
		),
	)
	
	if err != nil {
		return "❌ Error getting statistics: " + err.Error(), keyboard, err
	}

	text := fmt.Sprintf(`📊 **Bot Statistics**

👥 **Users:**
• Total Users: %d
• Active Today: %d
• Banned Users: %d

📈 **Activity Today:**
• Searches: %d
• Downloads: %d

⚙️ **Settings:**
• Public Mode: %s
• API Required: %s
• Maintenance: %s
• Global Limit: %d`,
		stats["total_users"],
		stats["active_today"],
		stats["banned_users"],
		stats["searches_today"],
		stats["downloads_today"],
		boolToEmoji(m.settings.PublicMode),
		boolToEmoji(m.settings.RequireAPIKey),
		boolToEmoji(m.settings.MaintenanceMode),
		m.settings.GlobalDailyLimit)

	return text, keyboard, nil
}

func (m *Manager) showStats(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard, _ := m.getStatsContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editStats(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard, _ := m.getStatsContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getUsersContent() (string, tgbotapi.InlineKeyboardMarkup, error) {
	users, err := m.userManager.GetAllUsers()
	
	// Default keyboard with back button
	defaultKeyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "admin_users"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_menu"),
		),
	)
	
	if err != nil {
		return "❌ Error getting users: " + err.Error(), defaultKeyboard, err
	}

	if len(users) == 0 {
		return "👥 No users found.", defaultKeyboard, nil
	}

	text := fmt.Sprintf("👥 All Users (%d total):\n\n", len(users))
	
	// Create keyboard with user buttons
	var keyboard [][]tgbotapi.InlineKeyboardButton
	
	// Show first 10 users as clickable buttons
	for i, user := range users {
		if i >= 10 { // Limit to first 10 users to avoid keyboard size issues
			text += fmt.Sprintf("... and %d more users (use refresh to see different users)\n", len(users)-10)
			break
		}

		status := "✅"
		if user.IsBanned {
			status = "🚫"
		}

		name := user.Username
		if name == "" {
			if user.FirstName != "" {
				name = user.FirstName
			} else {
				name = fmt.Sprintf("User_%d", user.UserID)
			}
		}

		apiStatus := "❌"
		if user.APIKey != "" {
			apiStatus = "✅"
		}

		text += fmt.Sprintf(`%s **%s** (ID: %d)
Searches: %d/%d | Downloads: %d | API: %s

`, status, name, user.UserID, user.DailySearchCount, user.DailyLimit, user.DailyDownloadCount, apiStatus)

		// Add user button to keyboard
		buttonText := fmt.Sprintf("%s %s", status, name)
		if len(buttonText) > 30 {
			buttonText = buttonText[:27] + "..."
		}
		
		userButton := tgbotapi.NewInlineKeyboardButtonData(buttonText, fmt.Sprintf("user_%d", user.UserID))
		
		// Add buttons in rows of 2
		if i%2 == 0 {
			keyboard = append(keyboard, []tgbotapi.InlineKeyboardButton{userButton})
		} else {
			keyboard[len(keyboard)-1] = append(keyboard[len(keyboard)-1], userButton)
		}
	}

	// Add control buttons
	keyboard = append(keyboard, 
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "admin_users"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_menu"),
		),
	)

	return text, tgbotapi.NewInlineKeyboardMarkup(keyboard...), nil
}

func (m *Manager) showUsers(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard, _ := m.getUsersContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editUsers(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard, _ := m.getUsersContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getSettingsContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := fmt.Sprintf(`⚙️ **Bot Settings**

🌐 **Public Mode:** %s
%s

🔑 **Require Bot Key:** %s
%s

📊 **Global Limits:**
• Search Limit: %d/day
• Download Limit: %d/day`,
		boolToEmoji(m.settings.PublicMode),
		func() string {
			if m.settings.PublicMode {
				return "Everyone can use the bot without Bot Key"
			}
			return "Only users with Bot Keys can use the bot"
		}(),
		boolToEmoji(m.settings.RequireAPIKey),
		func() string {
			if m.settings.RequireAPIKey {
				return "Users need Bot Keys to access features"
			}
			return "Users can access features without Bot Keys"
		}(),
		m.settings.GlobalDailyLimit,
		m.settings.GlobalDownloadLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🌐 Toggle Public", "toggle_public"),
			tgbotapi.NewInlineKeyboardButtonData("🔑 Toggle API", "toggle_api"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📊 Global Limits", "config_global_limits"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_menu"),
		),
	)

	return text, keyboard
}

func (m *Manager) showSettings(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getSettingsContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editSettings(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getSettingsContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getMaintenanceContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := fmt.Sprintf(`🔧 **Maintenance Mode**

**Status:** %s

%s`,
		boolToEmoji(m.settings.MaintenanceMode),
		func() string {
			if m.settings.MaintenanceMode {
				return "🚧 Bot is in maintenance mode. Only admins can use it."
			}
			return "✅ Bot is operational and available to users."
		}())

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔧 Toggle Maintenance", "toggle_maintenance"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_menu"),
		),
	)

	return text, keyboard
}

func (m *Manager) showMaintenance(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getMaintenanceContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editMaintenance(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getMaintenanceContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) handleTogglePublic(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	m.settings.PublicMode = !m.settings.PublicMode
	m.SaveSettings()

	status := "disabled"
	if m.settings.PublicMode {
		status = "enabled"
	}

	msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("✅ Public mode %s.", status))
	bot.Send(msg)
}

func (m *Manager) handleToggleAPI(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	m.settings.RequireAPIKey = !m.settings.RequireAPIKey
	m.SaveSettings()

	status := "disabled"
	if m.settings.RequireAPIKey {
		status = "enabled"
	}

	msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("✅ Bot Key requirement %s.", status))
	bot.Send(msg)
}

func (m *Manager) handleToggleMaintenance(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	m.settings.MaintenanceMode = !m.settings.MaintenanceMode
	m.SaveSettings()

	status := "disabled"
	if m.settings.MaintenanceMode {
		status = "enabled"
	}

	msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("✅ Maintenance mode %s.", status))
	bot.Send(msg)
}

func (m *Manager) handleBanUser(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	parts := strings.Fields(update.Message.Text)
	if len(parts) < 2 {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Usage: /banuser <user_id>")
		bot.Send(msg)
		return
	}

	userID, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Invalid user ID.")
		bot.Send(msg)
		return
	}

	if err := m.userManager.BanUser(userID); err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Error banning user: "+err.Error())
		bot.Send(msg)
		return
	}

	msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("✅ User %d has been banned.", userID))
	bot.Send(msg)
}

func (m *Manager) handleUnbanUser(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	parts := strings.Fields(update.Message.Text)
	if len(parts) < 2 {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Usage: /unbanuser <user_id>")
		bot.Send(msg)
		return
	}

	userID, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Invalid user ID.")
		bot.Send(msg)
		return
	}

	if err := m.userManager.UnbanUser(userID); err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Error unbanning user: "+err.Error())
		bot.Send(msg)
		return
	}

	msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("✅ User %d has been unbanned.", userID))
	bot.Send(msg)
}

func (m *Manager) handleSetUserLimit(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	parts := strings.Fields(update.Message.Text)
	if len(parts) < 3 {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Usage: /setuserlimit <user_id> <limit>")
		bot.Send(msg)
		return
	}

	userID, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Invalid user ID.")
		bot.Send(msg)
		return
	}

	limit, err := strconv.Atoi(parts[2])
	if err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Invalid limit.")
		bot.Send(msg)
		return
	}

	if err := m.userManager.SetUserLimit(userID, limit); err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Error setting user limit: "+err.Error())
		bot.Send(msg)
		return
	}

	msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("✅ User %d limit set to %d.", userID, limit))
	bot.Send(msg)
}

func (m *Manager) handleSetGlobalLimit(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	parts := strings.Fields(update.Message.Text)
	if len(parts) < 2 {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Usage: /setgloballimit <limit>")
		bot.Send(msg)
		return
	}

	limit, err := strconv.Atoi(parts[1])
	if err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Invalid limit.")
		bot.Send(msg)
		return
	}

	m.settings.GlobalDailyLimit = limit
	m.SaveSettings()

	msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("✅ Global daily limit set to %d.", limit))
	bot.Send(msg)
}

func (m *Manager) handleSetUserAPI(bot *tgbotapi.BotAPI, update tgbotapi.Update) {
	parts := strings.Fields(update.Message.Text)
	if len(parts) < 3 {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Usage: /setuserapi <user_id> <api_key>")
		bot.Send(msg)
		return
	}

	userID, err := strconv.ParseInt(parts[1], 10, 64)
	if err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Invalid user ID.")
		bot.Send(msg)
		return
	}

	apiKey := parts[2]

	if err := m.userManager.SetAPIKey(userID, apiKey); err != nil {
		msg := tgbotapi.NewMessage(update.Message.Chat.ID, "❌ Error setting Bot Key: "+err.Error())
		bot.Send(msg)
		return
	}

	msg := tgbotapi.NewMessage(update.Message.Chat.ID, fmt.Sprintf("✅ Bot Key set for user %d.", userID))
	bot.Send(msg)
}

func (m *Manager) getCheckerSettingsContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := fmt.Sprintf(`🎯 **Checker Settings**

⚙️ **Current Settings:**
• Max Workers: %d
• Target CPM: %d
• Batch Size: %d
• Use Your Proxies: %s

📝 **Configure Settings:**
Use the buttons below to modify global checker settings for all users.`,
		m.settings.CheckerSettings.MaxWorkers,
		m.settings.CheckerSettings.TargetCPM,
		m.settings.CheckerSettings.BatchSize,
		boolToEmoji(m.settings.CheckerSettings.UseUserProxy))

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("👥 Max Workers", "config_workers"),
			tgbotapi.NewInlineKeyboardButtonData("⚡ Target CPM", "config_cpm"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📦 Batch Size", "config_batch"),
			tgbotapi.NewInlineKeyboardButtonData("🔄 Toggle Proxies", "config_proxies"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "admin_checker"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_menu"),
		),
	)

	return text, keyboard
}

func (m *Manager) showCheckerSettings(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getCheckerSettingsContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editCheckerSettings(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getCheckerSettingsContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getAPIKeysContent() (string, tgbotapi.InlineKeyboardMarkup, error) {
	users, err := m.userManager.GetAllUsers()
	
	defaultKeyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("➕ Generate Key", "admin_generate_key"),
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "admin_api_keys"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_menu"),
		),
	)
	
	if err != nil {
		return "❌ Error getting users: " + err.Error(), defaultKeyboard, err
	}

	text := "🔑 **Bot Key Management**\n\n"
	
	// Count users with Bot Keys
	usersWithKeys := 0
	for _, user := range users {
		if user.APIKey != "" {
			usersWithKeys++
		}
	}

	text += fmt.Sprintf("**Summary:**\n• Total Users: %d\n• Users with Bot Keys: %d\n\n", len(users), usersWithKeys)

	// Create keyboard with Bot Key buttons
	var keyboard [][]tgbotapi.InlineKeyboardButton

	text += "**Users with Bot Keys:**\n"
	if usersWithKeys == 0 {
		text += "No users have Bot Keys yet.\n"
	} else {
		count := 0
		for _, user := range users {
			if user.APIKey != "" && count < 8 { // Limit to first 8 to avoid keyboard size issues
				name := user.Username
				if name == "" {
					name = fmt.Sprintf("User_%d", user.UserID)
				}
				
				// Show user info in text
				text += fmt.Sprintf("• **%s** (ID: %d)\n  🔑 Key: %s\n", name, user.UserID, user.APIKey[:8]+"...")
				
				// Add clickable button for this Bot Key
				buttonText := fmt.Sprintf("🔑 %s", name)
				if len(buttonText) > 25 {
					buttonText = buttonText[:22] + "..."
				}
				
				apiButton := tgbotapi.NewInlineKeyboardButtonData(buttonText, fmt.Sprintf("api_key_%d", user.UserID))
				
				// Add buttons in rows of 2
				if count%2 == 0 {
					keyboard = append(keyboard, []tgbotapi.InlineKeyboardButton{apiButton})
				} else {
					keyboard[len(keyboard)-1] = append(keyboard[len(keyboard)-1], apiButton)
				}
				count++
			}
		}
		if usersWithKeys > 8 {
			text += fmt.Sprintf("... and %d more users\n", usersWithKeys-8)
		}
	}

	text += "\n**Management Options:**\n"
	text += "• Click on user buttons above to manage their Bot Keys\n"
	text += "• Generate new keys for users\n"

	// Add management buttons
	keyboard = append(keyboard, 
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("➕ Generate Key", "admin_generate_key"),
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "admin_api_keys"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("📋 View All Keys", "view_all_keys"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_menu"),
		),
	)

	return text, tgbotapi.NewInlineKeyboardMarkup(keyboard...), nil
}

func (m *Manager) showAPIKeys(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard, _ := m.getAPIKeysContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editAPIKeys(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard, _ := m.getAPIKeysContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getGenerateKeyContent() (string, tgbotapi.InlineKeyboardMarkup) {
	// Generate a random Bot Key
	apiKey := m.generateAPIKey()
	
	text := fmt.Sprintf(`🔑 **New Bot Key Generated**

**Bot Key:** %s

This key is ready to be distributed to users. Users can redeem it using the "Redeem Bot Key" button when they start the bot.

**Note:** Keep this key secure and only share it with authorized users.`, apiKey)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back to Bot Keys", "admin_api_keys"),
		),
	)

	return text, keyboard
}

func (m *Manager) handleGenerateKey(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getGenerateKeyContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) handleGenerateKeyEdit(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getGenerateKeyContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getDisableUserContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `🚫 **Disable User**

To disable a user, send me their User ID.

Example: 123456789

This will ban the user from using the bot.`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back to Bot Keys", "admin_api_keys"),
		),
	)

	return text, keyboard
}

func (m *Manager) handleDisableUser(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getDisableUserContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) handleDisableUserEdit(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getDisableUserContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getEnableUserContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `✅ **Enable User**

To enable a user, send me their User ID.

Example: 123456789

This will unban the user and restore their access to the bot.`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back to Bot Keys", "admin_api_keys"),
		),
	)

	return text, keyboard
}

func (m *Manager) handleEnableUser(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getEnableUserContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) handleEnableUserEdit(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getEnableUserContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) generateAPIKey() string {
	// Generate a random 32-character Bot Key
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	key := make([]byte, 32)
	for i := range key {
		key[i] = charset[rand.Intn(len(charset))]
	}
	return string(key)
}

func boolToEmoji(b bool) string {
	if b {
		return "✅"
	}
	return "❌"
}

// Checker Settings Configuration Handlers
func (m *Manager) getConfigWorkersContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `👥 **Configure Max Workers**

Current: ` + fmt.Sprintf("%d", m.settings.CheckerSettings.MaxWorkers) + `

Select new value or enter custom:`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("50", "set_workers_50"),
			tgbotapi.NewInlineKeyboardButtonData("100", "set_workers_100"),
			tgbotapi.NewInlineKeyboardButtonData("200", "set_workers_200"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("500", "set_workers_500"),
			tgbotapi.NewInlineKeyboardButtonData("1000", "set_workers_1000"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✏️ Custom", "custom_workers"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_checker"),
		),
	)

	return text, keyboard
}

func (m *Manager) handleConfigWorkers(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getConfigWorkersContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editConfigWorkers(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getConfigWorkersContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getConfigCPMContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `⚡ **Configure Target CPM**

Current: ` + fmt.Sprintf("%d", m.settings.CheckerSettings.TargetCPM) + `

Select new value or enter custom:`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("500", "set_cpm_500"),
			tgbotapi.NewInlineKeyboardButtonData("1000", "set_cpm_1000"),
			tgbotapi.NewInlineKeyboardButtonData("2000", "set_cpm_2000"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("5000", "set_cpm_5000"),
			tgbotapi.NewInlineKeyboardButtonData("10000", "set_cpm_10000"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✏️ Custom", "custom_cpm"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_checker"),
		),
	)

	return text, keyboard
}

func (m *Manager) handleConfigCPM(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getConfigCPMContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editConfigCPM(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getConfigCPMContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getConfigBatchContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `📦 **Configure Batch Size**

Current: ` + fmt.Sprintf("%d", m.settings.CheckerSettings.BatchSize) + `

Select new value or enter custom:`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("10", "set_batch_10"),
			tgbotapi.NewInlineKeyboardButtonData("25", "set_batch_25"),
			tgbotapi.NewInlineKeyboardButtonData("50", "set_batch_50"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("100", "set_batch_100"),
			tgbotapi.NewInlineKeyboardButtonData("200", "set_batch_200"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✏️ Custom", "custom_batch"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_checker"),
		),
	)

	return text, keyboard
}

func (m *Manager) handleConfigBatch(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard := m.getConfigBatchContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editConfigBatch(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getConfigBatchContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) getConfigProxiesContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := fmt.Sprintf(`🔄 **Proxy Setting Updated**

Use Your Proxies: %s

This setting now applies to all users globally.`, boolToEmoji(m.settings.CheckerSettings.UseUserProxy))

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back to Checker Settings", "admin_checker"),
		),
	)

	return text, keyboard
}

func (m *Manager) handleConfigProxies(bot *tgbotapi.BotAPI, chatID int64) {
	// Toggle the proxy setting
	m.settings.CheckerSettings.UseUserProxy = !m.settings.CheckerSettings.UseUserProxy
	m.SaveSettings()

	text, keyboard := m.getConfigProxiesContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editConfigProxies(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	// Toggle the proxy setting
	m.settings.CheckerSettings.UseUserProxy = !m.settings.CheckerSettings.UseUserProxy
	m.SaveSettings()

	text, keyboard := m.getConfigProxiesContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// User Details Handler
func (m *Manager) getUserDetailsContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup, error) {
	user, err := m.userManager.GetUser(userID)
	
	defaultKeyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back to Users", "admin_users"),
		),
	)
	
	if err != nil {
		return "❌ Error getting user details: " + err.Error(), defaultKeyboard, err
	}

	status := "✅ Active"
	if user.IsBanned {
		status = "🚫 Banned"
	}

	name := user.Username
	if name == "" {
		if user.FirstName != "" {
			name = user.FirstName
		} else {
			name = fmt.Sprintf("User_%d", user.UserID)
		}
	}

	apiStatus := "❌ No Bot Key"
	if user.APIKey != "" {
		apiStatus = "✅ Has Bot Key"
	}

	text := fmt.Sprintf(`👤 User Details

%s (ID: %d)
Status: %s
Bot Key: %s

Usage Statistics:
• Daily Searches: %d/%d
• Daily Downloads: %d
• Total Searches: %d

Management Actions:
Use the buttons below to manage this user.`,
		name, user.UserID, status, apiStatus,
		user.DailySearchCount, user.DailyLimit, user.DailyDownloadCount, user.TotalSearchCount)

	var keyboard [][]tgbotapi.InlineKeyboardButton

	// Ban/Unban button
	if user.IsBanned {
		keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✅ Unban User", fmt.Sprintf("unban_%d", userID)),
		))
	} else {
		keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🚫 Ban User", fmt.Sprintf("ban_%d", userID)),
		))
	}

	// Bot Key management
	if user.APIKey != "" {
		keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔑 Remove Bot Key", fmt.Sprintf("remove_api_%d", userID)),
		))
	} else {
		keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔑 Give Bot Key", fmt.Sprintf("give_api_%d", userID)),
		))
	}

	// Limit management
	keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
		tgbotapi.NewInlineKeyboardButtonData("⚙️ Set Limits", fmt.Sprintf("user_limits_%d", userID)),
		tgbotapi.NewInlineKeyboardButtonData("🔄 Reset Usage", fmt.Sprintf("reset_usage_%d", userID)),
	))

	// Back button
	keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
		tgbotapi.NewInlineKeyboardButtonData("⬅️ Back to Users", "admin_users"),
	))

	return text, tgbotapi.NewInlineKeyboardMarkup(keyboard...), nil
}

func (m *Manager) showUserDetails(bot *tgbotapi.BotAPI, chatID int64, userID int64) {
	text, keyboard, _ := m.getUserDetailsContent(userID)
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editUserDetails(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text, keyboard, _ := m.getUserDetailsContent(userID)
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// Show Bot Key Details for a specific user
func (m *Manager) getAPIKeyDetailsContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup, error) {
	user, err := m.userManager.GetUser(userID)
	
	defaultKeyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back to Bot Keys", "admin_api_keys"),
		),
	)
	
	if err != nil {
		return "❌ Error getting user details: " + err.Error(), defaultKeyboard, err
	}

	name := user.Username
	if name == "" {
		if user.FirstName != "" {
			name = user.FirstName
		} else {
			name = fmt.Sprintf("User_%d", user.UserID)
		}
	}

	status := "✅ Active"
	if user.IsBanned {
		status = "🚫 Banned"
	}

	text := fmt.Sprintf(`🔑 **Bot Key Details**

**User:** %s (ID: %d)
**Status:** %s
**Bot Key:** %s

**Usage Statistics:**
• Daily Searches: %d/%d
• Daily Downloads: %d
• Total Searches: %d

**Bot Key Management:**
Use the buttons below to manage this user's Bot Key.`,
		name, user.UserID, status, user.APIKey,
		user.DailySearchCount, user.DailyLimit, user.DailyDownloadCount, user.TotalSearchCount)

	var keyboard [][]tgbotapi.InlineKeyboardButton

	// Bot Key actions
	keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
		tgbotapi.NewInlineKeyboardButtonData("🔄 Regenerate Key", fmt.Sprintf("regen_api_%d", userID)),
		tgbotapi.NewInlineKeyboardButtonData("🗑️ Delete Key", fmt.Sprintf("delete_api_%d", userID)),
	))

	// User status actions
	if user.IsBanned {
		keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✅ Enable User", fmt.Sprintf("enable_api_user_%d", userID)),
		))
	} else {
		keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🚫 Disable User", fmt.Sprintf("disable_api_user_%d", userID)),
		))
	}

	// Back button
	keyboard = append(keyboard, tgbotapi.NewInlineKeyboardRow(
		tgbotapi.NewInlineKeyboardButtonData("⬅️ Back to Bot Keys", "admin_api_keys"),
	))

	return text, tgbotapi.NewInlineKeyboardMarkup(keyboard...), nil
}

func (m *Manager) showAPIKeyDetails(bot *tgbotapi.BotAPI, chatID int64, userID int64) {
	text, keyboard, _ := m.getAPIKeyDetailsContent(userID)
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editAPIKeyDetails(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text, keyboard, _ := m.getAPIKeyDetailsContent(userID)
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// Show all Bot Keys in a detailed view
func (m *Manager) getAllAPIKeysContent() (string, tgbotapi.InlineKeyboardMarkup, error) {
	users, err := m.userManager.GetAllUsers()
	
	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔄 Refresh", "view_all_keys"),
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_api_keys"),
		),
	)
	
	if err != nil {
		return "❌ Error getting users: " + err.Error(), keyboard, err
	}

	text := "📋 **All Bot Keys**\n\n"
	
	// Count users with Bot Keys
	usersWithKeys := 0
	for _, user := range users {
		if user.APIKey != "" {
			usersWithKeys++
		}
	}

	if usersWithKeys == 0 {
		text += "No Bot Keys have been generated yet.\n"
	} else {
		text += fmt.Sprintf("**Total Bot Keys:** %d\n\n", usersWithKeys)
		
		for _, user := range users {
			if user.APIKey != "" {
				name := user.Username
				if name == "" {
					name = fmt.Sprintf("User_%d", user.UserID)
				}
				
				status := "✅"
				if user.IsBanned {
					status = "🚫"
				}
				
				text += fmt.Sprintf(`%s **%s** (ID: %d)
🔑 **Key:** %s
📊 **Usage:** %d/%d searches, %d downloads

`, status, name, user.UserID, user.APIKey, user.DailySearchCount, user.DailyLimit, user.DailyDownloadCount)
			}
		}
	}

	return text, keyboard, nil
}

func (m *Manager) showAllAPIKeys(bot *tgbotapi.BotAPI, chatID int64) {
	text, keyboard, _ := m.getAllAPIKeysContent()
	msg := tgbotapi.NewMessage(chatID, text)
	msg.ParseMode = "Markdown"
	msg.ReplyMarkup = keyboard
	bot.Send(msg)
}

func (m *Manager) editAllAPIKeys(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard, _ := m.getAllAPIKeysContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// Global Limits Configuration
func (m *Manager) getGlobalLimitsContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := fmt.Sprintf(`📊 **Global Limits Configuration**

**Current Limits:**
• 🔍 Search Limit: %d/day
• 📥 Download Limit: %d/day
• 🌐 Proxy Limit: %d per user

Select a limit to configure:`,
		m.settings.GlobalDailyLimit,
		m.settings.GlobalDownloadLimit,
		m.settings.GlobalProxyLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔍 Search Limit", "config_search_limit"),
			tgbotapi.NewInlineKeyboardButtonData("📥 Download Limit", "config_download_limit"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🌐 Proxy Limit", "config_proxy_limit"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "admin_settings"),
		),
	)

	return text, keyboard
}

func (m *Manager) editGlobalLimits(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getGlobalLimitsContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// Global Search Limit Configuration
func (m *Manager) getConfigSearchLimitContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `🔍 **Configure Global Search Limit**

Current: ` + fmt.Sprintf("%d", m.settings.GlobalDailyLimit) + `/day

Select new value or enter custom:`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("10,000", "set_global_search_10000"),
			tgbotapi.NewInlineKeyboardButtonData("25,000", "set_global_search_25000"),
			tgbotapi.NewInlineKeyboardButtonData("50,000", "set_global_search_50000"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("100,000", "set_global_search_100000"),
			tgbotapi.NewInlineKeyboardButtonData("Unlimited", "set_global_search_999999999"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✏️ Custom", "custom_search_limit"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "config_global_limits"),
		),
	)

	return text, keyboard
}

func (m *Manager) editConfigSearchLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getConfigSearchLimitContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// Global Download Limit Configuration
func (m *Manager) getConfigDownloadLimitContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `📥 **Configure Global Download Limit**

Current: ` + fmt.Sprintf("%d", m.settings.GlobalDownloadLimit) + `/day

Select new value or enter custom:`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("5,000", "set_global_download_5000"),
			tgbotapi.NewInlineKeyboardButtonData("10,000", "set_global_download_10000"),
			tgbotapi.NewInlineKeyboardButtonData("25,000", "set_global_download_25000"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("50,000", "set_global_download_50000"),
			tgbotapi.NewInlineKeyboardButtonData("Unlimited", "set_global_download_999999999"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✏️ Custom", "custom_download_limit"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "config_global_limits"),
		),
	)

	return text, keyboard
}

func (m *Manager) editConfigDownloadLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getConfigDownloadLimitContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// Global Proxy Limit Configuration
func (m *Manager) getConfigProxyLimitContent() (string, tgbotapi.InlineKeyboardMarkup) {
	text := `🌐 **Configure Global Proxy Limit**

Current: ` + fmt.Sprintf("%d", m.settings.GlobalProxyLimit) + ` proxies per user

Select new value or enter custom:`

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("3", "set_global_proxy_3"),
			tgbotapi.NewInlineKeyboardButtonData("5", "set_global_proxy_5"),
			tgbotapi.NewInlineKeyboardButtonData("10", "set_global_proxy_10"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("15", "set_global_proxy_15"),
			tgbotapi.NewInlineKeyboardButtonData("20", "set_global_proxy_20"),
			tgbotapi.NewInlineKeyboardButtonData("Unlimited", "set_global_proxy_999999"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✏️ Custom", "custom_proxy_limit"),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", "config_global_limits"),
		),
	)

	return text, keyboard
}

func (m *Manager) editConfigProxyLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int) {
	text, keyboard := m.getConfigProxyLimitContent()
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

func (m *Manager) promptCustomProxyLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text := `🌐 **Custom Proxy Limit**

Enter the maximum number of proxies per user:

Current: ` + fmt.Sprintf("%d", m.settings.GlobalProxyLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", "config_proxy_limit"),
		),
	)

	m.editMessage(bot, chatID, messageID, text, &keyboard)
	m.SetAdminState(userID, "waiting_custom_proxy_limit")
}

// User Limits Configuration
func (m *Manager) getUserLimitsContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup, error) {
	user, err := m.userManager.GetUser(userID)
	
	defaultKeyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", fmt.Sprintf("user_%d", userID)),
		),
	)
	
	if err != nil {
		return "❌ Error getting user: " + err.Error(), defaultKeyboard, err
	}

	name := user.Username
	if name == "" {
		if user.FirstName != "" {
			name = user.FirstName
		} else {
			name = fmt.Sprintf("User_%d", user.UserID)
		}
	}

	text := fmt.Sprintf(`📊 **User Limits - %s**

**Current Limits:**
• 🔍 Search Limit: %d/day
• 📥 Download Limit: %d/day

**Current Usage:**
• Searches: %d/%d
• Downloads: %d/%d

Select a limit to configure:`,
		name,
		user.DailyLimit,
		user.DailyDownloadLimit,
		user.DailySearchCount, user.DailyLimit,
		user.DailyDownloadCount, user.DailyDownloadLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("🔍 Search Limit", fmt.Sprintf("config_user_search_%d", userID)),
			tgbotapi.NewInlineKeyboardButtonData("📥 Download Limit", fmt.Sprintf("config_user_download_%d", userID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", fmt.Sprintf("user_%d", userID)),
		),
	)

	return text, keyboard, nil
}

func (m *Manager) editUserLimits(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text, keyboard, _ := m.getUserLimitsContent(userID)
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// User Search Limit Configuration
func (m *Manager) getConfigUserSearchLimitContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup) {
	user, _ := m.userManager.GetUser(userID)
	currentLimit := 50000
	if user != nil {
		currentLimit = user.DailyLimit
	}

	text := fmt.Sprintf(`🔍 **Configure User Search Limit**

Current: %d/day

Select new value or enter custom:`, currentLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("10,000", fmt.Sprintf("set_user_search_limit_%d_10000", userID)),
			tgbotapi.NewInlineKeyboardButtonData("25,000", fmt.Sprintf("set_user_search_limit_%d_25000", userID)),
			tgbotapi.NewInlineKeyboardButtonData("50,000", fmt.Sprintf("set_user_search_limit_%d_50000", userID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("100,000", fmt.Sprintf("set_user_search_limit_%d_100000", userID)),
			tgbotapi.NewInlineKeyboardButtonData("Unlimited", fmt.Sprintf("set_user_search_limit_%d_999999999", userID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✏️ Custom", fmt.Sprintf("custom_user_search_%d", userID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", fmt.Sprintf("user_limits_%d", userID)),
		),
	)

	return text, keyboard
}

func (m *Manager) editConfigUserSearchLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text, keyboard := m.getConfigUserSearchLimitContent(userID)
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// User Download Limit Configuration
func (m *Manager) getConfigUserDownloadLimitContent(userID int64) (string, tgbotapi.InlineKeyboardMarkup) {
	user, _ := m.userManager.GetUser(userID)
	currentLimit := 10000
	if user != nil {
		currentLimit = user.DailyDownloadLimit
	}

	text := fmt.Sprintf(`📥 **Configure User Download Limit**

Current: %d/day

Select new value or enter custom:`, currentLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("5,000", fmt.Sprintf("set_user_download_limit_%d_5000", userID)),
			tgbotapi.NewInlineKeyboardButtonData("10,000", fmt.Sprintf("set_user_download_limit_%d_10000", userID)),
			tgbotapi.NewInlineKeyboardButtonData("25,000", fmt.Sprintf("set_user_download_limit_%d_25000", userID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("50,000", fmt.Sprintf("set_user_download_limit_%d_50000", userID)),
			tgbotapi.NewInlineKeyboardButtonData("Unlimited", fmt.Sprintf("set_user_download_limit_%d_999999999", userID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("✏️ Custom", fmt.Sprintf("custom_user_download_%d", userID)),
		),
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("⬅️ Back", fmt.Sprintf("user_limits_%d", userID)),
		),
	)

	return text, keyboard
}

func (m *Manager) editConfigUserDownloadLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text, keyboard := m.getConfigUserDownloadLimitContent(userID)
	m.editMessage(bot, chatID, messageID, text, &keyboard)
}

// Custom input prompt functions
func (m *Manager) promptCustomWorkers(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text := `✏️ **Enter Custom Max Workers**

Please send a number for the max workers value.

Current: ` + fmt.Sprintf("%d", m.settings.CheckerSettings.MaxWorkers)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", "config_workers"),
		),
	)

	m.editMessage(bot, chatID, messageID, text, &keyboard)
	// Set admin state to wait for custom workers input
	m.SetAdminState(userID, "waiting_custom_workers")
}

func (m *Manager) promptCustomCPM(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text := `✏️ **Enter Custom Target CPM**

Please send a number for the target CPM value.

Current: ` + fmt.Sprintf("%d", m.settings.CheckerSettings.TargetCPM)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", "config_cpm"),
		),
	)

	m.editMessage(bot, chatID, messageID, text, &keyboard)
	m.SetAdminState(userID, "waiting_custom_cpm")
}

func (m *Manager) promptCustomBatch(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text := `✏️ **Enter Custom Batch Size**

Please send a number for the batch size value.

Current: ` + fmt.Sprintf("%d", m.settings.CheckerSettings.BatchSize)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", "config_batch"),
		),
	)

	m.editMessage(bot, chatID, messageID, text, &keyboard)
	m.SetAdminState(userID, "waiting_custom_batch")
}

func (m *Manager) promptCustomSearchLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text := `✏️ **Enter Custom Global Search Limit**

Please send a number for the global daily search limit.

Current: ` + fmt.Sprintf("%d", m.settings.GlobalDailyLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", "config_global_limits"),
		),
	)

	m.editMessage(bot, chatID, messageID, text, &keyboard)
	m.SetAdminState(userID, "waiting_custom_search_limit")
}

func (m *Manager) promptCustomDownloadLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int, userID int64) {
	text := `✏️ **Enter Custom Global Download Limit**

Please send a number for the global daily download limit.

Current: ` + fmt.Sprintf("%d", m.settings.GlobalDownloadLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", "config_global_limits"),
		),
	)

	m.editMessage(bot, chatID, messageID, text, &keyboard)
	m.SetAdminState(userID, "waiting_custom_download_limit")
}

func (m *Manager) promptCustomUserSearchLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int, adminID int64, targetUserID int64) {
	user, _ := m.userManager.GetUser(targetUserID)
	currentLimit := 0
	if user != nil {
		currentLimit = user.DailyLimit
	}

	text := fmt.Sprintf(`✏️ **Enter Custom Search Limit**

Please send a number for this user's daily search limit.

Current: %d`, currentLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", fmt.Sprintf("user_limits_%d", targetUserID)),
		),
	)

	m.editMessage(bot, chatID, messageID, text, &keyboard)
	m.SetAdminState(adminID, fmt.Sprintf("waiting_user_search_limit_%d", targetUserID))
}

func (m *Manager) promptCustomUserDownloadLimit(bot *tgbotapi.BotAPI, chatID int64, messageID int, adminID int64, targetUserID int64) {
	user, _ := m.userManager.GetUser(targetUserID)
	currentLimit := 0
	if user != nil {
		currentLimit = user.DailyDownloadLimit
	}

	text := fmt.Sprintf(`✏️ **Enter Custom Download Limit**

Please send a number for this user's daily download limit.

Current: %d`, currentLimit)

	keyboard := tgbotapi.NewInlineKeyboardMarkup(
		tgbotapi.NewInlineKeyboardRow(
			tgbotapi.NewInlineKeyboardButtonData("❌ Cancel", fmt.Sprintf("user_limits_%d", targetUserID)),
		),
	)

	m.editMessage(bot, chatID, messageID, text, &keyboard)
	m.SetAdminState(adminID, fmt.Sprintf("waiting_user_download_limit_%d", targetUserID))
}

// Admin state management for custom input
var adminStates = make(map[int64]string)

func (m *Manager) SetAdminState(userID int64, state string) {
	adminStates[userID] = state
}

func (m *Manager) GetAdminState(userID int64) string {
	return adminStates[userID]
}

func (m *Manager) ClearAdminState(userID int64) {
	delete(adminStates, userID)
}

// HandleAdminInput processes text input from admin for custom values
func (m *Manager) HandleAdminInput(bot *tgbotapi.BotAPI, chatID int64, userID int64, text string) bool {
	state := m.GetAdminState(userID)
	if state == "" {
		return false
	}

	value, err := strconv.Atoi(strings.TrimSpace(text))
	if err != nil {
		msg := tgbotapi.NewMessage(chatID, "❌ Invalid number. Please enter a valid number.")
		bot.Send(msg)
		return true
	}

	switch {
	case state == "waiting_custom_workers":
		m.settings.CheckerSettings.MaxWorkers = value
		m.SaveSettings()
		m.ClearAdminState(userID)
		msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ Max Workers set to %d", value))
		bot.Send(msg)
		m.showCheckerSettings(bot, chatID)
		return true

	case state == "waiting_custom_cpm":
		m.settings.CheckerSettings.TargetCPM = value
		m.SaveSettings()
		m.ClearAdminState(userID)
		msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ Target CPM set to %d", value))
		bot.Send(msg)
		m.showCheckerSettings(bot, chatID)
		return true

	case state == "waiting_custom_batch":
		m.settings.CheckerSettings.BatchSize = value
		m.SaveSettings()
		m.ClearAdminState(userID)
		msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ Batch Size set to %d", value))
		bot.Send(msg)
		m.showCheckerSettings(bot, chatID)
		return true

	case state == "waiting_custom_search_limit":
		m.settings.GlobalDailyLimit = value
		m.SaveSettings()
		m.ClearAdminState(userID)
		msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ Global Search Limit set to %d", value))
		bot.Send(msg)
		m.showSettings(bot, chatID)
		return true

	case state == "waiting_custom_download_limit":
		m.settings.GlobalDownloadLimit = value
		m.SaveSettings()
		m.ClearAdminState(userID)
		msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ Global Download Limit set to %d", value))
		bot.Send(msg)
		m.showSettings(bot, chatID)
		return true

	case state == "waiting_custom_proxy_limit":
		m.settings.GlobalProxyLimit = value
		m.SaveSettings()
		m.ClearAdminState(userID)
		msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ Global Proxy Limit set to %d proxies per user", value))
		bot.Send(msg)
		m.showSettings(bot, chatID)
		return true

	case strings.HasPrefix(state, "waiting_user_search_limit_"):
		targetUserIDStr := strings.TrimPrefix(state, "waiting_user_search_limit_")
		if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
			m.userManager.SetUserLimit(targetUserID, value)
			m.ClearAdminState(userID)
			msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ User Search Limit set to %d", value))
			bot.Send(msg)
			m.showUserDetails(bot, chatID, targetUserID)
			return true
		}

	case strings.HasPrefix(state, "waiting_user_download_limit_"):
		targetUserIDStr := strings.TrimPrefix(state, "waiting_user_download_limit_")
		if targetUserID, err := strconv.ParseInt(targetUserIDStr, 10, 64); err == nil {
			m.userManager.SetUserDownloadLimit(targetUserID, value)
			m.ClearAdminState(userID)
			msg := tgbotapi.NewMessage(chatID, fmt.Sprintf("✅ User Download Limit set to %d", value))
			bot.Send(msg)
			m.showUserDetails(bot, chatID, targetUserID)
			return true
		}
	}

	return false
}
