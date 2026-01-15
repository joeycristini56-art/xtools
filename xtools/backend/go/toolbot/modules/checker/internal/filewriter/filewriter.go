package filewriter

import (
	"bufio"
	"fmt"
	"os"
	"strings"
	"sync"

	"toolbot/modules/checker/pkg/types"
)

// Buffer pool to reduce allocations
var stringBuilderPool = sync.Pool{
	New: func() interface{} {
		return &strings.Builder{}
	},
}

// ThreadSafeFileWriter provides thread-safe file writing for valid accounts
type ThreadSafeFileWriter struct {
	filename string
	mutex    sync.Mutex
	file     *os.File
	writer   *bufio.Writer
}

// New creates a new file writer
func New(filename string) *ThreadSafeFileWriter {
	writer := &ThreadSafeFileWriter{
		filename: filename,
	}

	// Create and open file for writing
	file, err := os.OpenFile(filename, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		// Fallback to creating the file
		file, _ = os.Create(filename)
	}

	writer.file = file
	writer.writer = bufio.NewWriter(file)

	return writer
}

// WriteValid writes valid account to file
func (w *ThreadSafeFileWriter) WriteValid(email, password string, capturedData *types.CapturedData) {
	w.mutex.Lock()
	defer w.mutex.Unlock()

	// Get a string builder from the pool
	sb := stringBuilderPool.Get().(*strings.Builder)
	defer func() {
		sb.Reset()
		stringBuilderPool.Put(sb)
	}()

	// Start with email:password
	sb.WriteString(email)
	sb.WriteByte(':')
	sb.WriteString(password)

	// Pre-allocate parts slice to avoid growth
	parts := make([]string, 0, 8)

	// Parse credit card info efficiently
	if capturedData.CCInfo != "" {
		ccInfo := capturedData.CCInfo

		// Use IndexByte for faster searching
		ccStart := strings.Index(ccInfo, "CC: ")
		last4Start := strings.Index(ccInfo, "CC Last4Digit: ")

		if ccStart != -1 && last4Start != -1 {
			ccType := ""
			last4 := ""

			ccEnd := strings.Index(ccInfo[ccStart+4:], " |")
			if ccEnd != -1 {
				ccType = ccInfo[ccStart+4 : ccStart+4+ccEnd]
			}

			last4End := strings.Index(ccInfo[last4Start+16:], " |")
			if last4End != -1 {
				last4 = ccInfo[last4Start+16 : last4Start+16+last4End]
			}

			if ccType != "" && last4 != "" {
				// Use string builder for efficient concatenation
				ccBuilder := stringBuilderPool.Get().(*strings.Builder)
				ccBuilder.WriteString(ccType)
				ccBuilder.WriteString(" •••• ")
				ccBuilder.WriteString(last4)
				parts = append(parts, ccBuilder.String())
				ccBuilder.Reset()
				stringBuilderPool.Put(ccBuilder)
			}

			// Parse expiry efficiently
			monthStart := strings.Index(ccInfo, "CC expiryMonth: ")
			yearStart := strings.Index(ccInfo, "CC ExpYear: ")

			if monthStart != -1 && yearStart != -1 {
				month := ""
				year := ""

				monthEnd := strings.Index(ccInfo[monthStart+16:], " |")
				if monthEnd != -1 {
					month = ccInfo[monthStart+16 : monthStart+16+monthEnd]
				}

				yearEnd := strings.Index(ccInfo[yearStart+12:], " |")
				if yearEnd != -1 {
					year = ccInfo[yearStart+12 : yearStart+12+yearEnd]
				}

				if month != "" && year != "" {
					expiryBuilder := stringBuilderPool.Get().(*strings.Builder)
					expiryBuilder.WriteString("Expires: ")
					expiryBuilder.WriteString(month)
					expiryBuilder.WriteByte(' ')
					expiryBuilder.WriteString(year)
					parts = append(parts, expiryBuilder.String())
					expiryBuilder.Reset()
					stringBuilderPool.Put(expiryBuilder)
				}
			}
		}
	}

	if capturedData.PaypalEmail != "" {
		paypalBuilder := stringBuilderPool.Get().(*strings.Builder)
		paypalBuilder.WriteString("Paypal: ")
		paypalBuilder.WriteString(capturedData.PaypalEmail)
		parts = append(parts, paypalBuilder.String())
		paypalBuilder.Reset()
		stringBuilderPool.Put(paypalBuilder)
	}

	if capturedData.Balance != "" {
		balanceBuilder := stringBuilderPool.Get().(*strings.Builder)
		balanceBuilder.WriteString("Balance: (")
		balanceBuilder.WriteString(capturedData.Balance)
		balanceBuilder.WriteByte(')')
		parts = append(parts, balanceBuilder.String())
		balanceBuilder.Reset()
		stringBuilderPool.Put(balanceBuilder)
	}

	if capturedData.Country != "" {
		countryBuilder := stringBuilderPool.Get().(*strings.Builder)
		countryBuilder.WriteString("Country: ")
		countryBuilder.WriteString(capturedData.Country)
		parts = append(parts, countryBuilder.String())
		countryBuilder.Reset()
		stringBuilderPool.Put(countryBuilder)
	}

	// Parse services and recent purchases efficiently
	services := make([]string, 0, 3) // Pre-allocate for max 3 services
	var recentPurchases, recentCost string

	// Use array instead of slice to avoid allocation
	subscriptions := [3]string{capturedData.Subscription1, capturedData.Subscription2, capturedData.Subscription3}

	for _, sub := range subscriptions {
		if sub == "" {
			continue
		}

		serviceStart := strings.Index(sub, "[ Service: ")
		if serviceStart != -1 {
			serviceEnd := strings.Index(sub[serviceStart+11:], " ]")
			if serviceEnd != -1 {
				serviceName := sub[serviceStart+11 : serviceStart+11+serviceEnd]
				if serviceName != "" {
					services = append(services, serviceName)
				}
			}
		} else {
			purchaseStart := strings.Index(sub, "[ Recent Purchases: ")
			if purchaseStart != -1 {
				purchaseEnd := strings.Index(sub[purchaseStart+20:], " |")
				if purchaseEnd != -1 {
					recentPurchases = sub[purchaseStart+20 : purchaseStart+20+purchaseEnd]
				}

				costStart := strings.Index(sub, "Total Cost: ")
				if costStart != -1 {
					costEnd := strings.Index(sub[costStart+12:], " ]")
					if costEnd != -1 {
						recentCost = sub[costStart+12 : costStart+12+costEnd]
					}
				}
			}
		}
	}

	if len(services) > 0 {
		parts = append(parts, fmt.Sprintf("Services: %s", strings.Join(services, ", ")))
	}

	if recentCost != "" && recentPurchases != "" {
		parts = append(parts, fmt.Sprintf("Recent Purchases (%s) & Cost (%s)", recentPurchases, recentCost))
	} else if recentCost != "" {
		parts = append(parts, fmt.Sprintf("Recent Cost (%s)", recentCost))
	} else if recentPurchases != "" {
		parts = append(parts, fmt.Sprintf("Recent Purchases (%s)", recentPurchases))
	}

	// Build final output using string builder to reduce allocations
	if len(parts) > 0 {
		sb.WriteString(" | ")
		for i, part := range parts {
			if i > 0 {
				sb.WriteString(" | ")
			}
			sb.WriteString(part)
		}
	} else {
		sb.WriteString(" | No additional data")
	}
	sb.WriteByte('\n')

	if w.writer != nil {
		w.writer.WriteString(sb.String())
		w.writer.Flush() // Ensure data is written immediately
	}
}

// Close closes the file writer and flushes any remaining data
func (w *ThreadSafeFileWriter) Close() {
	w.mutex.Lock()
	defer w.mutex.Unlock()

	if w.writer != nil {
		w.writer.Flush()
		w.writer = nil
	}

	if w.file != nil {
		w.file.Close()
		w.file = nil
	}
}
