package manager

import (
	"bufio"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"xbox-checker/internal/checker"
	"xbox-checker/internal/filewriter"
	"xbox-checker/internal/logger"
	"xbox-checker/internal/proxy"
	"xbox-checker/internal/stats"
	"xbox-checker/pkg/types"
)

// XBOXCheckerManager manages high-speed concurrent checking
type XBOXCheckerManager struct {
	progressFile string
	proxyManager *proxy.Manager
}

// New creates a new manager
func New() *XBOXCheckerManager {
	return &XBOXCheckerManager{
		progressFile: "progress.txt",
		proxyManager: proxy.NewManager("v.txt", "line.txt"),
	}
}

// loadProgress loads last processed line number
func (m *XBOXCheckerManager) loadProgress() int {
	data, err := os.ReadFile(m.progressFile)
	if err != nil {
		return 0
	}
	
	content := strings.TrimSpace(string(data))
	if content == "" {
		return 0
	}
	
	if num, err := strconv.Atoi(content); err == nil {
		return num
	}
	
	return 0
}

// saveProgress saves current line number
func (m *XBOXCheckerManager) saveProgress(lineNum int) {
	os.WriteFile(m.progressFile, []byte(strconv.Itoa(lineNum)), 0644)
}

// resetProgress resets progress file
func (m *XBOXCheckerManager) resetProgress() {
	os.WriteFile(m.progressFile, []byte("0"), 0644)
}

// countCombos counts total valid combos in file without loading into memory
func (m *XBOXCheckerManager) countCombos(filename string) int {
	file, err := os.Open(filename)
	if err != nil {
		logger.GlobalLogger.LogBoth(fmt.Sprintf("❌ File not found: %s", filename))
		return 0
	}
	defer file.Close()
	
	count := 0
	scanner := bufio.NewScanner(file)
	// Use smaller buffer for counting
	buf := make([]byte, 64*1024)
	scanner.Buffer(buf, 64*1024)
	
	for scanner.Scan() {
		lineBytes := scanner.Bytes()
		// Quick validation without string conversion
		if len(lineBytes) > 0 {
			// Trim whitespace in-place
			start, end := 0, len(lineBytes)
			for start < end && (lineBytes[start] == ' ' || lineBytes[start] == '\t') {
				start++
			}
			for end > start && (lineBytes[end-1] == ' ' || lineBytes[end-1] == '\t' || lineBytes[end-1] == '\r') {
				end--
			}
			// Check for colon without string conversion
			if end > start {
				for i := start; i < end; i++ {
					if lineBytes[i] == ':' {
						count++
						break
					}
				}
			}
		}
	}
	
	return count
}

// loadBatchCombos loads a specific batch of combos from file (streaming approach)
func (m *XBOXCheckerManager) loadBatchCombos(filename string, startLine, batchSize int) []types.AccountCombo {
	file, err := os.Open(filename)
	if err != nil {
		logger.GlobalLogger.LogBoth(fmt.Sprintf("❌ File not found: %s", filename))
		return nil
	}
	defer file.Close()
	
	// Pre-allocate exact size to prevent slice growth
	combos := make([]types.AccountCombo, 0, batchSize)
	
	scanner := bufio.NewScanner(file)
	// Use optimized buffer size to reduce allocations
	buf := make([]byte, 8*1024) // Pre-allocate buffer
	scanner.Buffer(buf, 128*1024)
	
	lineNum := 1
	validLineNum := 0
	
	for scanner.Scan() {
		lineBytes := scanner.Bytes()
		if len(lineBytes) == 0 {
			lineNum++
			continue
		}
		
		// Trim whitespace in-place on bytes
		start, end := 0, len(lineBytes)
		for start < end && (lineBytes[start] == ' ' || lineBytes[start] == '\t') {
			start++
		}
		for end > start && (lineBytes[end-1] == ' ' || lineBytes[end-1] == '\t' || lineBytes[end-1] == '\r') {
			end--
		}
		
		// Quick check for colon without string conversion
		colonIndex := -1
		for i := start; i < end; i++ {
			if lineBytes[i] == ':' {
				colonIndex = i
				break
			}
		}
		if colonIndex == -1 {
			lineNum++
			continue
		}
		
		validLineNum++
		
		// Skip lines until we reach the start of this batch
		if validLineNum < startLine {
			lineNum++
			continue
		}
		
		// Stop if we've loaded enough for this batch
		if len(combos) >= batchSize {
			break
		}
		
		// Manual split on bytes to avoid string allocation
		emailBytes := lineBytes[start:colonIndex]
		passwordBytes := lineBytes[colonIndex+1:end]
		
		// Trim email bytes
		emailStart, emailEnd := 0, len(emailBytes)
		for emailStart < emailEnd && (emailBytes[emailStart] == ' ' || emailBytes[emailStart] == '\t') {
			emailStart++
		}
		for emailEnd > emailStart && (emailBytes[emailEnd-1] == ' ' || emailBytes[emailEnd-1] == '\t') {
			emailEnd--
		}
		
		// Trim password bytes
		passwordStart, passwordEnd := 0, len(passwordBytes)
		for passwordStart < passwordEnd && (passwordBytes[passwordStart] == ' ' || passwordBytes[passwordStart] == '\t') {
			passwordStart++
		}
		for passwordEnd > passwordStart && (passwordBytes[passwordEnd-1] == ' ' || passwordBytes[passwordEnd-1] == '\t') {
			passwordEnd--
		}
		
		// Convert to strings only when needed
		email := string(emailBytes[emailStart:emailEnd])
		password := string(passwordBytes[passwordStart:passwordEnd])
		
		combos = append(combos, types.AccountCombo{
			Email:    email,
			Password: password,
			LineNum:  lineNum,
		})
		
		lineNum++
	}
	
	if err := scanner.Err(); err != nil {
		logger.GlobalLogger.LogBoth(fmt.Sprintf("❌ Error reading file: %v", err))
		return nil
	}
	
	return combos
}

// createBatches splits combos into optimized batches
func (m *XBOXCheckerManager) createBatches(combos []types.AccountCombo, batchSize int) [][]types.AccountCombo {
	if len(combos) == 0 {
		return nil
	}
	
	// Pre-calculate number of batches to avoid slice reallocations
	numBatches := (len(combos) + batchSize - 1) / batchSize
	batches := make([][]types.AccountCombo, 0, numBatches)
	
	for i := 0; i < len(combos); i += batchSize {
		end := i + batchSize
		if end > len(combos) {
			end = len(combos)
		}
		batches = append(batches, combos[i:end])
	}
	
	return batches
}

// checkSingleAccount is the worker function for checking a single account
func checkSingleAccount(email, password string, threadID int, proxyManager *proxy.Manager) (string, string, types.CheckResult, *types.CapturedData, string) {
	checker := checker.New(threadID, proxyManager)
	defer checker.Close() // Ensure resources are cleaned up
	
	result, capturedData := checker.CheckAccount(email, password)
	
	// Get proxy info for logging
	proxyInfo := "No Proxy"
	if currentProxy := checker.GetCurrentProxy(); currentProxy != nil {
		proxyURL := currentProxy.HTTP
		if proxyURL != "" {
			// Extract just the IP:PORT part for cleaner logging
			if strings.Contains(proxyURL, "@") {
				parts := strings.Split(proxyURL, "@")
				if len(parts) > 1 {
					proxyInfo = parts[1]
				}
			} else {
				proxyInfo = strings.Replace(proxyURL, "http://", "", 1)
				proxyInfo = strings.Replace(proxyInfo, "https://", "", 1)
			}
		}
	}
	
	return email, password, result, capturedData, proxyInfo
}

// Define result struct outside function to avoid repeated allocations
type batchResult struct {
	email, password string
	result          types.CheckResult
	capturedData    *types.CapturedData
	proxyInfo       string
	lineNum         int
}

// processBatch processes a single batch of accounts
func (m *XBOXCheckerManager) processBatch(batch []types.AccountCombo, batchNum, totalBatches int, stats *stats.ThreadSafeStats, fileWriter *filewriter.ThreadSafeFileWriter, maxWorkers int, targetCPM int) int {
	maxLineNum := 0
	batchSize := len(batch)
	
	// Pre-allocate channels with exact capacity to prevent growth
	jobs := make(chan types.AccountCombo, batchSize)
	results := make(chan batchResult, batchSize)
	
	// Calculate delay between requests for CPM throttling
	var requestDelay time.Duration
	if targetCPM > 0 {
		// CPM = Checks Per Minute, so delay = 60 seconds / targetCPM
		requestDelay = time.Duration(60000/targetCPM) * time.Millisecond
	}
	
	// Use a WaitGroup to ensure all workers complete
	var workerWG sync.WaitGroup
	
	// Start workers
	for w := 0; w < maxWorkers; w++ {
		workerWG.Add(1)
		go func(workerID int) {
			defer workerWG.Done()
			// Pre-allocate result struct to reuse
			var result batchResult
			
			for combo := range jobs {
				// Apply CPM throttling if configured
				if requestDelay > 0 {
					time.Sleep(requestDelay)
				}
				
				email, password, checkResult, capturedData, proxyInfo := checkSingleAccount(combo.Email, combo.Password, workerID, m.proxyManager)
				
				// Reuse result struct to avoid allocation
				result.email = email
				result.password = password
				result.result = checkResult
				result.capturedData = capturedData
				result.proxyInfo = proxyInfo
				result.lineNum = combo.LineNum
				
				results <- result
			}
		}(w)
	}
	
	// Send jobs
	for i := range batch {
		jobs <- batch[i]
	}
	close(jobs)
	
	// Wait for all workers to complete
	go func() {
		workerWG.Wait()
		close(results)
	}()
	
	// Collect results
	for result := range results {
		if result.lineNum > maxLineNum {
			maxLineNum = result.lineNum
		}
		
		stats.Increment(result.result)
		
		if result.result == types.SUCCESS {
			fileWriter.WriteValid(result.email, result.password, result.capturedData)
			logger.GlobalLogger.LogBoth(fmt.Sprintf("✅ Valid [%s] - %s", result.email, result.proxyInfo))
		}
	}
	
	return maxLineNum
}

// RunBatchChecker runs the ultra-high-speed batch checker with streaming
func (m *XBOXCheckerManager) RunBatchChecker(combosFile, validFile string, maxWorkers, targetCPM, batchSize int, resetProgress bool) {
	if resetProgress {
		m.resetProgress()
	}
	
	startLine := m.loadProgress()
	totalCombos := m.countCombos(combosFile)
	
	if totalCombos == 0 {
		logger.GlobalLogger.LogBoth("❌ No combos found. Exiting.")
		return
	}
	
	// Calculate remaining combos and adjust start position
	remainingCombos := totalCombos
	currentStartLine := 1
	if startLine > 0 {
		currentStartLine = startLine + 1
		remainingCombos = totalCombos - startLine
		logger.GlobalLogger.LogBoth(fmt.Sprintf("🔄 Resuming from line %d, %d combos remaining", startLine, remainingCombos))
	}
	
	if batchSize == 0 {
		batchSize = int(math.Max(500, math.Min(2000, float64(remainingCombos)/100)))
	}
	
	totalBatches := int(math.Ceil(float64(remainingCombos) / float64(batchSize)))
	statsTracker := stats.New()
	fileWriter := filewriter.New(validFile)
	defer fileWriter.Close() // Ensure file is properly closed
	
	workingProxies, _ := m.proxyManager.GetProxyCount()
	
	logger.GlobalLogger.LogBoth("\n🚀 Xbox Account Checker - BATCH MODE (Ultra High Speed)")
	logger.GlobalLogger.LogBoth(fmt.Sprintf("📊 Target CPM: %d", targetCPM))
	logger.GlobalLogger.LogBoth(fmt.Sprintf("🔧 Max Workers: %d", maxWorkers))
	logger.GlobalLogger.LogBoth(fmt.Sprintf("📦 Batch Size: %d", batchSize))
	logger.GlobalLogger.LogBoth(fmt.Sprintf("📡 Proxies loaded: %d working", workingProxies))
	logger.GlobalLogger.LogBoth(fmt.Sprintf("📁 Combos file: %s", combosFile))
	logger.GlobalLogger.LogBoth(fmt.Sprintf("💾 Valid file: %s", validFile))
	logger.GlobalLogger.LogBoth(fmt.Sprintf("📈 Total accounts to check: %d", remainingCombos))
	logger.GlobalLogger.LogBoth(fmt.Sprintf("📦 Total batches: %d", totalBatches))
	if startLine > 0 {
		logger.GlobalLogger.LogBoth(fmt.Sprintf("🔄 Resuming from line: %d", startLine))
	}
	logger.GlobalLogger.LogBoth("📊 Statistics display interval: 60 seconds")
	logger.GlobalLogger.LogBoth(strings.Repeat("=", 60))
	
	// Progress display goroutine
	stopProgress := make(chan bool)
	go func() {
		// Wait 60 seconds before first display, but check for stop signal
		select {
		case <-stopProgress:
			return
		case <-time.After(60 * time.Second):
		}
		
		ticker := time.NewTicker(60 * time.Second)
		defer ticker.Stop()
		
		for {
			select {
			case <-stopProgress:
				return
			case <-ticker.C:
				currentStats := statsTracker.GetStats()
				progressPercent := 0.0
				if remainingCombos > 0 {
					progressPercent = math.Round((float64(currentStats["total"].(int64))/float64(remainingCombos))*100*10) / 10
				}
				logger.GlobalLogger.LogBoth(fmt.Sprintf("\n[🔨CPM: %.1f] 💰Checked: %d | ✅ Valid: %d | 🔒Custom: %d | 🧑🏽‍💻Progress: %.1f%%",
					currentStats["cpm"].(float64), currentStats["total"].(int64), currentStats["valid"].(int64),
					currentStats["custom"].(int64), progressPercent))
			}
		}
	}()
	
	// Process batches with streaming
	maxLineCompleted := startLine
	for batchNum := 0; batchNum < totalBatches; batchNum++ {
		// Load only this batch into memory
		batchStartLine := currentStartLine + (batchNum * batchSize)
		batch := m.loadBatchCombos(combosFile, batchStartLine, batchSize)
		
		if len(batch) == 0 {
			break // No more combos to process
		}
		
		// Only log batch start for first few batches
		if batchNum < 5 || (batchNum+1)%50 == 0 {
			logger.GlobalLogger.LogBoth(fmt.Sprintf("🔄 Starting batch %d/%d", batchNum+1, totalBatches))
		}
		
		batchMaxLine := m.processBatch(batch, batchNum+1, totalBatches, statsTracker, fileWriter, maxWorkers, targetCPM)
		if batchMaxLine > maxLineCompleted {
			maxLineCompleted = batchMaxLine
		}
		
		// Save progress after every batch
		m.saveProgress(maxLineCompleted)
		
		// Only log batch completion for first few batches or every 50th batch
		if batchNum < 5 || (batchNum+1)%50 == 0 {
			currentStats := statsTracker.GetStats()
			batchProgress := 0.0
			if remainingCombos > 0 {
				batchProgress = math.Round((float64(currentStats["total"].(int64))/float64(remainingCombos))*100*10) / 10
			}
			logger.GlobalLogger.LogBoth(fmt.Sprintf("✅ Batch %d/%d complete - [🔨CPM: %.1f] 🧑🏽‍💻Progress: %.1f%%",
				batchNum+1, totalBatches, currentStats["cpm"].(float64), batchProgress))
		}
	}
	
	// Stop progress display
	stopProgress <- true
	
	finalStats := statsTracker.GetStats()
	logger.GlobalLogger.LogBoth(strings.Repeat("=", 60))
	logger.GlobalLogger.LogBoth("✅ BATCH CHECKING COMPLETED")
	finalProgress := 0.0
	if remainingCombos > 0 {
		finalProgress = math.Round((float64(finalStats["total"].(int64))/float64(remainingCombos))*100*10) / 10
	}
	logger.GlobalLogger.LogBoth(fmt.Sprintf("📊 Final Stats - [🔨CPM: %.1f] 💰Checked: %d | ✅ Valid: %d | 🔒Custom: %d | 🧑🏽‍💻Progress: %.1f%%",
		finalStats["cpm"].(float64), finalStats["total"].(int64), finalStats["valid"].(int64),
		finalStats["custom"].(int64), finalProgress))
	logger.GlobalLogger.LogBoth(strings.Repeat("=", 60))
}