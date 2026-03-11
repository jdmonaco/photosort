# Bash completion for photosort
# Install: photosort completion bash --install
# Or: photosort completion bash > ~/.local/share/bash-completion/completions/photosort

# Helper: complete directories only (handles spaces correctly)
_photosort_complete_dirs() {
    local cur="$1"
    compopt -o filenames -o nospace
    mapfile -t COMPREPLY < <(compgen -d -- "$cur")
}

_photosort_completions() {
    local cur prev words cword
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    words=("${COMP_WORDS[@]}")
    cword="$COMP_CWORD"

    # All available options
    local opts="--source -s --dest -d --dry-run -n --copy -c --verbose -v
                --mode -m --group -g --timezone --tz --no-convert-videos
                --yes -y --version -V --help -h"

    # Handle 'completion' subcommand
    local subcmd=""
    if [[ "$cword" -ge 1 ]]; then
        subcmd="${words[1]}"
    fi

    if [[ "$subcmd" == "completion" ]]; then
        case "$cword" in
            2)
                COMPREPLY=($(compgen -W "bash" -- "$cur"))
                ;;
            *)
                if [[ "$cur" == -* ]]; then
                    COMPREPLY=($(compgen -W "--install --path" -- "$cur"))
                fi
                ;;
        esac
        return 0
    fi

    # Handle completion based on previous argument
    case "${prev}" in
        # Directory completion for source and dest options
        --source|-s|--dest|-d)
            _photosort_complete_dirs "$cur"
            return 0
            ;;

        # File mode completion (common octal modes)
        --mode|-m)
            COMPREPLY=($(compgen -W "644 664 600 755 744 640 660" -- "$cur"))
            return 0
            ;;

        # Group completion (system groups)
        --group|-g)
            if command -v dscl >/dev/null 2>&1; then
                # macOS: use dscl for group listing
                local groups
                groups=$(dscl . -list /Groups 2>/dev/null)
                COMPREPLY=($(compgen -W "$groups" -- "$cur"))
            elif command -v getent >/dev/null 2>&1; then
                # Linux: use getent
                local groups
                groups=$(getent group | cut -d: -f1)
                COMPREPLY=($(compgen -W "$groups" -- "$cur"))
            fi
            return 0
            ;;

        # Timezone completion (common timezones)
        --timezone|--tz)
            local timezones="America/New_York America/Los_Angeles America/Chicago
                           America/Denver America/Phoenix America/Anchorage
                           America/Honolulu America/Toronto America/Vancouver
                           Europe/London Europe/Berlin Europe/Paris Europe/Rome
                           Europe/Madrid Europe/Stockholm Europe/Zurich
                           Asia/Tokyo Asia/Shanghai Asia/Kolkata Asia/Dubai
                           Australia/Sydney Australia/Melbourne Australia/Perth
                           Pacific/Auckland UTC"
            COMPREPLY=($(compgen -W "$timezones" -- "$cur"))
            return 0
            ;;
    esac

    # Position 1: subcommands or positional source directory
    if [[ "$cword" -eq 1 ]]; then
        if [[ "$cur" == -* ]]; then
            COMPREPLY=($(compgen -W "$opts" -- "$cur"))
        else
            # Offer 'completion' subcommand and directory completion
            local subcmds="completion"
            COMPREPLY=($(compgen -W "$subcmds" -- "$cur"))
            local dirs
            mapfile -t dirs < <(compgen -d -- "$cur")
            COMPREPLY+=("${dirs[@]}")
        fi
        return 0
    fi

    # Position 2: dest directory (only if first arg was a positional path)
    if [[ "$cword" -eq 2 && "${words[1]}" != -* && "${words[1]}" != "completion" ]]; then
        _photosort_complete_dirs "$cur"
        return 0
    fi

    # Default: complete with available options
    if [[ "$cur" == -* ]]; then
        COMPREPLY=($(compgen -W "$opts" -- "$cur"))
        return 0
    fi

    # Fallback: directory completion
    _photosort_complete_dirs "$cur"
}

# Register completion
complete -F _photosort_completions photosort
