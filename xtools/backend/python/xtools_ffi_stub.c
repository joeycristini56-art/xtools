/*
 * XTools FFI - Windows Stub
 * Windows doesn't support Python C extensions easily, so we create a stub
 */

#include <stdio.h>

__declspec(dllexport) void gofile_upload() {}
__declspec(dllexport) void run_sort() {}
__declspec(dllexport) void run_filter() {}
__declspec(dllexport) void run_dedup() {}
__declspec(dllexport) void run_split() {}
__declspec(dllexport) void run_remove() {}
__declspec(dllexport) void discord_bot() {}
__declspec(dllexport) void telegram_bot() {}
__declspec(dllexport) void run_scraper() {}
__declspec(dllexport) void run_combo() {}
__declspec(dllexport) void run_captcha() {}

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved) {
    return TRUE;
}
