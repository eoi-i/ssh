FROM python:3.12-slim

WORKDIR /app

# تثبيت التبعيات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كود الخادم والإعدادات
COPY ssh_server.py config.json README.md AGENTS.md ./

# منفذ SSH الداخلي (Fly.io يوجه المرور الخارجي إليه)
EXPOSE 2222

# تشغيل الخادم على جميع الواجهات الداخلية حتى يصله المرور من Fly.io
CMD ["python3", "ssh_server.py", "--host", "0.0.0.0", "--port", "2222"]
