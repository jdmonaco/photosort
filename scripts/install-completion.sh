#!/bin/bash
# Manual completion installation script for photosort
# This can be used if the --install-completion option doesn't work

COMPLETION_DIR="$(dirname "$0")/../completion"
COMPLETION_FILE="$COMPLETION_DIR/photosort-completion.bash"
PHOTOSORT_DIR="$HOME/.photosort"
COMPLETION_DEST="$PHOTOSORT_DIR/completion.bash"

echo "Installing photosort bash completion..."

# Check if completion file exists
if [[ ! -f "$COMPLETION_FILE" ]]; then
    echo "Error: Completion file not found at $COMPLETION_FILE"
    exit 1
fi

# Create photosort config directory
mkdir -p "$PHOTOSORT_DIR"

# Copy completion script to ~/.photosort/completion.bash
cp "$COMPLETION_FILE" "$COMPLETION_DEST"

# Install to ~/.bashrc
BASHRC="$HOME/.bashrc"
MARKER_START="# >>> photosort completion >>>"
MARKER_END="# <<< photosort completion <<<"

# Check if already installed
if [[ -f "$BASHRC" ]] && grep -q "$MARKER_START" "$BASHRC"; then
    echo "Photosort completion already installed in ~/.bashrc"
    exit 0
fi

# Add source line to .bashrc
echo "" >> "$BASHRC"
echo "$MARKER_START" >> "$BASHRC"
echo "[ -r $COMPLETION_DEST ] && source $COMPLETION_DEST" >> "$BASHRC"
echo "$MARKER_END" >> "$BASHRC"

echo "✓ Completion script saved to $COMPLETION_DEST"
echo "✓ Bash completion installed to ~/.bashrc"
echo "Run 'source ~/.bashrc' or restart your terminal to enable completion"