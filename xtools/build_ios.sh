#!/bin/bash
# Build iOS libraries on Linux using cross-compilation

echo "Building iOS libraries on Linux..."

# Check for iOS cross-compilation tools
if ! command -v o64-clang &> /dev/null; then
    echo "Installing iOS cross-compilation tools..."
    apt-get update
    apt-get install -y clang llvm lld
fi

# Create iOS build directory
mkdir -p interpreters/ios/arm64
mkdir -p interpreters/ios/simulator

# Build Go libraries for iOS (arm64 - device)
echo "Building Go libraries for iOS arm64..."
cd backend/go/runtime
GOOS=darwin GOARCH=arm64 CGO_ENABLED=1 CC=o64-clang go build -buildmode=c-shared -o ../../interpreters/ios/arm64/libxboxchecker.dylib ffi_simple.go

cd ../toolbot
GOOS=darwin GOARCH=arm64 CGO_ENABLED=1 CC=o64-clang go build -buildmode=c-shared -o ../../interpreters/ios/arm64/libtoolbot.dylib ffi_export.go

# Build Go libraries for iOS (x64 - simulator)
echo "Building Go libraries for iOS x64..."
cd ../runtime
GOOS=darwin GOARCH=amd64 CGO_ENABLED=1 CC=o64-clang go build -buildmode=c-shared -o ../../interpreters/ios/simulator/libxboxchecker.dylib ffi_simple.go

cd ../toolbot
GOOS=darwin GOARCH=amd64 CGO_ENABLED=1 CC=o64-clang go build -buildmode=c-shared -o ../../interpreters/ios/simulator/libtoolbot.dylib ffi_export.go

echo "iOS libraries built in interpreters/ios/"
echo "Note: You need to create iOS frameworks using lipo (requires macOS)"
