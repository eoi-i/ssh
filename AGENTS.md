# ملاحظات المشروع — مشروع 2 (خادم طرفية SSH بلغة بايثون)

## كيف يُشغل محلياً
- البيئة: ألباين لينكس (proot)، بايثون 3.12.
- التبعيات: `python3 -m venv venv && venv/bin/pip install -r requirements.txt`
- التشغيل: `venv/bin/python ssh_server.py [--config config.json] [--host 0.0.0.0] [--port 2222]`
- الربط افتراضياً على `0.0.0.0:2222` (للتوافق مع Docker/Fly.io). محلياً استخدم `127.0.0.1`.

## الملفات الأساسية
- `ssh_server.py`: الكود الرئيسي (خادم SSH عبر `paramiko`، مصادقة كلمة مرور/مفتاح عام، PTY تفاعلي، سجلات).
- `config.json`: إعدادات المنفذ، المستخدمين، الشعار، الشل، ملف السجل.
- `requirements.txt`: `paramiko>=5.0.0`.
- `Dockerfile`: صورة Docker للنشر على Fly.io.
- `fly.toml`: إعدادات Fly.io للتطبيق `ssh-8zjrsa` (يعرض المنفذ 2222 عبر TCP).
- `host_key.pem`: مفتاح المضيف يُنشأ تلقائياً عند التشغيل الأول.

## النشر على Fly.io (التطبيق موجود أصلاً باسم ssh-8zjrsa)
**لا تستخدم `fly launch`** — التطبيق موجود أصلاً على Fly.io.
- من متصفحك: اذهب إلى `fly.io/apps/ssh-8zj` واضغط **Deploy** أو **"Retry from latest commit (main)"**.
- أو من سطر الأوامر (إذا ثبتت flyctl): `fly auth login && fly deploy --app ssh-8zjrsa`
- بعد النشر، العنوان: `ssh-8zjrsa.fly.dev` على المنفذ `2222`

## الاتصال من تطبيقات الجوال (SSH)
- المضيف: `ssh-8zjrsa.fly.dev`
- المنفذ: `2222`
- اسم المستخدم: `admin`
- كلمة المرور: `admin123` (غيّرها في الإنتاج!)
- تطبيقات مدعومة: Termius (iOS/Android)، JuiceSSH (Android)، ConnectBot (Android)، iTerminal (iOS).

## ملاحظات تقنية
- يُستخدم `os.fork()` + `pty.openpty()` لتوفير شل تفاعلي حقيقي لكل جلسة SSH.
- الربط على `0.0.0.0` مطلوب داخل حاوية Docker/Fly.io.
- السجلات تُكتب إلى `stdout` وإلى `ssh_server.log`.

## تحذير أمني
خادم تعليمي/تطويري. للإنتاج: فعّل المصادقة بالمفاتيح العامة فقط، كلمات مرور قوية، جدار ناري، وراقب السجلات.
