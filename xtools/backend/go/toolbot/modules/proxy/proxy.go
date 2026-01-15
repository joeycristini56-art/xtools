package proxy

import (
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

type Proxy struct {
	ID           int       `json:"id"`
	UserID       int64     `json:"user_id"`
	ProxyURL     string    `json:"proxy_url"`
	ProxyType    string    `json:"proxy_type"`
	Username     string    `json:"username"`
	Password     string    `json:"password"`
	IsActive     bool      `json:"is_active"`
	LastChecked  time.Time `json:"last_checked"`
	IsWorking    bool      `json:"is_working"`
	ResponseTime int       `json:"response_time"`
	CreatedAt    time.Time `json:"created_at"`
}

type Manager struct {
	db *sql.DB
}

func NewManager(db *sql.DB) *Manager {
	return &Manager{
		db: db,
	}
}

// GetUserProxyCount returns the number of proxies a user has
func (m *Manager) GetUserProxyCount(userID int64) (int, error) {
	var count int
	err := m.db.QueryRow("SELECT COUNT(*) FROM proxies WHERE user_id = ?", userID).Scan(&count)
	if err != nil {
		return 0, err
	}
	return count, nil
}

// AddProxy adds a new proxy for a specific user
func (m *Manager) AddProxy(userID int64, proxyURL, proxyType, username, password string) error {
	query := `INSERT INTO proxies (user_id, proxy_url, proxy_type, username, password) 
			  VALUES (?, ?, ?, ?, ?)`
	
	_, err := m.db.Exec(query, userID, proxyURL, proxyType, username, password)
	if err != nil {
		return fmt.Errorf("failed to add proxy: %v", err)
	}
	
	return nil
}

// AddProxyWithLimit adds a new proxy for a specific user, checking the limit first
func (m *Manager) AddProxyWithLimit(userID int64, proxyURL, proxyType, username, password string, maxProxies int) error {
	// Check current proxy count
	count, err := m.GetUserProxyCount(userID)
	if err != nil {
		return fmt.Errorf("failed to check proxy count: %v", err)
	}
	
	if count >= maxProxies {
		return fmt.Errorf("proxy limit reached (%d/%d)", count, maxProxies)
	}
	
	return m.AddProxy(userID, proxyURL, proxyType, username, password)
}

// GetUserProxies returns all proxies for a specific user
func (m *Manager) GetUserProxies(userID int64) ([]*Proxy, error) {
	query := `SELECT id, user_id, proxy_url, proxy_type, username, password, 
			  is_active, last_checked, is_working, response_time, created_at 
			  FROM proxies WHERE user_id = ? ORDER BY created_at DESC`
	
	rows, err := m.db.Query(query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var proxies []*Proxy
	for rows.Next() {
		proxy := &Proxy{}
		var lastChecked, createdAt sql.NullTime
		
		err := rows.Scan(
			&proxy.ID, &proxy.UserID, &proxy.ProxyURL, &proxy.ProxyType,
			&proxy.Username, &proxy.Password, &proxy.IsActive,
			&lastChecked, &proxy.IsWorking, &proxy.ResponseTime, &createdAt,
		)
		if err != nil {
			continue
		}
		
		if lastChecked.Valid {
			proxy.LastChecked = lastChecked.Time
		}
		if createdAt.Valid {
			proxy.CreatedAt = createdAt.Time
		}
		
		proxies = append(proxies, proxy)
	}
	
	return proxies, nil
}

// GetWorkingUserProxies returns only working proxies for a specific user
func (m *Manager) GetWorkingUserProxies(userID int64) ([]*Proxy, error) {
	query := `SELECT id, user_id, proxy_url, proxy_type, username, password, 
			  is_active, last_checked, is_working, response_time, created_at 
			  FROM proxies WHERE user_id = ? AND is_active = 1 AND is_working = 1 
			  ORDER BY response_time ASC`
	
	rows, err := m.db.Query(query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var proxies []*Proxy
	for rows.Next() {
		proxy := &Proxy{}
		var lastChecked, createdAt sql.NullTime
		
		err := rows.Scan(
			&proxy.ID, &proxy.UserID, &proxy.ProxyURL, &proxy.ProxyType,
			&proxy.Username, &proxy.Password, &proxy.IsActive,
			&lastChecked, &proxy.IsWorking, &proxy.ResponseTime, &createdAt,
		)
		if err != nil {
			continue
		}
		
		if lastChecked.Valid {
			proxy.LastChecked = lastChecked.Time
		}
		if createdAt.Valid {
			proxy.CreatedAt = createdAt.Time
		}
		
		proxies = append(proxies, proxy)
	}
	
	return proxies, nil
}

// DeleteProxy removes a proxy (user can only delete their own proxies)
func (m *Manager) DeleteProxy(userID int64, proxyID int) error {
	query := `DELETE FROM proxies WHERE id = ? AND user_id = ?`
	_, err := m.db.Exec(query, proxyID, userID)
	return err
}

// ToggleProxy toggles proxy active status (user can only toggle their own proxies)
func (m *Manager) ToggleProxy(userID int64, proxyID int) error {
	query := `UPDATE proxies SET is_active = NOT is_active WHERE id = ? AND user_id = ?`
	_, err := m.db.Exec(query, proxyID, userID)
	return err
}

// CheckProxy tests if a proxy is working
func (m *Manager) CheckProxy(proxy *Proxy) (bool, int) {
	start := time.Now()
	
	// Create proxy URL
	var proxyURLStr string
	if proxy.Username != "" && proxy.Password != "" {
		proxyURLStr = fmt.Sprintf("http://%s:%s@%s", proxy.Username, proxy.Password, proxy.ProxyURL)
	} else {
		proxyURLStr = fmt.Sprintf("http://%s", proxy.ProxyURL)
	}
	
	proxyURL, err := url.Parse(proxyURLStr)
	if err != nil {
		return false, 0
	}
	
	// Create HTTP client with proxy
	transport := &http.Transport{
		Proxy: http.ProxyURL(proxyURL),
	}
	
	client := &http.Client{
		Transport: transport,
		Timeout:   10 * time.Second,
	}
	
	// Test proxy with a simple request
	resp, err := client.Get("http://httpbin.org/ip")
	if err != nil {
		return false, 0
	}
	defer resp.Body.Close()
	
	responseTime := int(time.Since(start).Milliseconds())
	
	return resp.StatusCode == 200, responseTime
}

// UpdateProxyStatus updates proxy working status and response time
func (m *Manager) UpdateProxyStatus(proxyID int, isWorking bool, responseTime int) error {
	query := `UPDATE proxies SET is_working = ?, response_time = ?, last_checked = CURRENT_TIMESTAMP 
			  WHERE id = ?`
	_, err := m.db.Exec(query, isWorking, responseTime, proxyID)
	return err
}

// CheckAllProxies checks all proxies for all users (background task)
func (m *Manager) CheckAllProxies() error {
	query := `SELECT id, user_id, proxy_url, proxy_type, username, password, 
			  is_active, last_checked, is_working, response_time, created_at 
			  FROM proxies WHERE is_active = 1`
	
	rows, err := m.db.Query(query)
	if err != nil {
		return err
	}
	defer rows.Close()
	
	for rows.Next() {
		proxy := &Proxy{}
		var lastChecked, createdAt sql.NullTime
		
		err := rows.Scan(
			&proxy.ID, &proxy.UserID, &proxy.ProxyURL, &proxy.ProxyType,
			&proxy.Username, &proxy.Password, &proxy.IsActive,
			&lastChecked, &proxy.IsWorking, &proxy.ResponseTime, &createdAt,
		)
		if err != nil {
			continue
		}
		
		if lastChecked.Valid {
			proxy.LastChecked = lastChecked.Time
		}
		if createdAt.Valid {
			proxy.CreatedAt = createdAt.Time
		}
		
		// Check proxy
		isWorking, responseTime := m.CheckProxy(proxy)
		
		// Update status
		m.UpdateProxyStatus(proxy.ID, isWorking, responseTime)
	}
	
	return nil
}

// ParseProxyList parses a list of proxies from text for a specific user
func (m *Manager) ParseProxyList(userID int64, proxyText string) error {
	return m.ParseProxyListWithLimit(userID, proxyText, 999999) // No limit by default
}

// ParseProxyListWithLimit parses a list of proxies from text for a specific user with a limit
func (m *Manager) ParseProxyListWithLimit(userID int64, proxyText string, maxProxies int) error {
	// Get current proxy count
	currentCount, err := m.GetUserProxyCount(userID)
	if err != nil {
		return fmt.Errorf("failed to check proxy count: %v", err)
	}
	
	if currentCount >= maxProxies {
		return fmt.Errorf("proxy limit reached (%d/%d). Delete some proxies first", currentCount, maxProxies)
	}
	
	lines := strings.Split(proxyText, "\n")
	addedCount := 0
	
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		
		// Check if we've reached the limit
		if currentCount+addedCount >= maxProxies {
			return fmt.Errorf("proxy limit reached (%d/%d). Only added %d proxies", maxProxies, maxProxies, addedCount)
		}
		
		// Parse proxy format: ip:port or ip:port:username:password
		parts := strings.Split(line, ":")
		if len(parts) < 2 {
			continue
		}
		
		proxyURL := fmt.Sprintf("%s:%s", parts[0], parts[1])
		username := ""
		password := ""
		
		if len(parts) >= 4 {
			username = parts[2]
			password = parts[3]
		}
		
		// Add proxy for this specific user
		err := m.AddProxy(userID, proxyURL, "http", username, password)
		if err != nil {
			// Continue with other proxies if one fails
			continue
		}
		addedCount++
	}
	
	return nil
}

// GetProxyStats returns proxy statistics for a specific user
func (m *Manager) GetProxyStats(userID int64) (map[string]int, error) {
	stats := make(map[string]int)
	
	var total, working, active int
	
	// Total proxies for this user
	query := `SELECT COUNT(*) FROM proxies WHERE user_id = ?`
	err := m.db.QueryRow(query, userID).Scan(&total)
	if err != nil {
		return nil, err
	}
	stats["total"] = total
	
	// Working proxies for this user
	query = `SELECT COUNT(*) FROM proxies WHERE user_id = ? AND is_working = 1 AND is_active = 1`
	err = m.db.QueryRow(query, userID).Scan(&working)
	if err != nil {
		return nil, err
	}
	stats["working"] = working
	
	// Active proxies for this user
	query = `SELECT COUNT(*) FROM proxies WHERE user_id = ? AND is_active = 1`
	err = m.db.QueryRow(query, userID).Scan(&active)
	if err != nil {
		return nil, err
	}
	stats["active"] = active
	
	return stats, nil
}

// GetProxyByID returns a specific proxy if it belongs to the user
func (m *Manager) GetProxyByID(userID int64, proxyID int) (*Proxy, error) {
	query := `SELECT id, user_id, proxy_url, proxy_type, username, password, 
			  is_active, last_checked, is_working, response_time, created_at 
			  FROM proxies WHERE id = ? AND user_id = ?`
	
	proxy := &Proxy{}
	var lastChecked, createdAt sql.NullTime
	
	err := m.db.QueryRow(query, proxyID, userID).Scan(
		&proxy.ID, &proxy.UserID, &proxy.ProxyURL, &proxy.ProxyType,
		&proxy.Username, &proxy.Password, &proxy.IsActive,
		&lastChecked, &proxy.IsWorking, &proxy.ResponseTime, &createdAt,
	)
	
	if err != nil {
		return nil, err
	}
	
	if lastChecked.Valid {
		proxy.LastChecked = lastChecked.Time
	}
	if createdAt.Valid {
		proxy.CreatedAt = createdAt.Time
	}
	
	return proxy, nil
}

// StartBackgroundChecker starts the background proxy checker (runs every 5 minutes)
func (m *Manager) StartBackgroundChecker() {
	ticker := time.NewTicker(5 * time.Minute)
	go func() {
		for range ticker.C {
			m.CheckAllProxies()
		}
	}()
}

// CheckUserProxies checks all proxies for a specific user
func (m *Manager) CheckUserProxies(userID int64) error {
	proxies, err := m.GetUserProxies(userID)
	if err != nil {
		return err
	}
	
	for _, proxy := range proxies {
		if !proxy.IsActive {
			continue
		}
		
		// Check proxy
		isWorking, responseTime := m.CheckProxy(proxy)
		
		// Update status
		m.UpdateProxyStatus(proxy.ID, isWorking, responseTime)
	}
	
	return nil
}

// StartValidationService starts the background proxy validation service
func (m *Manager) StartValidationService() {
	ticker := time.NewTicker(5 * time.Minute)
	defer ticker.Stop()
	
	log.Println("🔄 Proxy validation service started (checking every 5 minutes)")
	
	for {
		select {
		case <-ticker.C:
			log.Println("🔍 Running proxy validation check...")
			
			// Get all active proxies from all users
			query := `SELECT id, user_id, proxy_url, proxy_type, username, password 
					  FROM proxies WHERE is_active = 1`
			
			rows, err := m.db.Query(query)
			if err != nil {
				log.Printf("❌ Error querying proxies for validation: %v", err)
				continue
			}
			
			var proxiesToCheck []*Proxy
			for rows.Next() {
				proxy := &Proxy{}
				var username, password sql.NullString
				
				err := rows.Scan(&proxy.ID, &proxy.UserID, &proxy.ProxyURL, 
								&proxy.ProxyType, &username, &password)
				if err != nil {
					log.Printf("❌ Error scanning proxy: %v", err)
					continue
				}
				
				if username.Valid {
					proxy.Username = username.String
				}
				if password.Valid {
					proxy.Password = password.String
				}
				
				proxiesToCheck = append(proxiesToCheck, proxy)
			}
			rows.Close()
			
			if len(proxiesToCheck) == 0 {
				log.Println("ℹ️ No active proxies to validate")
				continue
			}
			
			log.Printf("🔍 Validating %d proxies...", len(proxiesToCheck))
			
			// Check proxies in batches to avoid overwhelming the system
			batchSize := 50
			for i := 0; i < len(proxiesToCheck); i += batchSize {
				end := i + batchSize
				if end > len(proxiesToCheck) {
					end = len(proxiesToCheck)
				}
				
				batch := proxiesToCheck[i:end]
				m.validateProxyBatch(batch)
				
				// Small delay between batches
				time.Sleep(1 * time.Second)
			}
			
			log.Println("✅ Proxy validation completed")
		}
	}
}

func (m *Manager) validateProxyBatch(proxies []*Proxy) {
	var wg sync.WaitGroup
	
	for _, proxy := range proxies {
		wg.Add(1)
		go func(p *Proxy) {
			defer wg.Done()
			
			// Test proxy
			isWorking, responseTime := m.CheckProxy(p)
			
			// Update status
			m.UpdateProxyStatus(p.ID, isWorking, responseTime)
		}(proxy)
	}
	
	wg.Wait()
}

// GetActiveProxies returns all active and working proxies for a user
func (m *Manager) GetActiveProxies(userID int64) ([]*Proxy, error) {
	query := `SELECT id, user_id, proxy_url, proxy_type, username, password, 
			  is_active, last_checked, is_working, response_time, created_at 
			  FROM proxies WHERE user_id = ? AND is_active = 1 AND is_working = 1`
	
	rows, err := m.db.Query(query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	
	var proxies []*Proxy
	for rows.Next() {
		proxy := &Proxy{}
		var lastChecked, createdAt sql.NullTime
		var username, password sql.NullString
		
		err := rows.Scan(
			&proxy.ID, &proxy.UserID, &proxy.ProxyURL, &proxy.ProxyType,
			&username, &password, &proxy.IsActive,
			&lastChecked, &proxy.IsWorking, &proxy.ResponseTime, &createdAt,
		)
		
		if err != nil {
			return nil, err
		}
		
		if username.Valid {
			proxy.Username = username.String
		}
		if password.Valid {
			proxy.Password = password.String
		}
		if lastChecked.Valid {
			proxy.LastChecked = lastChecked.Time
		}
		if createdAt.Valid {
			proxy.CreatedAt = createdAt.Time
		}
		
		proxies = append(proxies, proxy)
	}
	
	return proxies, nil
}