package httpclient

import (
	"sync"
	"sync/atomic"
	"time"

	"github.com/gospider007/ja3"
	"github.com/ncpmeplmls0614/requests"
)

var (
	// clientPool holds 50 HTTP client instances for 50 concurrent connections
	clientPool []*requests.Client
	// poolSize defines the number of clients in the pool (50 for 50 concurrent connections)
	poolSize = 1000
	// poolIndex tracks the current client to use (atomic counter for lock-free access)
	poolIndex int64
	// poolOnce ensures the pool is created only once
	poolOnce sync.Once
)

// GetGlobalClient returns one of 50 HTTP client instances using lock-free round-robin
// This allows for true 50 concurrent connections without lock contention
func GetGlobalClient() *requests.Client {
	poolOnce.Do(func() {
		initializeClientPool()
	})
	
	// Lock-free atomic round-robin selection
	index := atomic.AddInt64(&poolIndex, 1) - 1 // Get index then increment
	clientIndex := index % int64(poolSize)
	return clientPool[clientIndex]
}

// initializeClientPool creates 50 optimized HTTP client instances
func initializeClientPool() {
	clientPool = make([]*requests.Client, poolSize)
	
	for i := 0; i < poolSize; i++ {
		clientPool[i] = createOptimizedClient()
		if clientPool[i] != nil {
		} else {
		}
	}
}

// createOptimizedClient creates a single optimized HTTP client
func createOptimizedClient() *requests.Client {
	// Set up Chrome-like JA3 fingerprint for anti-detection
	chromeJa3 := "772,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,5-27-13-35-16-18-43-17513-65281-51-45-11-0-10-23,12092-29-23-24,0"
	ja3Spec, err := ja3.CreateSpecWithStr(chromeJa3)
	if err != nil {
		// Fallback to default if JA3 creation fails
		ja3Spec = ja3.Ja3Spec{}
	} else {
	}

	// Default headers for all requests
	defaultHeaders := map[string]string{
		"User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		"Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
		"Accept-Language": "en-US,en;q=0.9",
		"Accept-Encoding": "gzip, deflate, br",
		"DNT":             "1",
		"Connection":      "keep-alive",
		"Upgrade-Insecure-Requests": "1",
	}

	// Create the optimized global client with enhanced connection pooling for 50 concurrent connections
	client, err := requests.NewClient(nil, requests.ClientOption{
		DisCookie: false,  // Enable automatic cookie management 
		DisAlive:  false,  // Enable keep-alive connections
		Ja3Spec:   ja3Spec, // Set JA3 fingerprint at client level
		Timeout:   10 * time.Second, // Reasonable timeout
		Headers:   defaultHeaders, // Set default browser-like headers
		
		// Optimized connection settings to reduce memory usage and improve performance
		ResponseHeaderTimeout: 5 * time.Second,  // Reduce header timeout
		TlsHandshakeTimeout:   3 * time.Second,  // Reduce TLS timeout
		DialTimeout:          3 * time.Second,   // Reduce dial timeout
		KeepAlive:            30 * time.Second,  // Standard keepalive
		MaxRetries:           1,                 // Reduce retry attempts
		MaxRedirectNum:       3,                 // Limit redirects
		
		// Connection pooling optimizations (removed unsupported fields)
	})
	
	if err != nil {
		// If client creation fails, create a basic one
		client, _ = requests.NewClient(nil, requests.ClientOption{
			Timeout: 10 * time.Second,
		})
	} else {
	}
	
	return client
}

// SetPoolSize allows changing the pool size (must be called before first GetGlobalClient call)
func SetPoolSize(size int) {
	if size < 1 {
		size = 1
	}
	if size > 5000 {
		size = 5000
	}
	poolSize = size
}

// GetPoolSize returns the current pool size
func GetPoolSize() int {
	return poolSize
}

// ResetClientPool allows resetting the client pool (useful for testing)
func ResetClientPool() {
	clientPool = nil
	atomic.StoreInt64(&poolIndex, 0)
	poolOnce = sync.Once{}
}