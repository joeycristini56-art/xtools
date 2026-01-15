package utils

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/url"
	"strings"
	"sync"
)

var (
	// Pool for reusing strings.Builder to reduce allocations
	stringBuilderPool = sync.Pool{
		New: func() interface{} {
			return &strings.Builder{}
		},
	}
)

// getStringBuilder gets a string builder from the pool
func getStringBuilder() *strings.Builder {
	return stringBuilderPool.Get().(*strings.Builder)
}

// putStringBuilder returns a string builder to the pool
func putStringBuilder(sb *strings.Builder) {
	sb.Reset()
	stringBuilderPool.Put(sb)
}

// Base64Decode decodes base64 string
func Base64Decode(encoded string) string {
	decoded, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		return ""
	}
	return string(decoded)
}

// URLEncode URL encodes text
func URLEncode(text string) string {
	return url.QueryEscape(text)
}

// URLDecode URL decodes text
func URLDecode(text string) string {
	decoded, err := url.QueryUnescape(text)
	if err != nil {
		return text
	}
	return decoded
}

// ParseLR parses text between left and right delimiters efficiently
func ParseLR(source, left, right string, createEmpty bool) string {
	start := strings.Index(source, left)
	if start == -1 {
		return ""
	}
	start += len(left)

	// Optimize for single character right delimiter
	if len(right) == 1 {
		end := strings.IndexByte(source[start:], right[0])
		if end == -1 {
			return ""
		}
		result := source[start : start+end]
		if len(result) == 0 && !createEmpty {
			return ""
		}
		return result
	}

	end := strings.Index(source[start:], right)
	if end == -1 {
		return ""
	}

	result := source[start : start+end]
	if len(result) == 0 && !createEmpty {
		return ""
	}
	return result
}

// ParseJSON parses JSON value by key
func ParseJSON(source, key string) string {
	var data interface{}
	if err := json.Unmarshal([]byte(source), &data); err != nil {
		return ""
	}
	return getNestedValue(data, key)
}

// getNestedValue gets nested value from JSON data
func getNestedValue(data interface{}, key string) string {
	switch v := data.(type) {
	case map[string]interface{}:
		if val, ok := v[key]; ok {
			return fmt.Sprintf("%v", val)
		}
		for _, value := range v {
			if result := getNestedValue(value, key); result != "" {
				return result
			}
		}
	case []interface{}:
		for _, item := range v {
			if result := getNestedValue(item, key); result != "" {
				return result
			}
		}
	}
	return ""
}

// FormatCurrency formats balance with currency code efficiently
func FormatCurrency(balance float64, currency string) string {
	currency = strings.ToUpper(currency)

	// Use string builder to avoid multiple allocations
	sb := getStringBuilder()
	defer putStringBuilder(sb)

	// Format balance based on currency
	if currency == "JPY" || currency == "KRW" {
		sb.WriteString(fmt.Sprintf("%.0f", balance))
	} else {
		if balance == float64(int64(balance)) {
			sb.WriteString(fmt.Sprintf("%.0f", balance))
		} else {
			sb.WriteString(fmt.Sprintf("%.2f", balance))
		}
	}

	sb.WriteByte(' ')
	sb.WriteString(currency)

	return sb.String()
}
