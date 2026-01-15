package proxy

import (
	"bufio"
	"fmt"
	"math"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/ncpmeplmls0614/requests"
	"toolbot/modules/checker/internal/logger"
	"toolbot/modules/checker/pkg/httpclient"
	"toolbot/modules/checker/pkg/types"
)

// Manager manages proxy loading, testing, and rotation
type Manager struct {
	proxyFile      string
	lineFile       string
	workingProxies []types.ProxyWithLine
	failedProxies  []types.ProxyWithLine
	mutex          sync.Mutex
	currentIndex   int
	currentProxy   *types.ProxyConfig
}

// NewManager creates a new proxy manager
func NewManager(proxyFile, lineFile string) *Manager {
	pm := &Manager{
		proxyFile: proxyFile,
		lineFile:  lineFile,
	}
	pm.loadProxies()
	pm.FindNextWorkingProxy()
	return pm
}

// loadProxyLinePosition loads the current proxy line position
func (pm *Manager) loadProxyLinePosition() int {
	data, err := os.ReadFile(pm.lineFile)
	if err != nil {
		return 0
	}

	content := strings.TrimSpace(string(data))
	if content == "" {
		return 0
	}

	lines := strings.Split(content, "\n")
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if num, err := strconv.Atoi(line); err == nil {
			return num
		}
	}

	// Reset to 0 if corrupted, but don't auto-create file
	logger.GlobalLogger.LogBoth("⚠️ Corrupted line.txt file detected, resetting to position 0")
	return 0
}

// saveProxyLinePosition saves the current proxy line position only if proxy file exists
func (pm *Manager) saveProxyLinePosition(lineNum int) {
	// Only save line position if proxy file exists
	if _, err := os.Stat(pm.proxyFile); err == nil {
		os.WriteFile(pm.lineFile, []byte(strconv.Itoa(lineNum)), 0644)
	}
}

// loadProxies loads proxies from file starting from saved position
func (pm *Manager) loadProxies() {
	startLine := pm.loadProxyLinePosition()

	file, err := os.Open(pm.proxyFile)
	if err != nil {
		return // Continue without proxy support
	}
	defer file.Close()

	// First pass: count valid proxies to pre-allocate slice
	scanner := bufio.NewScanner(file)
	// Use a larger buffer to reduce allocations
	buf := make([]byte, 64*1024)
	scanner.Buffer(buf, 64*1024)

	validProxyCount := 0
	lineNum := 1

	for scanner.Scan() {
		lineBytes := scanner.Bytes()
		// Quick validation without string conversion
		if len(lineBytes) > 0 && lineBytes[0] != '#' {
			// Trim whitespace in-place on bytes
			start, end := 0, len(lineBytes)
			for start < end && (lineBytes[start] == ' ' || lineBytes[start] == '\t') {
				start++
			}
			for end > start && (lineBytes[end-1] == ' ' || lineBytes[end-1] == '\t' || lineBytes[end-1] == '\r') {
				end--
			}
			if end > start && lineNum > startLine {
				validProxyCount++
			}
		}
		lineNum++
	}

	// Reset file position for second pass
	file.Seek(0, 0)
	scanner = bufio.NewScanner(file)
	// Reuse the same buffer
	scanner.Buffer(buf, 64*1024)

	// Pre-allocate slice with exact capacity
	remainingProxies := make([]types.ProxyWithLine, 0, validProxyCount)
	lineNum = 1

	for scanner.Scan() {
		lineBytes := scanner.Bytes()
		if len(lineBytes) > 0 && lineBytes[0] != '#' {
			// Trim whitespace in-place on bytes
			start, end := 0, len(lineBytes)
			for start < end && (lineBytes[start] == ' ' || lineBytes[start] == '\t') {
				start++
			}
			for end > start && (lineBytes[end-1] == ' ' || lineBytes[end-1] == '\t' || lineBytes[end-1] == '\r') {
				end--
			}
			if end > start && lineNum > startLine {
				// Convert to string only when needed
				line := string(lineBytes[start:end])
				remainingProxies = append(remainingProxies, types.ProxyWithLine{
					LineNum: lineNum,
					Proxy:   line,
				})
			}
		}
		lineNum++
	}

	if len(remainingProxies) > 0 {
		totalProxies := validProxyCount + startLine
		logger.GlobalLogger.LogBoth(fmt.Sprintf("📡 Loaded %d total proxies from %s", totalProxies, pm.proxyFile))
		if startLine > 0 {
			logger.GlobalLogger.LogBoth(fmt.Sprintf("📍 Resuming from proxy line %d, %d proxies remaining", startLine+1, len(remainingProxies)))
		}

		pm.mutex.Lock()
		pm.workingProxies = remainingProxies
		pm.failedProxies = make([]types.ProxyWithLine, 0, 10) // Pre-allocate small capacity for failed proxies
		pm.mutex.Unlock()

		logger.GlobalLogger.LogBoth(fmt.Sprintf("✅ %d proxies loaded and ready for testing", len(remainingProxies)))
	} else if startLine > 0 {
		logger.GlobalLogger.LogBoth(fmt.Sprintf("📡 All proxies from %s have been used. Resetting to beginning.", pm.proxyFile))
		pm.saveProxyLinePosition(0)
		pm.loadProxies()
	} else {
		logger.GlobalLogger.LogBoth("⚠️ No proxies found in file, continuing without proxy support")
	}
}

// parseProxy converts proxy string to ProxyConfig efficiently
func (pm *Manager) parseProxy(proxy string) *types.ProxyConfig {
	// Only trim if necessary
	if len(proxy) > 0 && (proxy[0] == ' ' || proxy[len(proxy)-1] == ' ') {
		proxy = strings.TrimSpace(proxy)
	}
	if proxy == "" {
		return nil
	}

	// Check for protocol prefixes efficiently
	if len(proxy) > 7 {
		if proxy[:7] == "http://" || proxy[:8] == "https://" ||
			(len(proxy) > 8 && proxy[:8] == "socks4://") ||
			(len(proxy) > 8 && proxy[:8] == "socks5://") {
			return &types.ProxyConfig{
				HTTP:  proxy,
				HTTPS: proxy,
			}
		}
	}

	// Count colons to determine format
	colonCount := strings.Count(proxy, ":")

	if colonCount == 1 {
		// Format: ip:port
		colonIndex := strings.IndexByte(proxy, ':')
		if colonIndex > 0 && colonIndex < len(proxy)-1 {
			return &types.ProxyConfig{
				HTTP:  "http://" + proxy,
				HTTPS: "http://" + proxy,
			}
		}
	} else if colonCount == 3 {
		// Format: ip:port:user:pass
		parts := strings.SplitN(proxy, ":", 4)
		if len(parts) == 4 {
			// Build URL efficiently
			proxyURL := "http://" + parts[2] + ":" + parts[3] + "@" + parts[0] + ":" + parts[1]
			return &types.ProxyConfig{
				HTTP:  proxyURL,
				HTTPS: proxyURL,
			}
		}
	}

	// Fallback: use as-is
	return &types.ProxyConfig{
		HTTP:  proxy,
		HTTPS: proxy,
	}
}

// testSingleProxy tests a single proxy using the global client
func (pm *Manager) testSingleProxy(proxy string) bool {
	proxyConfig := pm.parseProxy(proxy)
	if proxyConfig == nil {
		return false
	}

	headers := map[string]string{
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
	}

	// Use the global client for proxy testing to reduce memory usage
	_, err := httpclient.GetGlobalClient().Get(nil, "https://login.live.com/", requests.RequestOption{
		Headers: headers,
		Timeout: 1500 * time.Millisecond,
		Proxy:   proxyConfig.HTTP,
	})

	return err == nil
}

// GetSharedProxy returns the current shared proxy
func (pm *Manager) GetSharedProxy() *types.ProxyConfig {
	pm.mutex.Lock()
	defer pm.mutex.Unlock()
	return pm.currentProxy
}

// FindNextWorkingProxy finds and sets the next working proxy
func (pm *Manager) FindNextWorkingProxy() *types.ProxyConfig {
	pm.mutex.Lock()
	defer pm.mutex.Unlock()

	if len(pm.workingProxies) == 0 {
		pm.currentProxy = nil
		return nil
	}

	// Try up to 5 proxies for speed
	maxAttempts := int(math.Min(5, float64(len(pm.workingProxies))))
	for i := 0; i < maxAttempts; i++ {
		proxyWithLine := pm.workingProxies[pm.currentIndex]
		pm.currentIndex = (pm.currentIndex + 1) % len(pm.workingProxies)

		proxyConfig := pm.parseProxy(proxyWithLine.Proxy)
		if proxyConfig != nil {
			// Quick test with shorter timeout
			if pm.testSingleProxy(proxyWithLine.Proxy) {
				pm.currentProxy = proxyConfig
				pm.saveProxyLinePosition(proxyWithLine.LineNum)
				return proxyConfig
			}
		}
	}

	// If no proxy worked, just use the next one without testing
	if len(pm.workingProxies) > 0 {
		proxyWithLine := pm.workingProxies[pm.currentIndex]
		pm.currentIndex = (pm.currentIndex + 1) % len(pm.workingProxies)
		proxyConfig := pm.parseProxy(proxyWithLine.Proxy)
		if proxyConfig != nil {
			pm.currentProxy = proxyConfig
			pm.saveProxyLinePosition(proxyWithLine.LineNum)
			return proxyConfig
		}
	}

	pm.currentProxy = nil
	return nil
}

// MarkProxyFailed marks the current proxy as failed
func (pm *Manager) MarkProxyFailed(proxyConfig *types.ProxyConfig) {
	if proxyConfig == nil {
		return
	}

	pm.mutex.Lock()
	defer pm.mutex.Unlock()

	if pm.currentProxy == proxyConfig {
		pm.currentProxy = nil
	}
}

// GetProxyCount returns working and failed proxy counts
func (pm *Manager) GetProxyCount() (int, int) {
	pm.mutex.Lock()
	defer pm.mutex.Unlock()
	return len(pm.workingProxies), len(pm.failedProxies)
}
