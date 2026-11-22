# Fly.io Linux SSH Terminal

A Debian Linux terminal exposed through SSH on TCP port **2222**. Python prepares the account and SSH configuration; OpenSSH provides the standard SSH and SFTP protocols for compatibility with mobile SSH clients.

## Included

- Interactive Bash shell with PTY support
- SFTP subsystem
- Public-key-only authentication
- `terminal` user (no direct root login)
- `sudo` administrative access
- TCP port 2222, raw TCP passthrough

## 1. Create an SSH key on your phone or computer

Use an SSH app's key generator, or OpenSSH:

```bash
ssh-keygen -t ed25519 -C "fly-linux-terminal"
```

Copy the **public** key (the line in `id_ed25519.pub`). Never upload or share the private key.

## 2. Set the public key as a Fly secret

From this project directory, run:

```bash
fly secrets set SSH_AUTHORIZED_KEYS="PASTE_YOUR_PUBLIC_KEY_HERE" -a YOUR_FLY_APP_NAME
```

Replace the two values with your public key and actual Fly app name. This is a public key, not a password or private key.

## 3. Deploy

Set `app` in `fly.toml` to the exact Fly app name, then:

```bash
fly deploy
```

Ensure the app has a dedicated public IPv4 address for raw SSH/TCP access:

```bash
fly ips allocate-v4 -a YOUR_FLY_APP_NAME
```

A shared IPv4 may not route non-HTTP, non-TLS SSH traffic. A dedicated IPv4 is the reliable public endpoint for raw TCP services.

## 4. Connect from a phone or computer

In Termius, JuiceSSH, ConnectBot, or any OpenSSH client:

- Host: `YOUR_FLY_APP_NAME.fly.dev` (or the app's dedicated IPv4)
- Port: `2222`
- Username: `terminal`
- Authentication: the private key matching the public key you uploaded
- Password: leave empty

OpenSSH example:

```bash
ssh -p 2222 terminal@YOUR_FLY_APP_NAME.fly.dev
```

SFTP example:

```bash
sftp -P 2222 terminal@YOUR_FLY_APP_NAME.fly.dev
```

After login, use `sudo` for administrative commands, for example:

```bash
sudo apt-get update
sudo apt-get install htop
```

## Security and persistence notes

- Password authentication and root SSH login are disabled.
- The `terminal` user has passwordless sudo. Anyone holding its private SSH key therefore has full administrative control of this container. Protect the key and rotate it immediately if exposed.
- The container filesystem is ephemeral unless you explicitly configure and mount a Fly Volume. Files installed or created inside the container can be lost when the Machine is replaced. This starter intentionally does not create a persistent volume.
- SSH host keys are generated at startup. Without persistent storage, the host fingerprint can change after a Machine replacement. Verify a changed fingerprint before accepting it.
- This provides a Linux userland inside a Debian container, not a full virtual machine or privileged host. Kernel modules, systemd, nested virtualization, and host-level administration are not provided.
- Fly.io bills for running Machines and dedicated IP resources according to its current pricing.
