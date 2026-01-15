package stats

import (
	"math"
	"sync/atomic"
	"time"

	"toolbot/modules/checker/pkg/types"
)

// ThreadSafeStats provides thread-safe statistics tracking
type ThreadSafeStats struct {
	totalChecked int64
	validCount   int64
	failedCount  int64
	bannedCount  int64
	customCount  int64
	startTime    time.Time
}

// New creates a new stats tracker
func New() *ThreadSafeStats {
	return &ThreadSafeStats{
		startTime: time.Now(),
	}
}

// Increment increments the appropriate counter
func (s *ThreadSafeStats) Increment(result types.CheckResult) {
	atomic.AddInt64(&s.totalChecked, 1)

	switch result {
	case types.SUCCESS:
		atomic.AddInt64(&s.validCount, 1)
	case types.FAILURE:
		atomic.AddInt64(&s.failedCount, 1)
	case types.BAN:
		atomic.AddInt64(&s.bannedCount, 1)
	case types.CUSTOM:
		atomic.AddInt64(&s.customCount, 1)
	}
}

// GetCPM returns current checks per minute
func (s *ThreadSafeStats) GetCPM() float64 {
	elapsed := time.Since(s.startTime).Seconds()
	if elapsed > 0 {
		return (float64(atomic.LoadInt64(&s.totalChecked)) / elapsed) * 60
	}
	return 0.0
}

// GetStats returns current statistics
func (s *ThreadSafeStats) GetStats() map[string]interface{} {
	elapsed := time.Since(s.startTime).Seconds()
	cpm := 0.0
	if elapsed > 0 {
		cpm = (float64(atomic.LoadInt64(&s.totalChecked)) / elapsed) * 60
	}

	return map[string]interface{}{
		"total":  atomic.LoadInt64(&s.totalChecked),
		"valid":  atomic.LoadInt64(&s.validCount),
		"failed": atomic.LoadInt64(&s.failedCount),
		"banned": atomic.LoadInt64(&s.bannedCount),
		"custom": atomic.LoadInt64(&s.customCount),
		"cpm":    math.Round(cpm*10) / 10,
	}
}

// GetValidCount returns the current valid count
func (s *ThreadSafeStats) GetValidCount() int64 {
	return atomic.LoadInt64(&s.validCount)
}
