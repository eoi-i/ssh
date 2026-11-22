# ملاحظات المشروع — مشروع 2 (خادم طرفية SSH بلغة بايثون)

## كيف يُشغل محلياً
- البيئة: ألباين لينكس (proot)، بايثون 3.12، الربط مسموح فقط على `127.0.0.1`.
- التبعيات تُثبّت في بيئة افتراضية: `python3 -m venv venv && venv/bin/pip install -r requirements.txt`
- التشغيل: `venv/bin/python ssh_server.py [--config config.json] [--host 0.0.0.0] [--port 2222]`
- الربط افتراضياً على `0.0.0.0:2222` (للتوافق مع Docker/Fly.io). محلياً استخدم `127.0.0.1`.

## الملفات الأساسية
- `ssh_server.py`: الكود الرئيسي (خادم SSH عبر `paramiko`، مصادقة كلمة مرور/مفتاح عام، PTY تفاعلي، سجلات).
- `config.json`: إعدادات المنفذ، المستخدمين، الشعار، الشل، ملف السجل.
- `requirements.txt`: `paramiko>=5.0.0`.
- `Dockerfile`: صورة Docker للنشر على Fly.io.
- `fly.toml`: إعدادات Fly.io (يعرض المنفذ 2222 عبر TCP).
- `host_key.pem`: مفتاح المضيف يُنشأ تلقائياً عند التشغيل الأول.

## النشر على Fly.io
1. ثبّت أداة `flyctl` من https://fly.io/docs/hands-on/install/
2. سجّل دخولك: `fly auth login`
3. أنشئ التطبيق: `fly apps create python-ssh-terminal` (غيّر الاسم في `fly.toml` إن أردت)
4. انشر: `fly deploy`
5. بعد النشر، يكون العنوان: `python-ssh-terminal.fly.dev` على المنفذ `2222`

## الاتصال من تطبيقات الجوال (SSH)
- المضيف: `python-ssh-terminal.fly.dev`
- المنفذ: `2222`
- اسم المستخدم: `admin` (أو أي مستخدم مضاف في `config.json`)
- كلمة المرور: `admin123` (غيّرها في الإنتاج!)
- تطبيقات مدعومة: Termius (iOS/Android)، JuiceSSH (Android)، ConnectBot (Android)، iTerminal (iOS)، أو أي عميل SSH آخر.

## ملاحظات تقنية
- يُستخدم `os.fork()` + `pty.openpty()` لتوفير شل تفاعلي حقيقي لكل جلسة SSH.
- الربط على `0.0.0.0` مطلوب داخل حاوية Docker/Fly.io.
- كلمات المرور تدعم النص العادي أو التجزئة ببادئة `sha256:` في `config.json`.
- السجلات تُكتب إلى `stdout` وإلى `ssh_server.log` (تدوير تلقائي).

## تحذير أمني
خادم تعليمي/تطويري. للإنتاج: فعّل المصادقة بالمفاتيح العامة فقط، كلمات مرور قوية، جدار ناري، وراقب السجلات.
