package logger

import (
	"fmt"
	"os"
	"sync"
	"time"
)

// Logger provides thread-safe logging to console and file
type Logger struct {
	logFile string
	mutex   sync.Mutex
}

// New creates a new logger instance
func New(logFile string) *Logger {
	logger := &Logger{
		logFile: logFile,
	}
	
	// Initialize log file
	file, err := os.Create(logFile)
	if err == nil {
		fmt.Fprintf(file, "=== Xbox Account Checker Log - %s ===\n", time.Now().Format("2006-01-02 15:04:05"))
		file.Close()
	}
	
	return logger
}

// Log writes a message to console and/or file
func (l *Logger) Log(message string, toConsole, toFile bool) {
	timestamp := time.Now().Format("15:04:05")
	formattedMessage := fmt.Sprintf("[%s] %s", timestamp, message)
	
	l.mutex.Lock()
	defer l.mutex.Unlock()
	
	if toConsole {
		fmt.Println(message)
	}
	
	if toFile {
		file, err := os.OpenFile(l.logFile, os.O_APPEND|os.O_WRONLY, 0644)
		if err == nil {
			fmt.Fprintln(file, formattedMessage)
			file.Close()
		}
	}
}

// LogBoth logs to both console and file
func (l *Logger) LogBoth(message string) {
	l.Log(message, true, true)
}

// LogConsole logs only to console
func (l *Logger) LogConsole(message string) {
	l.Log(message, true, false)
}

// Global logger instance
var GlobalLogger = New("checker.log")