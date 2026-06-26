#!/bin/bash
set -e

# Run tests first
./tests.sh

echo "Building compiled app..."
BUILD_DIR=$(mktemp -d)

# Copy packages
cp -r playlister_lib "$BUILD_DIR/"
cp -r spotipy "$BUILD_DIR/"

# Add entrypoint for zipapp
cat << 'EOF' > "$BUILD_DIR/__main__.py"
import sys
from playlister_lib.main import main
if __name__ == "__main__":
    main()
EOF

mkdir -p bin
python3 -m zipapp "$BUILD_DIR" -o bin/playlister -p "/usr/bin/env python3"
chmod +x bin/playlister

rm -rf "$BUILD_DIR"
echo "Compilation completed: bin/playlister created successfully."
