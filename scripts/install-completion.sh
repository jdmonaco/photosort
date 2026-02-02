#!/usr/bin/env bash
# Manual completion installation script for photosort
# This can be used if the --install-completion option doesn't work
set -eu

# Set script and link paths
PHOTOSORT_DIR="$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")"
PHOTOSORT_COMPL_FILE="$PHOTOSORT_DIR/data/completion.bash"
LOCAL_COMPL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions"
LOCAL_COMPL_LINK="$LOCAL_COMPL_DIR/photosort"

# Verify completion script path
if [[ ! -f "$PHOTOSORT_COMPL_FILE" ]]; then
    echo "Error: Completion file not found: $PHOTOSORT_COMPL_FILE" >&2
    exit 1
fi

# Ensure completions directory exists
echo "Installing photosort completion script..."
mkdir -pv "$LOCAL_COMPL_DIR" || true

# Link completion script
ln -sfv "$PHOTOSORT_COMPL_FILE" "$LOCAL_COMPL_LINK"

# Summary
echo ""
echo "✅ Completion script linked:"
echo "    $LOCAL_COMPL_LINK"
echo ""
echo "Source ~/.bashrc or restart terminal to enable completion."
