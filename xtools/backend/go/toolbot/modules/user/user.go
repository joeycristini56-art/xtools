package user

import (
	"database/sql"
	"fmt"
	"time"
)

type User struct {
	UserID             int64     `json:"user_id"`
	Username           string    `json:"username"`
	FirstName          string    `json:"first_name"`
	APIKey             string    `json:"api_key"`
	DailySearchCount   int       `json:"daily_search_count"`
	DailyDownloadCount int       `json:"daily_download_count"`
	TotalSearchCount   int       `json:"total_search_count"`
	TotalDownloadCount int       `json:"total_download_count"`
	DailyLimit         int       `json:"daily_limit"`
	DailyDownloadLimit int       `json:"daily_download_limit"`
	HasCustomSearchLimit   bool  `json:"has_custom_search_limit"`
	HasCustomDownloadLimit bool  `json:"has_custom_download_limit"`
	IsBanned           bool      `json:"is_banned"`
	CreatedAt          time.Time `json:"created_at"`
	LastActivity       time.Time `json:"last_activity"`
	LastResetDate      string    `json:"last_reset_date"`
}

// GlobalLimitsFunc is a function type that returns global search and download limits
type GlobalLimitsFunc func() (searchLimit int, downloadLimit int)

type Manager struct {
	db               *sql.DB
	getGlobalLimits  GlobalLimitsFunc
}

func NewManager(db *sql.DB) *Manager {
	return &Manager{
		db: db,
		getGlobalLimits: func() (int, int) {
			return 50000, 10000 // Default fallback values
		},
	}
}

// SetGlobalLimitsFunc sets the function to get global limits from admin settings
func (m *Manager) SetGlobalLimitsFunc(fn GlobalLimitsFunc) {
	m.getGlobalLimits = fn
}

func (m *Manager) GetOrCreateUser(userID int64, username, firstName string) (*User, error) {
	user, err := m.GetUser(userID)
	if err == nil {
		// User exists, update activity and reset daily counts if needed
		return m.updateUserActivity(user, username, firstName)
	}

	// User doesn't exist, create new one
	return m.createUser(userID, username, firstName)
}

func (m *Manager) GetUser(userID int64) (*User, error) {
	query := `
	SELECT user_id, username, COALESCE(first_name, '') as first_name, api_key, 
	       daily_search_count, daily_download_count, total_search_count, 
	       total_download_count, daily_limit, COALESCE(daily_download_limit, 10000) as daily_download_limit,
	       COALESCE(has_custom_search_limit, 0) as has_custom_search_limit,
	       COALESCE(has_custom_download_limit, 0) as has_custom_download_limit,
	       is_banned, created_at, last_activity, last_reset_date
	FROM users WHERE user_id = ?`

	user := &User{}
	err := m.db.QueryRow(query, userID).Scan(
		&user.UserID, &user.Username, &user.FirstName, &user.APIKey, &user.DailySearchCount, &user.DailyDownloadCount,
		&user.TotalSearchCount, &user.TotalDownloadCount, &user.DailyLimit, &user.DailyDownloadLimit,
		&user.HasCustomSearchLimit, &user.HasCustomDownloadLimit,
		&user.IsBanned, &user.CreatedAt, &user.LastActivity, &user.LastResetDate,
	)

	if err != nil {
		return nil, err
	}

	// If user doesn't have custom limits, use global limits from admin settings
	globalSearchLimit, globalDownloadLimit := m.getGlobalLimits()
	if !user.HasCustomSearchLimit {
		user.DailyLimit = globalSearchLimit
	}
	if !user.HasCustomDownloadLimit {
		user.DailyDownloadLimit = globalDownloadLimit
	}

	return user, nil
}

func (m *Manager) createUser(userID int64, username, firstName string) (*User, error) {
	// Don't automatically assign API key - users need to redeem one
	now := time.Now()
	today := now.Format("2006-01-02")

	// Get global limits from admin settings
	searchLimit, downloadLimit := m.getGlobalLimits()

	query := `
	INSERT INTO users (user_id, username, first_name, api_key, 
	                  daily_search_count, daily_download_count, total_search_count, 
	                  total_download_count, daily_limit, daily_download_limit, is_banned, created_at, 
	                  last_activity, last_reset_date)
	VALUES (?, ?, ?, '', 0, 0, 0, 0, ?, ?, FALSE, ?, ?, ?)`

	_, err := m.db.Exec(query, userID, username, firstName, searchLimit, downloadLimit, now, now, today)
	if err != nil {
		return nil, err
	}

	return m.GetUser(userID)
}

func (m *Manager) updateUserActivity(user *User, username, firstName string) (*User, error) {
	now := time.Now()
	today := now.Format("2006-01-02")

	// Reset daily counts if it's a new day
	if user.LastResetDate != today {
		query := `
		UPDATE users SET username = ?, first_name = ?, 
		                daily_search_count = 0, daily_download_count = 0,
		                last_activity = ?, last_reset_date = ?
		WHERE user_id = ?`

		_, err := m.db.Exec(query, username, firstName, now, today, user.UserID)
		if err != nil {
			return nil, err
		}
	} else {
		// Just update activity, username and first_name
		query := `
		UPDATE users SET username = ?, first_name = ?, last_activity = ?
		WHERE user_id = ?`

		_, err := m.db.Exec(query, username, firstName, now, user.UserID)
		if err != nil {
			return nil, err
		}
	}

	return m.GetUser(user.UserID)
}

func (m *Manager) IncrementSearchCount(userID int64) error {
	query := `
	UPDATE users SET daily_search_count = daily_search_count + 1,
	                total_search_count = total_search_count + 1,
	                last_activity = ?
	WHERE user_id = ?`

	_, err := m.db.Exec(query, time.Now(), userID)
	return err
}

func (m *Manager) IncrementDownloadCount(userID int64) error {
	return m.IncrementDownloadCountBy(userID, 1)
}

// IncrementDownloadCountBy increments the download count by a specific amount
func (m *Manager) IncrementDownloadCountBy(userID int64, amount int) error {
	query := `
	UPDATE users SET daily_download_count = daily_download_count + ?,
	                total_download_count = total_download_count + ?,
	                last_activity = ?
	WHERE user_id = ?`

	_, err := m.db.Exec(query, amount, amount, time.Now(), userID)
	return err
}

func (m *Manager) CanSearch(userID int64) (bool, error) {
	user, err := m.GetUser(userID)
	if err != nil {
		return false, err
	}

	if user.IsBanned {
		return false, fmt.Errorf("user is banned")
	}

	if user.DailySearchCount >= user.DailyLimit {
		return false, fmt.Errorf("daily search limit reached")
	}

	return true, nil
}

func (m *Manager) CanDownload(userID int64) (bool, error) {
	return m.CanDownloadAmount(userID, 1)
}

// CanDownloadAmount checks if user can download a specific amount
func (m *Manager) CanDownloadAmount(userID int64, amount int) (bool, error) {
	user, err := m.GetUser(userID)
	if err != nil {
		return false, err
	}

	if user.IsBanned {
		return false, fmt.Errorf("user is banned")
	}

	if user.DailyDownloadCount+amount > user.DailyDownloadLimit {
		return false, fmt.Errorf("daily download limit reached")
	}

	return true, nil
}

// GetRemainingDownloads returns how many downloads the user has left
func (m *Manager) GetRemainingDownloads(userID int64) (int, error) {
	user, err := m.GetUser(userID)
	if err != nil {
		return 0, err
	}
	remaining := user.DailyDownloadLimit - user.DailyDownloadCount
	if remaining < 0 {
		remaining = 0
	}
	return remaining, nil
}

func (m *Manager) SetUserLimit(userID int64, limit int) error {
	// Set custom search limit and mark as custom
	query := `UPDATE users SET daily_limit = ?, has_custom_search_limit = 1 WHERE user_id = ?`
	_, err := m.db.Exec(query, limit, userID)
	return err
}

func (m *Manager) SetUserDownloadLimit(userID int64, limit int) error {
	// Set custom download limit and mark as custom
	query := `UPDATE users SET daily_download_limit = ?, has_custom_download_limit = 1 WHERE user_id = ?`
	_, err := m.db.Exec(query, limit, userID)
	return err
}

// ResetUserToGlobalLimits resets a user to use global limits instead of custom limits
func (m *Manager) ResetUserToGlobalLimits(userID int64) error {
	query := `UPDATE users SET has_custom_search_limit = 0, has_custom_download_limit = 0 WHERE user_id = ?`
	_, err := m.db.Exec(query, userID)
	return err
}

func (m *Manager) BanUser(userID int64) error {
	query := `UPDATE users SET is_banned = TRUE WHERE user_id = ?`
	_, err := m.db.Exec(query, userID)
	return err
}

func (m *Manager) UnbanUser(userID int64) error {
	query := `UPDATE users SET is_banned = FALSE WHERE user_id = ?`
	_, err := m.db.Exec(query, userID)
	return err
}

func (m *Manager) GetAllUsers() ([]*User, error) {
	query := `
	SELECT user_id, username, COALESCE(first_name, '') as first_name, api_key, 
	       daily_search_count, daily_download_count, total_search_count, 
	       total_download_count, daily_limit, COALESCE(daily_download_limit, 10000) as daily_download_limit,
	       COALESCE(has_custom_search_limit, 0) as has_custom_search_limit,
	       COALESCE(has_custom_download_limit, 0) as has_custom_download_limit,
	       is_banned, created_at, last_activity, last_reset_date
	FROM users ORDER BY last_activity DESC`

	rows, err := m.db.Query(query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	globalSearchLimit, globalDownloadLimit := m.getGlobalLimits()

	var users []*User
	for rows.Next() {
		user := &User{}
		err := rows.Scan(
			&user.UserID, &user.Username, &user.FirstName, &user.APIKey, &user.DailySearchCount, &user.DailyDownloadCount,
			&user.TotalSearchCount, &user.TotalDownloadCount, &user.DailyLimit, &user.DailyDownloadLimit,
			&user.HasCustomSearchLimit, &user.HasCustomDownloadLimit,
			&user.IsBanned, &user.CreatedAt, &user.LastActivity, &user.LastResetDate,
		)
		if err != nil {
			continue
		}
		// Apply global limits if no custom limits set
		if !user.HasCustomSearchLimit {
			user.DailyLimit = globalSearchLimit
		}
		if !user.HasCustomDownloadLimit {
			user.DailyDownloadLimit = globalDownloadLimit
		}
		users = append(users, user)
	}

	return users, nil
}

func (m *Manager) GetUserStats() (map[string]interface{}, error) {
	stats := make(map[string]interface{})

	// Total users
	var totalUsers int
	err := m.db.QueryRow("SELECT COUNT(*) FROM users").Scan(&totalUsers)
	if err != nil {
		return nil, err
	}
	stats["total_users"] = totalUsers

	// Active users today
	today := time.Now().Format("2006-01-02")
	var activeToday int
	err = m.db.QueryRow("SELECT COUNT(*) FROM users WHERE DATE(last_activity) = ?", today).Scan(&activeToday)
	if err != nil {
		return nil, err
	}
	stats["active_today"] = activeToday

	// Banned users
	var bannedUsers int
	err = m.db.QueryRow("SELECT COUNT(*) FROM users WHERE is_banned = TRUE").Scan(&bannedUsers)
	if err != nil {
		return nil, err
	}
	stats["banned_users"] = bannedUsers

	// Total searches today
	var searchesToday int
	err = m.db.QueryRow("SELECT COALESCE(SUM(daily_search_count), 0) FROM users WHERE last_reset_date = ?", today).Scan(&searchesToday)
	if err != nil {
		return nil, err
	}
	stats["searches_today"] = searchesToday

	// Total downloads today
	var downloadsToday int
	err = m.db.QueryRow("SELECT COALESCE(SUM(daily_download_count), 0) FROM users WHERE last_reset_date = ?", today).Scan(&downloadsToday)
	if err != nil {
		return nil, err
	}
	stats["downloads_today"] = downloadsToday

	return stats, nil
}

func (m *Manager) HasAPIKey(userID int64) bool {
	user, err := m.GetUser(userID)
	if err != nil {
		return false
	}
	return user.APIKey != ""
}

func (m *Manager) SetAPIKey(userID int64, apiKey string) error {
	query := `UPDATE users SET api_key = ? WHERE user_id = ?`
	_, err := m.db.Exec(query, apiKey, userID)
	return err
}

func (m *Manager) ValidateAPIKey(apiKey string) (*User, error) {
	query := `
	SELECT user_id, username, api_key, 
	       daily_search_count, daily_download_count, total_search_count, 
	       total_download_count, daily_limit, is_banned, created_at, 
	       last_activity, last_reset_date
	FROM users WHERE api_key = ?`

	user := &User{}
	err := m.db.QueryRow(query, apiKey).Scan(
		&user.UserID, &user.Username, &user.APIKey, &user.DailySearchCount, &user.DailyDownloadCount,
		&user.TotalSearchCount, &user.TotalDownloadCount, &user.DailyLimit,
		&user.IsBanned, &user.CreatedAt, &user.LastActivity, &user.LastResetDate,
	)

	if err != nil {
		return nil, err
	}

	return user, nil
}
// UpdateCheckStats updates user's checking statistics
func (m *Manager) UpdateCheckStats(userID int64, valid, invalid int) error {
	query := `UPDATE users SET 
		total_search_count = total_search_count + ?,
		total_download_count = total_download_count + ?,
		last_activity = CURRENT_TIMESTAMP
		WHERE user_id = ?`
	
	_, err := m.db.Exec(query, valid+invalid, valid, userID)
	return err
}

// ResetUserUsage resets daily usage counts for a user
func (m *Manager) ResetUserUsage(userID int64) error {
	query := `UPDATE users SET daily_search_count = 0, daily_download_count = 0 WHERE user_id = ?`
	_, err := m.db.Exec(query, userID)
	return err
}
