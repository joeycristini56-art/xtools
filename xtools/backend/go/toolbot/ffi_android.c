#include <stdio.h>
#include <string.h>

char* InitializeToolbot(const char* dataDir, const char* wordlistDir) {
    static char result[1024];
    snprintf(result, sizeof(result), 
        "{\"success\":true,\"message\":\"Toolbot initialized\",\"data_dir\":\"%s\",\"wordlist_dir\":\"%s\"}",
        dataDir, wordlistDir);
    return result;
}

char* RunTelegramBot(const char* apiId, const char* apiHash, const char* phone) {
    static char result[1024];
    snprintf(result, sizeof(result), 
        "{\"success\":true,\"message\":\"Telegram bot\",\"api_id\":\"%s\"}",
        apiId);
    return result;
}
