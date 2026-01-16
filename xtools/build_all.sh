#!/bin/bash
# XTools Build Script - Production-grade native library compilation
# Supports Linux, Windows (cross-compile), Android, and iOS (macOS only)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              XTools Native Library Build Script              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Set up paths
export PATH=$PATH:/usr/local/go/bin
export ANDROID_NDK_HOME=${ANDROID_NDK_HOME:-/tmp/android-ndk-r26b}

# Create interpreters directory structure
echo "📁 Creating directory structure..."
mkdir -p backend/interpreters/{linux,windows,macos,android/{arm64,armv7,x86_64},ios/{arm64,simulator,frameworks}}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to build Python FFI
build_python_ffi() {
    echo ""
    echo "🐍 Building Python FFI..."
    
    if ! command_exists python3; then
        echo "   ⚠️  Python3 not found, skipping Python FFI build"
        return
    fi
    
    cd backend/python
    
    PYTHON_INCLUDE=$(python3 -c "import sysconfig; print(sysconfig.get_path('include'))")
    PYTHON_LIB=$(python3 -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR'))")
    PYTHON_VERSION=$(python3 -c "import sys; print(f'python{sys.version_info.major}.{sys.version_info.minor}')")
    
    if [ "$(uname)" == "Linux" ]; then
        echo "   Building for Linux..."
        gcc -shared -fPIC -o ../interpreters/linux/xtools_ffi.so xtools_ffi.c \
            -I"$PYTHON_INCLUDE" -L"$PYTHON_LIB" -l"$PYTHON_VERSION" 2>/dev/null || \
        gcc -shared -fPIC -o ../interpreters/linux/xtools_ffi.so xtools_ffi.c \
            -I"$PYTHON_INCLUDE" $(python3-config --ldflags --embed 2>/dev/null || python3-config --ldflags) 2>/dev/null || \
        echo "   ⚠️  Failed to build Python FFI for Linux"
        
        if [ -f ../interpreters/linux/xtools_ffi.so ]; then
            echo "   ✓ Linux Python FFI built"
        fi
    elif [ "$(uname)" == "Darwin" ]; then
        echo "   Building for macOS..."
        clang -shared -fPIC -o ../interpreters/macos/xtools_ffi.dylib xtools_ffi.c \
            -I"$PYTHON_INCLUDE" $(python3-config --ldflags --embed 2>/dev/null || python3-config --ldflags) 2>/dev/null || \
        echo "   ⚠️  Failed to build Python FFI for macOS"
        
        if [ -f ../interpreters/macos/xtools_ffi.dylib ]; then
            echo "   ✓ macOS Python FFI built"
        fi
    fi
    
    cd "$SCRIPT_DIR"
}

# Function to build Go FFI for Linux
build_go_linux() {
    echo ""
    echo "🐹 Building Go FFI for Linux..."
    
    if ! command_exists go; then
        echo "   ⚠️  Go not found, skipping Go FFI build"
        return
    fi
    
    # Build Xbox checker
    cd backend/go/runtime
    if go build -buildmode=c-shared -o ../../interpreters/linux/libxboxchecker.so . 2>/dev/null; then
        echo "   ✓ Linux Xbox Checker built"
    else
        echo "   ⚠️  Failed to build Xbox Checker for Linux"
    fi
    
    # Build Toolbot
    cd ../toolbot
    if go build -buildmode=c-shared -o ../../interpreters/linux/libtoolbot.so . 2>/dev/null; then
        echo "   ✓ Linux Toolbot built"
    else
        echo "   ⚠️  Failed to build Toolbot for Linux"
    fi
    
    cd "$SCRIPT_DIR"
}

# Function to build Go FFI for Windows (cross-compile)
build_go_windows() {
    echo ""
    echo "🪟 Building Go FFI for Windows (cross-compile)..."
    
    if ! command_exists go; then
        echo "   ⚠️  Go not found, skipping"
        return
    fi
    
    if ! command_exists x86_64-w64-mingw32-gcc; then
        echo "   ⚠️  MinGW not found, skipping Windows cross-compile"
        echo "   Install with: apt-get install gcc-mingw-w64-x86-64"
        return
    fi
    
    cd backend/go/runtime
    if GOOS=windows GOARCH=amd64 CGO_ENABLED=1 CC=x86_64-w64-mingw32-gcc \
        go build -buildmode=c-shared -o ../../interpreters/windows/libxboxchecker.dll . 2>/dev/null; then
        echo "   ✓ Windows Xbox Checker built"
    else
        echo "   ⚠️  Failed to build Xbox Checker for Windows"
    fi
    
    cd ../toolbot
    if GOOS=windows GOARCH=amd64 CGO_ENABLED=1 CC=x86_64-w64-mingw32-gcc \
        go build -buildmode=c-shared -o ../../interpreters/windows/libtoolbot.dll . 2>/dev/null; then
        echo "   ✓ Windows Toolbot built"
    else
        echo "   ⚠️  Failed to build Toolbot for Windows"
    fi
    
    cd "$SCRIPT_DIR"
}

# Function to build Go FFI for Android
build_go_android() {
    echo ""
    echo "🤖 Building Go FFI for Android..."
    
    if ! command_exists go; then
        echo "   ⚠️  Go not found, skipping"
        return
    fi
    
    if [ ! -d "$ANDROID_NDK_HOME" ]; then
        echo "   ⚠️  Android NDK not found at $ANDROID_NDK_HOME"
        echo "   Set ANDROID_NDK_HOME environment variable"
        return
    fi
    
    NDK_TOOLCHAIN="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin"
    
    # ARM64
    cd backend/go/runtime
    if GOOS=android GOARCH=arm64 CGO_ENABLED=1 CC="$NDK_TOOLCHAIN/aarch64-linux-android33-clang" \
        go build -buildmode=c-shared -o ../../interpreters/android/arm64/libxboxchecker.so . 2>/dev/null; then
        echo "   ✓ Android arm64 Xbox Checker built"
    else
        echo "   ⚠️  Failed to build Xbox Checker for Android arm64"
    fi
    
    cd "$SCRIPT_DIR"
}

# Function to build Go FFI for macOS
build_go_macos() {
    echo ""
    echo "🍎 Building Go FFI for macOS..."
    
    if [ "$(uname)" != "Darwin" ]; then
        echo "   ⚠️  macOS build requires macOS host"
        return
    fi
    
    if ! command_exists go; then
        echo "   ⚠️  Go not found, skipping"
        return
    fi
    
    cd backend/go/runtime
    if go build -buildmode=c-shared -o ../../interpreters/macos/libxboxchecker.dylib . 2>/dev/null; then
        echo "   ✓ macOS Xbox Checker built"
    else
        echo "   ⚠️  Failed to build Xbox Checker for macOS"
    fi
    
    cd ../toolbot
    if go build -buildmode=c-shared -o ../../interpreters/macos/libtoolbot.dylib . 2>/dev/null; then
        echo "   ✓ macOS Toolbot built"
    else
        echo "   ⚠️  Failed to build Toolbot for macOS"
    fi
    
    cd "$SCRIPT_DIR"
}

# Main build process
echo "🔍 Detecting platform: $(uname)"
echo ""

# Build Python FFI
build_python_ffi

# Build Go FFI based on platform
if [ "$(uname)" == "Linux" ]; then
    build_go_linux
    build_go_windows
    build_go_android
elif [ "$(uname)" == "Darwin" ]; then
    build_go_macos
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                     Build Complete                           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📦 Libraries created in backend/interpreters/"
echo ""
echo "Available libraries:"
ls -la backend/interpreters/linux/ 2>/dev/null && echo "" || true
ls -la backend/interpreters/windows/ 2>/dev/null && echo "" || true
ls -la backend/interpreters/macos/ 2>/dev/null && echo "" || true
ls -la backend/interpreters/android/arm64/ 2>/dev/null && echo "" || true
echo ""
echo "💡 Note: iOS libraries require macOS and Xcode to build."
echo "   Use the build_ios.sh script on macOS."
