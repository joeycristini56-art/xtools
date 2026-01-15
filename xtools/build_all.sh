#!/bin/bash
# Build script for all platforms

echo "=== XTools Build Script ==="
echo ""

# Set up paths
export PATH=$PATH:/usr/local/go/bin
export ANDROID_NDK_HOME=/tmp/android-ndk-r26b

# Create interpreters directory structure
mkdir -p interpreters/{linux,windows,android/{arm64,armv7,x86_64},ios/{arm64,simulator,frameworks}}

echo "1. Building Python FFI for Linux..."
cd backend/python
gcc -shared -fPIC -o ../../interpreters/linux/xtools_ffi.so xtools_ffi.c \
    -I$(python3 -c "import sysconfig; print(sysconfig.get_path('include'))") -lpython3
echo "   ✓ Linux Python FFI"

echo ""
echo "2. Building Go FFI for Linux..."
cd ../go/runtime
go build -buildmode=c-shared -o ../../interpreters/linux/libxboxchecker.so ffi_export.go
cd ../toolbot
go build -buildmode=c-shared -o ../../interpreters/linux/libtoolbot.so ffi_export.go
echo "   ✓ Linux Go FFI"

echo ""
echo "3. Building Go FFI for Windows..."
cd ../runtime
GOOS=windows GOARCH=amd64 CGO_ENABLED=1 CC=x86_64-w64-mingw32-gcc go build -buildmode=c-shared -o ../../interpreters/windows/libxboxchecker.dll ffi_export.go
cd ../toolbot
GOOS=windows GOARCH=amd64 CGO_ENABLED=1 CC=x86_64-w64-mingw32-gcc go build -buildmode=c-shared -o ../../interpreters/windows/libtoolbot.dll ffi_export.go
echo "   ✓ Windows Go FFI"

echo ""
echo "4. Building Go FFI for Android..."
cd ../runtime
GOOS=linux GOARCH=arm64 CGO_ENABLED=1 CC=$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android33-clang go build -buildmode=c-shared -o ../../interpreters/android/arm64/libxboxchecker.so ffi_export.go
cd ../toolbot
GOOS=linux GOARCH=arm64 CGO_ENABLED=1 CC=$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android33-clang go build -buildmode=c-shared -o ../../interpreters/android/arm64/libtoolbot.so ffi_export.go
echo "   ✓ Android arm64 Go FFI"

echo ""
echo "5. Building Go FFI for iOS (requires macOS)..."
echo "   ⚠️  iOS requires macOS to build"
echo "   Use GitHub Actions workflow to build iOS libraries"

echo ""
echo "=== Build Complete ==="
echo ""
echo "Libraries created in interpreters/"
echo "- Linux: interpreters/linux/"
echo "- Windows: interpreters/windows/"
echo "- Android: interpreters/android/"
echo "- iOS: Use GitHub Actions workflow"
