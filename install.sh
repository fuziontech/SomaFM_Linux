#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/fuziontech/SomaFM_Linux.git"
INSTALL_DIR="${HOME}/.local/share/somafm"
SERVICE_FILE="${HOME}/.config/systemd/user/somafm.service"

info()  { printf '\033[1;34m::\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m::\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m::\033[0m %s\n' "$*" >&2; }
die()   { error "$@"; exit 1; }

# ---------------------------------------------------------------------------
# Distro detection
# ---------------------------------------------------------------------------
detect_distro() {
    if [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        echo "${ID}"
    else
        echo "unknown"
    fi
}

# Map derivative distros to their parent
normalize_distro() {
    local distro="$1"
    case "$distro" in
        fedora|rhel|centos|rocky|alma|nobara) echo "fedora" ;;
        ubuntu|debian|pop|linuxmint|elementary|zorin) echo "debian" ;;
        arch|manjaro|endeavouros|garuda) echo "arch" ;;
        opensuse*|sles) echo "opensuse" ;;
        *) echo "unknown" ;;
    esac
}

# ---------------------------------------------------------------------------
# Install system dependencies
# ---------------------------------------------------------------------------
install_system_deps() {
    local distro="$1"

    info "Installing system dependencies for ${distro}..."

    case "$distro" in
        fedora)
            sudo dnf install -y mpv python3-gobject gtk3 libappindicator-gtk3 git
            ;;
        debian)
            sudo apt-get update
            sudo apt-get install -y mpv python3-gi gir1.2-appindicator3-0.1 gir1.2-gtk-3.0 git
            ;;
        arch)
            sudo pacman -S --needed --noconfirm mpv python-gobject gtk3 libappindicator-gtk3 git
            ;;
        opensuse)
            sudo zypper install -y mpv python3-gobject gtk3 libappindicator-gtk3 git
            ;;
        *)
            die "Unsupported distribution. Please install these packages manually:
  - mpv
  - python3 + PyGObject (GTK3 bindings)
  - AppIndicator3 GIR bindings
  - git
Then re-run this script with: SKIP_SYSTEM_DEPS=1 bash install.sh"
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Clone or update the repository
# ---------------------------------------------------------------------------
install_repo() {
    if [[ -d "${INSTALL_DIR}/.git" ]]; then
        info "Updating existing installation..."
        git -C "${INSTALL_DIR}" pull --ff-only
    else
        info "Cloning SomaFM Linux to ${INSTALL_DIR}..."
        mkdir -p "$(dirname "${INSTALL_DIR}")"
        git clone "${REPO_URL}" "${INSTALL_DIR}"
    fi
}

# ---------------------------------------------------------------------------
# Install Python dependencies
# ---------------------------------------------------------------------------
install_python_deps() {
    info "Installing Python dependencies..."
    pip install --user -r "${INSTALL_DIR}/requirements.txt" 2>/dev/null \
        || pip install --break-system-packages --user -r "${INSTALL_DIR}/requirements.txt" \
        || warn "pip install failed — 'requests' may already be available via system packages."
}

# ---------------------------------------------------------------------------
# Create systemd user service
# ---------------------------------------------------------------------------
install_service() {
    info "Creating systemd user service..."

    mkdir -p "$(dirname "${SERVICE_FILE}")"

    cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=SomaFM Linux Internet Radio
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/env python3 ${INSTALL_DIR}/somafm.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable somafm.service
    info "Service installed and enabled."
}

# ---------------------------------------------------------------------------
# Start the service
# ---------------------------------------------------------------------------
start_service() {
    if [[ -n "${DISPLAY:-}" ]] || [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
        info "Starting SomaFM..."
        systemctl --user start somafm.service
        info "SomaFM is running! Look for the tray icon."
    else
        warn "No graphical session detected — skipping auto-start."
        warn "Start it later with: systemctl --user start somafm"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    info "SomaFM Linux Installer"
    echo

    local raw_distro
    raw_distro="$(detect_distro)"
    local distro
    distro="$(normalize_distro "${raw_distro}")"

    info "Detected distro: ${raw_distro} (family: ${distro})"

    # Install system dependencies (skip if requested)
    if [[ "${SKIP_SYSTEM_DEPS:-0}" != "1" ]]; then
        install_system_deps "${distro}"
    else
        warn "Skipping system dependency installation (SKIP_SYSTEM_DEPS=1)."
    fi

    install_repo
    install_python_deps
    install_service
    start_service

    echo
    info "Installation complete!"
    info "  Manage with: systemctl --user {start,stop,status} somafm"
    info "  Uninstall:   systemctl --user disable --now somafm && rm -rf ${INSTALL_DIR} ${SERVICE_FILE}"
}

main "$@"
