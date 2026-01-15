package search

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"toolbot/modules/database"
	"toolbot/modules/user"
)

type SearchResult struct {
	Domain        string   `json:"domain"`
	EmailCount    int      `json:"email_count"`
	ComboCount    int      `json:"combo_count"`
	PasswordCount int      `json:"password_count"`
	Emails        []string `json:"emails,omitempty"`
	Combos        []string `json:"combos,omitempty"`
	Passwords     []string `json:"passwords,omitempty"`
}

type DownloadRequest struct {
	UserID int64  `json:"user_id"`
	Domain string `json:"domain"`
	Type   string `json:"type"` // emails, combos, passwords
	Count  int    `json:"count"`
	Format string `json:"format"` // txt, csv
}

type Manager struct {
	db          *database.Database
	userManager *user.Manager
}

func NewManager(db *database.Database, userManager *user.Manager) *Manager {
	return &Manager{
		db:          db,
		userManager: userManager,
	}
}

func (m *Manager) SearchDomain(userID int64, domain string) (*SearchResult, error) {
	return m.SearchDomainWithLimit(userID, domain, 0)
}

func (m *Manager) SearchDomainWithLimit(userID int64, domain string, limit int) (*SearchResult, error) {
	canSearch, err := m.userManager.CanSearch(userID)
	if err != nil {
		return nil, err
	}
	if !canSearch {
		return nil, fmt.Errorf("search limit reached or user is banned")
	}

	if err := m.userManager.IncrementSearchCount(userID); err != nil {
		return nil, err
	}

	result := &SearchResult{
		Domain: domain,
	}

	emailCount, err := m.db.CountEmailsWithLimit(domain, limit)
	if err != nil {
		return nil, err
	}
	result.EmailCount = emailCount

	comboCount, err := m.db.CountCombosWithLimit(domain, limit)
	if err != nil {
		return nil, err
	}
	result.ComboCount = comboCount

	passwordCount, err := m.db.CountPasswordsWithLimit(limit)
	if err != nil {
		return nil, err
	}
	result.PasswordCount = passwordCount

	return result, nil
}

// GenerateDownload is now optimized with Buffered I/O for high-speed file creation
func (m *Manager) GenerateDownload(req *DownloadRequest) (string, error) {
	tmpDir := filepath.Join("tmp", fmt.Sprintf("user_%d", req.UserID))
	if err := os.MkdirAll(tmpDir, 0755); err != nil {
		return "", err
	}

	countStr := formatCountForFilename(req.Count)
	cleanDomain := strings.TrimPrefix(req.Domain, "@")
	if idx := strings.Index(cleanDomain, "."); idx > 0 {
		cleanDomain = cleanDomain[:idx]
	}
	
	filename := filepath.Join(tmpDir, fmt.Sprintf("%s-%s.txt", countStr, cleanDomain))

	// 1. Fetch data from DB
	var data []string
	var err error

	switch req.Type {
	case "emails":
		data, err = m.db.SearchEmails(req.Domain, req.Count)
	case "combos":
		data, err = m.db.SearchCombos(req.Domain, req.Count)
	case "passwords":
		data, err = m.db.GetRandomPasswords(req.Count)
	default:
		return "", fmt.Errorf("invalid download type: %s", req.Type)
	}

	if err != nil {
		return "", err
	}

	// 2. High-speed write using bufio
	file, err := os.Create(filename)
	if err != nil {
		return "", err
	}
	
	// Create a buffered writer (defaults to 4KB buffer, significantly reducing syscalls)
	writer := bufio.NewWriter(file)

	for _, line := range data {
		// We use writer.WriteString which is much faster than file.WriteString in a loop
		if _, err := writer.WriteString(line + "\n"); err != nil {
			file.Close()
			return "", err
		}
	}

	// IMPORTANT: Flush ensures all buffered data is actually pushed to the file disk
	if err := writer.Flush(); err != nil {
		file.Close()
		return "", err
	}

	// Close file handle
	if err := file.Close(); err != nil {
		return "", err
	}

	return filename, nil
}

func formatCountForFilename(count int) string {
	if count >= 1000000 {
		if count%1000000 == 0 {
			return fmt.Sprintf("%dm", count/1000000)
		}
		return fmt.Sprintf("%.1fm", float64(count)/1000000)
	} else if count >= 1000 {
		if count%1000 == 0 {
			return fmt.Sprintf("%dk", count/1000)
		}
		return fmt.Sprintf("%.1fk", float64(count)/1000)
	}
	return fmt.Sprintf("%d", count)
}

func (m *Manager) GetPopularDomains() ([]string, error) {
	return []string{
		"@gmail.com", "@yahoo.com", "@hotmail.com", "@outlook.com",
		"@aol.com", "@icloud.com", "@live.com", "@msn.com",
		"@comcast.net", "@verizon.net",
	}, nil
}

func (m *Manager) ValidateDomain(domain string) error {
	if domain == "" {
		return fmt.Errorf("domain cannot be empty")
	}
	if !strings.HasPrefix(domain, "@") {
		return fmt.Errorf("domain must start with @")
	}
	if len(domain) < 4 {
		return fmt.Errorf("domain too short")
	}
	if !strings.Contains(domain[1:], ".") {
		return fmt.Errorf("invalid domain format")
	}
	return nil
}

func (m *Manager) GetUserDownloadHistory(userID int64) ([]string, error) {
	tmpDir := filepath.Join("tmp", fmt.Sprintf("user_%d", userID))
	files, err := os.ReadDir(tmpDir)
	if err != nil {
		if os.IsNotExist(err) {
			return []string{}, nil
		}
		return nil, err
	}

	var history []string
	for _, file := range files {
		if !file.IsDir() && strings.HasSuffix(file.Name(), ".txt") {
			history = append(history, file.Name())
		}
	}
	return history, nil
}

func (m *Manager) CleanupUserFiles(userID int64, olderThan time.Duration) error {
	tmpDir := filepath.Join("tmp", fmt.Sprintf("user_%d", userID))
	files, err := os.ReadDir(tmpDir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return err
	}

	cutoff := time.Now().Add(-olderThan)
	for _, file := range files {
		if file.IsDir() {
			continue
		}
		info, err := file.Info()
		if err != nil {
			continue
		}
		if info.ModTime().Before(cutoff) {
			os.Remove(filepath.Join(tmpDir, file.Name()))
		}
	}
	return nil
}

func (m *Manager) GetFileSize(filePath string) (int64, error) {
	info, err := os.Stat(filePath)
	if err != nil {
		return 0, err
	}
	return info.Size(), nil
}

func (m *Manager) DeleteFile(filePath string) error {
	return os.Remove(filePath)
}

func FormatFileSize(bytes int64) string {
	const unit = 1024
	if bytes < unit {
		return fmt.Sprintf("%d B", bytes)
	}
	div, exp := int64(unit), 0
	for n := bytes / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(bytes)/float64(div), "KMGTPE"[exp])
}

func GetFileExtension(downloadType string) string {
	switch downloadType {
	case "emails":
		return "emails.txt"
	case "combos":
		return "combos.txt"
	case "passwords":
		return "passwords.txt"
	case "generated_combos":
		return "generated_combos.txt"
	default:
		return "data.txt"
	}
}
