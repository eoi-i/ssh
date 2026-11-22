#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Professional Linux Terminal SSH Server
======================================
خادم طرفية (Terminal Server) مبني بلغة بايثون يعمل على لينكس،
ويستقبل اتصالات عبر SSH ويوفر شل تفاعلي حقيقي (PTY) لكل جلسة.

بناءً على مكتبة paramiko. مخصص للأغراض التعليمية والاستخدام المصرح به.

طريقة التشغيل:
    python3 ssh_server.py [--config config.json] [--port 2222]

تحذير أمني:
    هذا خادم تطوير/تعليمي. للاستخدام الإنتاجي فعّل المصادقة بالمفاتيح
    (public-key)، وكلمات مرور قوية، وحمايته بجدار ناري (firewall).
"""

import argparse
import fcntl
import hashlib
import json
import logging
import logging.handlers
import os
import pty
import select
import signal
import socket
import struct
import sys
import termios
import threading
import time
import tty

import paramiko
from paramiko import (
    AUTH_SUCCESSFUL,
    AUTH_FAILED,
    OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED,
    OPEN_SUCCEEDED,
    ServerInterface,
    Transport,
)

DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 2222,
    "host_key_key": "host_key.pem",
    "host_key_file": "host_key.pem",
    "banner": "\r\nمرحباً بك في خادم الطرفية الاحترافي المبني بلغة بايثون\r\nاكتب 'exit' للخروج.\r\n",
    "users": {
        "admin": "admin123"
    },
    "shell": "/bin/sh",
    "auth_timeout": 30,
    "channel_timeout": 300,
    "max_auth_tries": 3,
    "log_file": "ssh_server.log",
    "log_level": "INFO",
    "allow_password_auth": True,
    "allow_key_auth": False,
    "authorized_keys_file": "authorized_keys",
    "ssh_version": "SSH-2.0-PythonTerminalServer_1.0",
}

logger = logging.getLogger("ssh_server")


class TerminalSession:
    """إدارة جلسة SSH واحدة مع شل تفاعلي مرتبط بـ PTY."""

    def __init__(self, transport, channel, config, cols=80, rows=24):
        self.transport = transport
        self.channel = channel
        self.config = config
        self.shell = config.get("shell", "/bin/sh")
        self.cols = cols
        self.rows = rows
        self.master_fd = None
        self.slave_fd = None
        self.pid = None
        self._closed = False
        self._lock = threading.Lock()

    def start(self):
        try:
            # إنشاء PTY وهمي للشل التفاعلي
            self.master_fd, self.slave_fd = pty.openpty()

            # ضبط أبعاد النافذة (terminal size) إن توفر
            try:
                winsize = struct.pack("HHHH", self.rows, self.cols, 0, 0)
                fcntl.ioctl(self.slave_fd, termios.TIOCSWINSZ, winsize)
            except Exception:
                pass

            self.pid = os.fork()
            if self.pid == 0:
                # العملية الفرعية: تشغيل الشل مرتبط بـ slave PTY
                os.close(self.master_fd)
                os.setsid()
                os.dup2(self.slave_fd, 0)  # stdin
                os.dup2(self.slave_fd, 1)  # stdout
                os.dup2(self.slave_fd, 2)  # stderr
                if self.slave_fd > 2:
                    os.close(self.slave_fd)
                os.environ["TERM"] = os.environ.get("TERM", "xterm-256color")
                os.execvp(self.shell, [self.shell])
                os._exit(127)
            else:
                # العملية الأم: التحويل بين قناة SSH و master PTY
                os.close(self.slave_fd)
                flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
                fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

                banner = self.config.get("banner", "")
                if banner:
                    try:
                        self.channel.send(banner.encode("utf-8", errors="replace"))
                    except Exception:
                        pass

                self._relay()
        except Exception:
            logger.exception("TerminalSession error")
        finally:
            self.close()

    def _relay(self):
        """تحويل البيانات بين قناة SSH و PTY الرئيسي."""
        channel = self.channel
        master_fd = self.master_fd
        try:
            channel.settimeout(0.2)
        except Exception:
            pass

        while not self._closed:
            try:
                rlist, _, _ = select.select([channel, master_fd], [], [], 0.5)
            except (OSError, ValueError):
                break

            if channel in rlist:
                try:
                    data = channel.recv(4096)
                except (socket.timeout, Exception):
                    data = b""
                if not data:
                    break
                try:
                    os.write(master_fd, data)
                except OSError:
                    break

            if master_fd in rlist:
                try:
                    data = os.read(master_fd, 4096)
                except OSError:
                    data = b""
                if not data:
                    break
                try:
                    channel.send(data)
                except Exception:
                    break

            if self.pid is not None:
                try:
                    wpid, _status = os.waitpid(self.pid, os.WNOHANG)
                    if wpid != 0:
                        break
                except ChildProcessError:
                    break

        self.close()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            if self.master_fd is not None:
                try:
                    os.close(self.master_fd)
                except OSError:
                    pass
        except Exception:
            pass
        try:
            if self.channel is not None and not self.channel.closed:
                self.channel.close()
        except Exception:
            pass
        try:
            if self.pid is not None:
                try:
                    os.waitpid(self.pid, 0)
                except ChildProcessError:
                    pass
        except Exception:
            pass
        logger.info("انتهت جلسة SSH")


class SSHServer(ServerInterface):
    """واجهة خادم SSH من paramiko: المصادقة وقبول القنوات."""

    def __init__(self, config):
        self.config = config
        self.users = config.get("users", {})
        self.max_auth_tries = config.get("max_auth_tries", 3)
        self.auth_tries = {}
        self.allow_password = config.get("allow_password_auth", True)
        self.allow_key = config.get("allow_key_auth", False)
        self.auth_keys = self._load_authorized_keys()

    def _load_authorized_keys(self):
        keys = {}
        path = self.config.get("authorized_keys_file", "authorized_keys")
        if not os.path.exists(path):
            return keys
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        keys[parts[1]] = line
        except Exception as exc:
            logger.warning("تعذر تحميل authorized_keys: %s", exc)
        return keys

    def check_auth_password(self, username, password):
        key = (username, "password")
        self.auth_tries[key] = self.auth_tries.get(key, 0) + 1
        if self.auth_tries[key] > self.max_auth_tries:
            logger.warning("تجاوزت محاولات المصادقة لـ %s", username)
            return AUTH_FAILED

        if not self.allow_password:
            return AUTH_FAILED

        expected = self.users.get(username)
        if expected is None:
            return AUTH_FAILED

        if isinstance(expected, str) and expected.startswith("sha256:"):
            expected_hash = expected.split(":", 1)[1]
            if hashlib.sha256(password.encode("utf-8")).hexdigest() == expected_hash:
                logger.info("ناجحة: مصادقة كلمة مرور لـ %s", username)
                return AUTH_SUCCESSFUL
        else:
            if expected == password:
                logger.info("ناجحة: مصادقة كلمة مرور لـ %s", username)
                return AUTH_SUCCESSFUL

        logger.warning("فشلت مصادقة كلمة مرور لـ %s", username)
        return AUTH_FAILED

    def check_auth_publickey(self, username, key):
        if not self.allow_key:
            return AUTH_FAILED
        key_base64 = key.get_base64()
        if key_base64 in self.auth_keys:
            logger.info("ناجحة: مصادقة المفتاح العام لـ %s", username)
            return AUTH_SUCCESSFUL
        logger.warning("فشلت مصادقة المفتاح العام لـ %s", username)
        return AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return OPEN_SUCCEEDED
        return OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel):
        return True

    def check_channel_pty_request(self, channel, term, width, height,
                                  pixelwidth, pixelheight, modes):
        return True

    def check_channel_exec_request(self, channel, command):
        return True

    def check_channel_window_change_request(self, channel, width, height,
                                            pixelwidth, pixelheight):
        return True


def generate_host_key(path):
    """إنشاء مفتاح مضيف (RSA) إن لم يكن موجوداً، أو تحميله."""
    if os.path.exists(path):
        logger.info("مفتاح المضيف موجود: %s", path)
        return paramiko.RSAKey.from_private_key_file(path)
    logger.info("إنشاء مفتاح مضيف RSA جديد: %s", path)
    key = paramiko.RSAKey.generate(2048)
    key.write_private_key_file(path)
    os.chmod(path, 0o600)
    return key


def handle_client(client_sock, addr, config, host_key):
    """معالجة اتصال SSH وارد من عميل واحد."""
    logger.info("اتصال جديد من %s:%d", addr[0], addr[1])
    transport = Transport(client_sock)
    transport.add_server_key(host_key)
    transport.local_version = config.get("ssh_version", "SSH-2.0-PythonTerminalServer_1.0")

    server = SSHServer(config)
    try:
        transport.start_server(server=server)
    except Exception as exc:
        logger.error("فشل التفاوض على SSH من %s: %s", addr[0], exc)
        try:
            client_sock.close()
        except Exception:
            pass
        return

    # انتظار اكتمال المصادقة مع مهلة
    auth_deadline = time.time() + config.get("auth_timeout", 30)
    while not transport.is_authenticated():
        if time.time() > auth_deadline:
            logger.warning("انتهت مهلة المصادقة لـ %s", addr[0])
            try:
                transport.close()
            except Exception:
                pass
            return
        time.sleep(0.2)

    # فتح قناة جلسة
    try:
        channel = transport.accept(timeout=config.get("channel_timeout", 300))
    except Exception as exc:
        logger.error("خطأ في قبول القناة من %s: %s", addr[0], exc)
        try:
            transport.close()
        except Exception:
            pass
        return

    if channel is None:
        logger.warning("لم تُفتح قناة من %s", addr[0])
        try:
            transport.close()
        except Exception:
            pass
        return

    logger.info("جلسة مصادقة ناجحة من %s:%d", addr[0], addr[1])
    session = TerminalSession(transport, channel, config)
    session.start()
    try:
        transport.close()
    except Exception:
        pass
    logger.info("انتهى الاتصال من %s:%d", addr[0], addr[1])


def load_config(path):
    config = dict(DEFAULT_CONFIG)
    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config.update(user_config)
    return config


def setup_logging(config):
    level = getattr(logging, str(config.get("log_level", "INFO")).upper(), logging.INFO)
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    log_file = config.get("log_file")
    if log_file:
        fh = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)


def main():
    parser = argparse.ArgumentParser(description="خادم طرفية SSH احترافي مبني بلغة بايثون")
    parser.add_argument("--config", default="config.json", help="مسار ملف الإعدادات JSON")
    parser.add_argument("--host", default=None, help="عنوان الربط (الافتراضي: من الإعدادات أو 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="المنفذ (الافتراضي: من الإعدادات أو 2222)")
    parser.add_argument("--generate-key", action="store_true",
                        help="إنشاء مفتاح المضيف والخروج")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(config)

    if args.generate_key:
        generate_host_key(config.get("host_key_file", "host_key.pem"))
        return

    host = args.host or config.get("host", "127.0.0.1")
    port = args.port or config.get("port", 2222)

    host_key = generate_host_key(config.get("host_key_file", "host_key.pem"))

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind((host, port))
    except OSError as exc:
        logger.error("لا يمكن الربط على %s:%d — %s", host, port, exc)
        sys.exit(1)
    server_sock.listen(128)
    logger.info("خادم الطرفية SSH يعمل على %s:%d", host, port)
    logger.info("لإيقاف الخادم اضغط Ctrl+C")

    running = True

    def stop(signum, frame):
        nonlocal running
        running = False
        logger.info("تم استلام إشارة الإيقاف")

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    server_sock.settimeout(1.0)
    threads = []

    try:
        while running:
            try:
                client_sock, addr = server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            client_sock.settimeout(30)
            t = threading.Thread(
                target=handle_client,
                args=(client_sock, addr, config, host_key),
                daemon=True,
            )
            t.start()
            threads.append(t)
    finally:
        server_sock.close()
        for t in threads:
            t.join(timeout=5)
        logger.info("توقف الخادم")


if __name__ == "__main__":
    main()
