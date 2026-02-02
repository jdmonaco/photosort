#!/usr/bin/env bash
# Bash completion script for photosort
# 
# Installation:
#   Source this file in your .bashrc or place it in /etc/bash_completion.d/
#   Or install via: photosort --install-completion
#
# Usage: 
#   source photosort-completion.bash
#   # or
#   sudo cp photosort-completion.bash /etc/bash_completion.d/photosort

_photosort_completion() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    # All available options
    opts="--source -s --dest -d --dry-run -n --copy -c --verbose -v 
          --mode -m --group -g --timezone --tz --no-convert-videos 
          --version -V --help -h --install-completion"

    # Handle completion based on previous argument
    case "${prev}" in
        # Directory completion for source and dest options
        --source|-s|--dest|-d)
            COMPREPLY=($(compgen -d -- "${cur}"))
            return 0
            ;;
        
        # File mode completion (common octal modes)
        --mode|-m)
            local modes="644 664 600 755 744 640 660"
            COMPREPLY=($(compgen -W "${modes}" -- "${cur}"))
            return 0
            ;;
        
        # Group completion (system groups)
        --group|-g)
            if command -v getent >/dev/null 2>&1; then
                local groups=$(getent group | cut -d: -f1)
                COMPREPLY=($(compgen -W "${groups}" -- "${cur}"))
            else
                # Fallback for macOS and systems without getent
                local common_groups="staff wheel users admin dialout cdrom floppy audio dip video plugdev netdev lpadmin scanner"
                COMPREPLY=($(compgen -W "${common_groups}" -- "${cur}"))
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
            COMPREPLY=($(compgen -W "${timezones}" -- "${cur}"))
            return 0
            ;;
    esac

    # Positional argument completion
    case "${COMP_CWORD}" in
        1)
            # First positional arg: source directory
            COMPREPLY=($(compgen -d -- "${cur}"))
            # Also include options if user starts typing --
            if [[ "${cur}" == -* ]]; then
                COMPREPLY+=($(compgen -W "${opts}" -- "${cur}"))
            fi
            return 0
            ;;
        2)
            # Second positional arg: dest directory (only if first arg wasn't an option)
            if [[ "${COMP_WORDS[1]}" != -* ]]; then
                COMPREPLY=($(compgen -d -- "${cur}"))
                return 0
            fi
            # Otherwise fall through to option completion
            ;;
    esac

    # Default: complete with available options
    if [[ "${cur}" == -* ]]; then
        COMPREPLY=($(compgen -W "${opts}" -- "${cur}"))
        return 0
    fi

    # If no options matched, try directory completion
    COMPREPLY=($(compgen -d -- "${cur}"))
}

# Register the completion function
complete -F _photosort_completion photosort

# Export for use in other scripts
export -f _photosort_completion