package main

import "C"
import (
"encoding/json"
"os"
"path/filepath"
)

//export InitializeToolbot
func InitializeToolbot(dataDir *C.char, wordlistDir *C.char) *C.char {
dataDirStr := C.GoString(dataDir)
wordlistDirStr := C.GoString(wordlistDir)

// Create directories
os.MkdirAll(filepath.Join(dataDirStr, "data"), 0755)
os.MkdirAll(filepath.Join(dataDirStr, "tmp"), 0755)

result := map[string]interface{}{
"success": true,
"message": "Toolbot initialized",
"data_dir": dataDirStr,
"wordlist_dir": wordlistDirStr,
}

jsonBytes, _ := json.Marshal(result)
return C.CString(string(jsonBytes))
}

//export RunTelegramBot
func RunTelegramBot(apiId *C.char, apiHash *C.char, phone *C.char) *C.char {
// Would need to start the bot in a goroutine
result := map[string]interface{}{
"success": true,
"message": "Telegram bot would start here",
"api_id": C.GoString(apiId),
}

jsonBytes, _ := json.Marshal(result)
return C.CString(string(jsonBytes))
}
