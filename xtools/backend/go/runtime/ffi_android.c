#include <stdio.h>
#include <string.h>

char* CheckXboxAccount(const char* apiKey, const char* comboFile) {
    static char result[1024];
    snprintf(result, sizeof(result), 
        "{\"success\":true,\"message\":\"Android check\",\"api_key\":\"%s\",\"combo_file\":\"%s\"}",
        apiKey, comboFile);
    return result;
}
