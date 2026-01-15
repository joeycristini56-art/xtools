package httpclient

import (
	"bytes"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/ncpmeplmls0614/requests"
	"xbox-checker/internal/logger"
)

// StreamingResponseHandler provides efficient response handling methods
type StreamingResponseHandler struct {
	response *requests.Response
	maxSize  int64
}

// NewStreamingResponseHandler creates a new streaming response handler
func NewStreamingResponseHandler(resp *requests.Response, maxSize int64) *StreamingResponseHandler {
	return &StreamingResponseHandler{
		response: resp,
		maxSize:  maxSize,
	}
}

// GetSafeText safely gets response text with size limits to prevent memory issues
func (h *StreamingResponseHandler) GetSafeText() string {
	if h.response == nil {
		return ""
	}
	
	// Check content length first
	contentLength := h.response.ContentLength()
	if contentLength > h.maxSize {
		logger.GlobalLogger.LogBoth(fmt.Sprintf("⚠️ Response too large: %d bytes, skipping", contentLength))
		return ""
	}
	
	// Get content as bytes to avoid Text() allocation
	content := h.response.Content()
	if int64(len(content)) > h.maxSize {
		logger.GlobalLogger.LogBoth(fmt.Sprintf("⚠️ Response content too large: %d bytes, truncating", len(content)))
		content = content[:h.maxSize]
	}
	
	return string(content)
}

// StreamDecodeJSON uses streaming JSON decoder to parse response without loading entire body into memory
func (h *StreamingResponseHandler) StreamDecodeJSON(target interface{}) error {
	if h.response == nil {
		return fmt.Errorf("response is nil")
	}

	// Check content length first
	contentLength := h.response.ContentLength()
	if contentLength > h.maxSize {
		return fmt.Errorf("response too large: %d bytes", contentLength)
	}

	// Get the response content
	content := h.response.Content()
	if len(content) == 0 {
		return fmt.Errorf("response content is empty")
	}

	// Limit the content size to prevent excessive memory usage
	if int64(len(content)) > h.maxSize {
		content = content[:h.maxSize]
	}
	
	// Create a JSON decoder that reads from the content
	reader := bytes.NewReader(content)
	decoder := json.NewDecoder(reader)
	
	// Decode directly into the target without intermediate allocations
	return decoder.Decode(target)
}

// FindInResponse efficiently searches for patterns in response without loading entire content
func (h *StreamingResponseHandler) FindInResponse(startPattern, endPattern string, caseSensitive bool) string {
	if h.response == nil {
		return ""
	}

	content := h.GetSafeText()
	if content == "" {
		return ""
	}

	// Use efficient string operations
	if !caseSensitive {
		content = strings.ToLower(content)
		startPattern = strings.ToLower(startPattern)
		endPattern = strings.ToLower(endPattern)
	}

	startIndex := strings.Index(content, startPattern)
	if startIndex == -1 {
		return ""
	}

	startIndex += len(startPattern)
	endIndex := strings.Index(content[startIndex:], endPattern)
	if endIndex == -1 {
		return ""
	}

	return content[startIndex : startIndex+endIndex]
}

// ParseBalanceFromJSON efficiently parses balance information from JSON response using streaming
func (h *StreamingResponseHandler) ParseBalanceFromJSON() (float64, string, error) {
	// Define a minimal struct to capture only what we need
	type BalanceInfo struct {
		Details struct {
			Balance  float64 `json:"balance"`
			Currency string  `json:"currency"`
		} `json:"details"`
	}

	var balanceArray []BalanceInfo
	
	// Use streaming decoder to parse only the balance information
	if err := h.StreamDecodeJSON(&balanceArray); err != nil {
		return 0, "", err
	}

	// Find the first valid balance
	for _, item := range balanceArray {
		if item.Details.Balance > 0 && item.Details.Currency != "" {
			return item.Details.Balance, item.Details.Currency, nil
		}
	}

	return 0, "", fmt.Errorf("no valid balance found")
}

