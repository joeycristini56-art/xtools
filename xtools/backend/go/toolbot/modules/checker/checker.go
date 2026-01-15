package checker

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"toolbot/modules/checker/internal/checker"
	"toolbot/modules/checker/internal/filewriter"
	"toolbot/modules/checker/internal/logger"
	"toolbot/modules/checker/internal/proxy"
	"toolbot/modules/checker/internal/stats"
	"toolbot/modules/checker/pkg/types"
	userProxy "toolbot/modules/proxy"
	"toolbot/modules/user"
)

type CheckSession struct {
	UserID     int64     `json:"user_id"`
	SessionID  string    `json:"session_id"`
	InputFile  string    `json:"input_file"`
	OutputFile string    `json:"output_file"`
	Status     string    `json:"status"` // running, completed, failed, cancelled
	Progress   int       `json:"progress"`
	Total      int       `json:"total"`
	Valid      int       `json:"valid"`
	Invalid    int       `json:"invalid"`
	Custom     int       `json:"custom"`
	Failed     int       `json:"failed"`
	CPM        float64   `json:"cpm"`
	StartTime  time.Time `json:"start_time"`
	EndTime    time.Time `json:"end_time"`
	LastUpdate time.Time `json:"last_update"`
	Config     *Config   `json:"config"`
	manager    *XBOXCheckerManager
}

type Config struct {
	MaxWorkers    int  `json:"max_workers"`
	TargetCPM     int  `json:"target_cpm"`
	BatchSize     int  `json:"batch_size"`
	UseUserProxy  bool `json:"use_user_proxy"`
	ResetProgress bool `json:"reset_progress"`
}

type Manager struct {
	userManager  *user.Manager
	proxyManager *userProxy.Manager
	sessions     map[string]*CheckSession
	sessionMutex sync.RWMutex
	getGlobalSettings func() *Config // Function to get global settings
}

// XBOXCheckerManager wraps the original manager for our use
type XBOXCheckerManager struct {
	proxyManager *proxy.Manager
	fileWriter   *filewriter.ThreadSafeFileWriter
	stats        *stats.ThreadSafeStats
	logger       *logger.Logger
	stopChan     chan bool
	session      *CheckSession
	userProxies  []*userProxy.Proxy
}

// CheckStats represents checking statistics for progress updates
type CheckStats struct {
	Total                    int
	Checked                  int
	Valid                    int
	Invalid                  int
	Errors                   int
	CPM                      float64
	ActiveThreads            int
	ElapsedTime              time.Duration
	EstimatedTimeRemaining   time.Duration
}

// GetStats returns current session statistics
func (s *CheckSession) GetStats() *CheckStats {
	elapsed := time.Since(s.StartTime)
	var eta time.Duration
	if s.Progress > 0 && s.CPM > 0 {
		remaining := s.Total - s.Progress
		eta = time.Duration(float64(remaining)/s.CPM) * time.Minute
	}
	
	activeThreads := 0
	if s.manager != nil {
		activeThreads = s.Config.MaxWorkers
	}
	
	return &CheckStats{
		Total:                  s.Total,
		Checked:                s.Progress,
		Valid:                  s.Valid,
		Invalid:                s.Invalid,
		Errors:                 s.Failed,
		CPM:                    s.CPM,
		ActiveThreads:          activeThreads,
		ElapsedTime:            elapsed,
		EstimatedTimeRemaining: eta,
	}
}

func NewManager(userManager *user.Manager, proxyManager *userProxy.Manager, getGlobalSettings func() *Config) *Manager {
	return &Manager{
		userManager:       userManager,
		proxyManager:      proxyManager,
		sessions:          make(map[string]*CheckSession),
		getGlobalSettings: getGlobalSettings,
	}
}

// GetGlobalSettings returns the current global checker settings
func (m *Manager) GetGlobalSettings() *Config {
	if m.getGlobalSettings != nil {
		return m.getGlobalSettings()
	}
	// Return default settings if no global settings function is provided
	return &Config{
		MaxWorkers:   100,
		TargetCPM:    1000,
		BatchSize:    50,
		UseUserProxy: true,
	}
}

func (m *Manager) CreateSession(userID int64, combos []string, config *Config) (*CheckSession, error) {
	// Check if user can use the checker
	user, err := m.userManager.GetUser(userID)
	if err != nil {
		return nil, err
	}

	if user.IsBanned {
		return nil, fmt.Errorf("user is banned")
	}

	// Generate session ID
	sessionID := fmt.Sprintf("%d_%d", userID, time.Now().Unix())

	// Create user session directory
	sessionDir := filepath.Join("tmp", fmt.Sprintf("user_%d", userID), "sessions", sessionID)
	if err := os.MkdirAll(sessionDir, 0755); err != nil {
		return nil, err
	}

	// Create input file
	inputFile := filepath.Join(sessionDir, "combos.txt")
	if err := m.writeComboFile(inputFile, combos); err != nil {
		return nil, err
	}

	// Create output file path
	outputFile := filepath.Join(sessionDir, "valid.txt")

	session := &CheckSession{
		UserID:     userID,
		SessionID:  sessionID,
		InputFile:  inputFile,
		OutputFile: outputFile,
		Status:     "created",
		Total:      len(combos),
		StartTime:  time.Now(),
		Config:     config,
	}

	m.sessionMutex.Lock()
	m.sessions[sessionID] = session
	m.sessionMutex.Unlock()

	return session, nil
}

func (m *Manager) StartSession(sessionID string) error {
	m.sessionMutex.Lock()
	session, exists := m.sessions[sessionID]
	if !exists {
		m.sessionMutex.Unlock()
		return fmt.Errorf("session not found")
	}

	if session.Status != "created" {
		m.sessionMutex.Unlock()
		return fmt.Errorf("session already started or completed")
	}

	session.Status = "running"
	session.StartTime = time.Now()
	m.sessionMutex.Unlock()

	// Start checking in a goroutine
	go m.runChecker(session)

	return nil
}

func (m *Manager) GetSession(sessionID string) (*CheckSession, error) {
	m.sessionMutex.RLock()
	session, exists := m.sessions[sessionID]
	m.sessionMutex.RUnlock()

	if !exists {
		return nil, fmt.Errorf("session not found")
	}

	return session, nil
}

func (m *Manager) GetUserSessions(userID int64) ([]*CheckSession, error) {
	m.sessionMutex.RLock()
	defer m.sessionMutex.RUnlock()

	var userSessions []*CheckSession
	for _, session := range m.sessions {
		if session.UserID == userID {
			userSessions = append(userSessions, session)
		}
	}

	return userSessions, nil
}

func (m *Manager) CancelSession(sessionID string, userID int64) error {
	m.sessionMutex.Lock()
	session, exists := m.sessions[sessionID]
	if !exists {
		m.sessionMutex.Unlock()
		return fmt.Errorf("session not found")
	}

	if session.UserID != userID {
		m.sessionMutex.Unlock()
		return fmt.Errorf("unauthorized")
	}

	if session.Status == "running" {
		session.Status = "cancelled"
		session.EndTime = time.Now()

		// Stop the checker manager
		if session.manager != nil {
			session.manager.Stop()
		}
	}
	m.sessionMutex.Unlock()

	return nil
}

func (m *Manager) writeComboFile(filename string, combos []string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	for _, combo := range combos {
		if _, err := file.WriteString(combo + "\n"); err != nil {
			return err
		}
	}

	return nil
}

func (m *Manager) runChecker(session *CheckSession) {
	defer func() {
		session.EndTime = time.Now()
		if session.Status == "running" {
			session.Status = "completed"
		}
	}()

	// Get user proxies if configured
	var userProxies []*userProxy.Proxy
	if session.Config.UseUserProxy {
		proxies, err := m.proxyManager.GetActiveProxies(session.UserID)
		if err == nil {
			userProxies = proxies
		}
	}

	// Create Xbox checker manager
	checkerManager := m.createCheckerManager(session, userProxies)
	session.manager = checkerManager

	// Start the checking process
	checkerManager.StartChecking()
}

func (m *Manager) createCheckerManager(session *CheckSession, userProxies []*userProxy.Proxy) *XBOXCheckerManager {
	// Create logger for this session
	sessionLogger := logger.New(fmt.Sprintf("tmp/user_%d/sessions/%s/checker.log", session.UserID, session.SessionID))

	// Create stats tracker
	statsTracker := stats.New()

	// Create file writer for valid accounts
	fileWriter := filewriter.New(session.OutputFile)

	// Create proxy manager and convert user proxies
	proxyMgr := proxy.NewManager("proxies.txt", "proxy_line.txt")
	if len(userProxies) > 0 {
		// Convert user proxies to checker proxy format
		var proxyLines []string
		for _, p := range userProxies {
			// Parse proxy URL to extract address and port
			proxyURL := p.ProxyURL
			// Remove protocol if present
			if strings.Contains(proxyURL, "://") {
				parts := strings.Split(proxyURL, "://")
				if len(parts) > 1 {
					proxyURL = parts[1]
				}
			}
			
			// Handle auth in URL format (user:pass@host:port)
			if strings.Contains(proxyURL, "@") {
				parts := strings.Split(proxyURL, "@")
				if len(parts) == 2 {
					proxyURL = parts[1] // Use host:port part
				}
			}
			
			// Create proxy line
			proxyLine := proxyURL
			if p.Username != "" && p.Password != "" {
				proxyLine = fmt.Sprintf("%s:%s:%s", proxyURL, p.Username, p.Password)
			}
			proxyLines = append(proxyLines, proxyLine)
		}

		// Write proxies to temp file
		proxyFile := filepath.Join(filepath.Dir(session.InputFile), "proxies.txt")
		if err := m.writeProxyFile(proxyFile, proxyLines); err == nil {
			// Proxy manager loads proxies automatically in constructor
			// Create new manager with the proxy file
			proxyMgr = proxy.NewManager(proxyFile, filepath.Join(filepath.Dir(session.InputFile), "proxy_line.txt"))
		}
	}

	return &XBOXCheckerManager{
		proxyManager: proxyMgr,
		fileWriter:   fileWriter,
		stats:        statsTracker,
		logger:       sessionLogger,
		stopChan:     make(chan bool),
		session:      session,
		userProxies:  userProxies,
	}
}

func (m *Manager) writeProxyFile(filename string, proxies []string) error {
	file, err := os.Create(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	for _, proxy := range proxies {
		if _, err := file.WriteString(proxy + "\n"); err != nil {
			return err
		}
	}

	return nil
}

// XBOXCheckerManager methods
func (xcm *XBOXCheckerManager) StartChecking() {
	// Read combos from input file
	combos, err := xcm.readCombos(xcm.session.InputFile)
	if err != nil {
		xcm.session.Status = "failed"
		return
	}

	// Set total count
	xcm.session.Total = len(combos)

	// Configure workers
	maxWorkers := xcm.session.Config.MaxWorkers
	if maxWorkers <= 0 {
		maxWorkers = 100
	}

	// Create worker pool
	jobs := make(chan types.AccountCombo, len(combos))
	results := make(chan CheckResult, len(combos))

	// Start workers
	var wg sync.WaitGroup
	for i := 0; i < maxWorkers; i++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()
			xcm.worker(workerID, jobs, results)
		}(i)
	}

	// Send jobs
	go func() {
		for i, combo := range combos {
			if xcm.session.Status != "running" {
				break
			}

			parts := strings.Split(combo, ":")
			if len(parts) == 2 {
				jobs <- types.AccountCombo{
					Email:    parts[0],
					Password: parts[1],
					LineNum:  i + 1,
				}
			}
		}
		close(jobs)
	}()

	// Collect results
	go func() {
		wg.Wait()
		close(results)
	}()

	// Process results
	startTime := time.Now()
	for result := range results {
		if xcm.session.Status != "running" {
			break
		}

		xcm.session.Progress++
		xcm.session.LastUpdate = time.Now()

		// Calculate CPM
		elapsed := time.Since(startTime).Minutes()
		if elapsed > 0 {
			xcm.session.CPM = float64(xcm.session.Progress) / elapsed
		}

		switch result.Status {
		case "valid":
			xcm.session.Valid++
			xcm.fileWriter.WriteValid(result.Email, result.Password, result.CapturedData)
		case "invalid":
			xcm.session.Invalid++
		case "custom":
			xcm.session.Custom++
		case "failed":
			xcm.session.Failed++
		}
	}
}

func (xcm *XBOXCheckerManager) worker(workerID int, jobs <-chan types.AccountCombo, results chan<- CheckResult) {
	// Create checker instance for this worker
	checkerInstance := checker.New(workerID, xcm.proxyManager)
	if checkerInstance == nil {
		return
	}
	defer checkerInstance.Close()

	for combo := range jobs {
		if xcm.session.Status != "running" {
			break
		}

		// Check the account
		result, capturedData := checkerInstance.CheckAccount(combo.Email, combo.Password)

		// Convert result
		var status string
		switch result {
		case types.SUCCESS:
			status = "valid"
		case types.FAILURE:
			status = "invalid"
		case types.BAN:
			status = "failed"
		case types.CUSTOM:
			status = "custom"
		default:
			status = "failed"
		}

		results <- CheckResult{
			Email:        combo.Email,
			Password:     combo.Password,
			Status:       status,
			CapturedData: capturedData,
		}

		// Rate limiting
		if xcm.session.Config.TargetCPM > 0 {
			delay := time.Minute / time.Duration(xcm.session.Config.TargetCPM)
			time.Sleep(delay)
		}
	}
}

func (xcm *XBOXCheckerManager) Stop() {
	close(xcm.stopChan)
}

func (xcm *XBOXCheckerManager) readCombos(filename string) ([]string, error) {
	file, err := os.Open(filename)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var combos []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" && strings.Contains(line, ":") {
			combos = append(combos, line)
		}
	}

	return combos, scanner.Err()
}

type CheckResult struct {
	Email        string
	Password     string
	Status       string
	CapturedData *types.CapturedData
}

// SessionResult represents a result from a checking session
type SessionResult struct {
	Combo        string
	IsValid      bool
	FullResult   string // Full line with metadata for valid accounts
}

func (m *Manager) GetSessionResults(sessionID string, userID int64) ([]SessionResult, error) {
	session, err := m.GetSession(sessionID)
	if err != nil {
		return nil, err
	}

	if session.UserID != userID {
		return nil, fmt.Errorf("unauthorized")
	}

	if session.Status != "completed" {
		return nil, fmt.Errorf("session not completed")
	}

	// Read valid results from output file (includes metadata)
	validLines, err := m.readComboFile(session.OutputFile)
	if err != nil {
		validLines = []string{} // Empty if file doesn't exist
	}

	// Read original combos from input file
	allCombos, err := m.readComboFile(session.InputFile)
	if err != nil {
		return nil, err
	}

	// Create a map of valid combos with their full result lines
	// The valid.txt format is: email:password | metadata...
	validMap := make(map[string]string) // combo -> full line with metadata
	for _, line := range validLines {
		// Extract the email:password part (before the first " | ")
		combo := line
		if idx := strings.Index(line, " | "); idx > 0 {
			combo = line[:idx]
		}
		validMap[combo] = line // Store full line with metadata
	}

	// Create results
	var results []SessionResult
	for _, combo := range allCombos {
		fullResult, isValid := validMap[combo]
		if isValid {
			results = append(results, SessionResult{
				Combo:      combo,
				IsValid:    true,
				FullResult: fullResult, // Include full metadata
			})
		} else {
			results = append(results, SessionResult{
				Combo:      combo,
				IsValid:    false,
				FullResult: combo, // Just the combo for invalid
			})
		}
	}

	return results, nil
}

func (m *Manager) readComboFile(filename string) ([]string, error) {
	file, err := os.Open(filename)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var lines []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" {
			lines = append(lines, line)
		}
	}

	return lines, scanner.Err()
}

func (m *Manager) CleanupSession(sessionID string) error {
	m.sessionMutex.Lock()
	session, exists := m.sessions[sessionID]
	if !exists {
		m.sessionMutex.Unlock()
		return fmt.Errorf("session not found")
	}

	// Remove from memory
	delete(m.sessions, sessionID)
	m.sessionMutex.Unlock()

	// Clean up files
	sessionDir := filepath.Dir(session.InputFile)
	return os.RemoveAll(sessionDir)
}

func (m *Manager) CleanupOldSessions(olderThan time.Duration) {
	m.sessionMutex.Lock()
	defer m.sessionMutex.Unlock()

	cutoff := time.Now().Add(-olderThan)

	for sessionID, session := range m.sessions {
		if session.EndTime.Before(cutoff) && session.Status != "running" {
			// Clean up files
			sessionDir := filepath.Dir(session.InputFile)
			os.RemoveAll(sessionDir)

			// Remove from memory
			delete(m.sessions, sessionID)
		}
	}
}
