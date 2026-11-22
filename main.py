#!/usr/bin/env python3
"""Python bootstrapper for a hardened OpenSSH terminal service on Fly.io."""
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path

USER = os.getenv("SSH_USER", "terminal")
PORT = int(os.getenv("PORT", "2222"))
HOME = Path(f"/home/{USER}")
SSH_DIR = HOME / ".ssh"
AUTHORIZED_KEYS = os.getenv("SSH_AUTHORIZED_KEYS", "").strip()

def run(*args):
    subprocess.run(args, check=True)

def main():
    if os.geteuid() != 0:
        raise SystemExit("Startup must run as root inside the container.")
    if not AUTHORIZED_KEYS:
        raise SystemExit(
            "SSH_AUTHORIZED_KEYS is empty. Set it as a Fly secret containing "
            "your public SSH key (for example, the full contents of id_ed25519.pub)."
        )
    if "\n" not in AUTHORIZED_KEYS and not AUTHORIZED_KEYS.startswith(
        ("ssh-ed25519 ", "ssh-rsa ", "ecdsa-sha2-", "sk-ssh-ed25519@", "sk-ecdsa-sha2-")
    ):
        raise SystemExit("SSH_AUTHORIZED_KEYS does not look like an SSH public key.")

    try:
        pwd.getpwnam(USER)
    except KeyError:
        run("useradd", "--create-home", "--shell", "/bin/bash", "--groups", "sudo", USER)
    run("usermod", "--shell", "/bin/bash", USER)
    run("install", "-d", "-m", "700", "-o", USER, "-g", USER, str(SSH_DIR))
    key_file = SSH_DIR / "authorized_keys"
    key_file.write_text(AUTHORIZED_KEYS + "\n", encoding="utf-8")
    run("chown", f"{USER}:{USER}", str(key_file))
    run("chmod", "600", str(key_file))

    # The terminal account has administrative access through sudo.
    sudoers = Path("/etc/sudoers.d/terminal")
    sudoers.write_text(f"{USER} ALL=(ALL:ALL) NOPASSWD:ALL\n", encoding="utf-8")
    run("chmod", "440", str(sudoers))
    run("visudo", "-cf", str(sudoers))

    Path("/run/sshd").mkdir(parents=True, exist_ok=True)
    run("ssh-keygen", "-A")

    config = f"""
Port {PORT}
AddressFamily any
ListenAddress 0.0.0.0
PermitRootLogin no
PubkeyAuthentication yes
AuthenticationMethods publickey
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
UsePAM no
AllowUsers {USER}
AuthorizedKeysFile .ssh/authorized_keys
Subsystem sftp internal-sftp
X11Forwarding no
AllowTcpForwarding no
AllowAgentForwarding no
PermitTunnel no
GatewayPorts no
ClientAliveInterval 60
ClientAliveCountMax 3
LoginGraceTime 30
MaxAuthTries 3
MaxSessions 10
PrintMotd no
"""
    Path("/etc/ssh/sshd_config").write_text(config.strip() + "\n", encoding="utf-8")
    run("/usr/sbin/sshd", "-t")
    print(f"SSH terminal ready on 0.0.0.0:{PORT} for user {USER}", flush=True)
    os.execv("/usr/sbin/sshd", ["sshd", "-D", "-e"])

if __name__ == "__main__":
    main()
