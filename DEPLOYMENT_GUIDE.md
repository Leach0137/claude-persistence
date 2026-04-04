# Claude Persistence Server - Production Deployment Guide

## Files to Update in Your GitHub Repository

You need to add/update these files in your `claude-persistence` repository:

### 1. requirements.txt
```
Flask==3.0.0
anthropic==0.18.1
gunicorn==21.2.0
python-dotenv==1.0.0
```

### 2. Procfile (new file)
```
web: gunicorn --bind 0.0.0.0:$PORT --workers 4 --timeout 120 app:app
```

### 3. gunicorn.conf.py (optional but recommended)
```python
import multiprocessing
import os

bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

workers = 4
worker_class = 'sync'
worker_connections = 1000
timeout = 120
keepalive = 5

accesslog = '-'
errorlog = '-'
loglevel = 'info'
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

proc_name = 'claude-persistence-server'
daemon = False
```

If using this config file, update Procfile to:
```
web: gunicorn -c gunicorn.conf.py app:app
```

## Deployment Steps

1. **Push files to GitHub:**
   ```bash
   git add requirements.txt Procfile gunicorn.conf.py
   git commit -m "Add Gunicorn for production deployment"
   git push origin main
   ```

2. **Railway will auto-deploy** when it detects the changes

3. **Verify deployment:**
   - Check logs show "Booting worker" messages instead of Flask dev server warnings
   - Should see: `Starting gunicorn 21.2.0`
   - Status should remain "Active" without crashes

## Why This Fixes the Issue

- **Gunicorn** is a production-grade WSGI server
- **Multiple workers** (4) handle concurrent requests properly
- **Thread-safe** for multiple Claude instances accessing simultaneously
- **Proper timeouts** prevent hanging requests
- **Better logging** for debugging
- **Auto-restart workers** if they crash

## Alternative: If You Want Minimal Changes

Just update `Procfile` with:
```
web: gunicorn --bind 0.0.0.0:$PORT app:app
```

This gives you production-ready deployment with default Gunicorn settings.

## Expected Log Output After Deployment

You should see:
```
Starting gunicorn 21.2.0
Listening at: http://0.0.0.0:5000
Using worker: sync
Booting worker with pid: 123
Booting worker with pid: 124
Booting worker with pid: 125
Booting worker with pid: 126
```

No more "development server" warnings!
