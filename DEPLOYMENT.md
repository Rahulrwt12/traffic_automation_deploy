# 🚀 Traffic Automation - Production Deployment Guide

## 📋 Table of Contents
- [Prerequisites](#prerequisites)
- [Server Requirements](#server-requirements)
- [Installation Steps](#installation-steps)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

---

## ✅ Prerequisites

### Required Software
- **Python 3.9+** (3.10 or 3.11 recommended)
- **pip** (Python package manager)
- **Git** (for cloning repository)
- **sudo/root access** (for installing system dependencies)

### Required Accounts & API Keys
1. **Webshare Proxy API** - Get API key from https://proxy.webshare.io/
   - Minimum: 100 proxies subscription
   - Cost: ~$50-100/month for 100 proxies

2. **Authentication Credentials** (if using QA environment)
   - HTTP Basic Auth username
   - HTTP Basic Auth password

---

## 💻 Server Requirements

### Recommended Specifications (for 50 concurrent proxies)
- **CPU**: 4-8 cores
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 50GB SSD (fast I/O for browser operations)
- **Bandwidth**: Unlimited or high limit (proxy traffic)
- **OS**: Ubuntu 20.04/22.04 LTS (recommended)

### Cloud Providers (Tested)
- ✅ **AWS EC2**: t3.xlarge (4 vCPU, 16GB RAM)
- ✅ **DigitalOcean**: Droplet 8GB/4vCPU
- ✅ **Linode**: Dedicated 8GB
- ✅ **Vultr**: High Frequency 8GB

### Memory Usage Estimates
```
Base system:          ~500MB
Python + deps:        ~500MB
Streamlit app:        ~200MB
Each Chromium:        ~200-400MB
-----------------------------------
50 browsers peak:     ~10-20GB (with pooling: ~4-8GB actual)
Recommended total:    8-16GB RAM
```

---

## 📦 Installation Steps

### Step 1: System Dependencies (Ubuntu/Debian)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and pip
sudo apt install -y python3 python3-pip python3-venv

# Install Playwright system dependencies (CRITICAL)
sudo apt install -y \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libxshmfence1
```

### Step 2: Clone Repository

```bash
# Clone your repository
git clone <your-repo-url>
cd Traffic_automation_Deploy

# OR if already downloaded, navigate to directory
cd /path/to/Traffic_automation_Deploy
```

### Step 3: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Step 4: Install Python Dependencies

```bash
# Install all requirements (pinned versions for stability)
pip install -r requirements.txt

# CRITICAL: Install Playwright browsers
playwright install chromium

# Install Playwright system dependencies
playwright install-deps chromium
```

### Step 5: Configure Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your actual credentials
nano .env
```

**Required values in `.env`:**
```bash
# REQUIRED: Webshare Proxy API Key
PROXY_API_KEY=your_actual_api_key_here

# REQUIRED if using QA environment
BROWSER_AUTH_USERNAME=your_username
BROWSER_AUTH_PASSWORD=your_password

# Optional: Override defaults
MAX_CONCURRENT_PROXIES=50
MAX_PROXIES=100
LOG_LEVEL=INFO
```

**IMPORTANT: Never commit `.env` to Git!**

### Step 6: Verify Configuration

```bash
# Check config.json exists
ls -la config.json

# Verify .env is loaded
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Proxy API Key:', 'SET' if os.getenv('PROXY_API_KEY') else 'NOT SET')"
```

---

## ⚙️ Configuration

### Production-Ready Settings (Already Optimized)

Your `config.json` is pre-configured for production with:
- ✅ **50 concurrent proxies** (max_concurrent_proxies: 50)
- ✅ **100 proxy pool** (max_proxies: 100)
- ✅ **Chromium headless** (stable in production)
- ✅ **Memory optimization** enabled
- ✅ **Resource monitoring** enabled (alerts at 85% RAM)
- ✅ **Browser pooling** (reduces memory usage)

### Customization Options

Edit `config.json` to adjust:

```json
{
  "parallel_mode": {
    "max_concurrent_proxies": 50,  // Adjust based on RAM
    "automated_batches": {
      "proxies_per_batch": 50,
      "delay_between_batches_minutes": 45.0
    }
  },
  "browser": {
    "headless": true,              // Must be true for production
    "browser_type": "chromium"     // Don't change (most stable)
  },
  "memory_optimization": {
    "browser_pool_size": 10,       // Increase for better performance
    "max_browser_idle_time_seconds": 300
  }
}
```

---

## 🚀 Running the Application

### Option 1: Direct Run (Testing)

```bash
# Activate virtual environment
source venv/bin/activate

# Run Streamlit app
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
```

### Option 2: Background Run (Production)

```bash
# Using nohup (simple)
nohup streamlit run app.py --server.port=8501 --server.address=0.0.0.0 > streamlit.log 2>&1 &

# Using screen (recommended)
screen -S traffic_bot
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
# Press Ctrl+A then D to detach
# To reattach: screen -r traffic_bot

# Using systemd (best for production)
# See systemd section below
```

### Option 3: Systemd Service (Recommended)

Create service file:
```bash
sudo nano /etc/systemd/system/traffic-bot.service
```

```ini
[Unit]
Description=Traffic Automation Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/Traffic_automation_Deploy
Environment="PATH=/path/to/Traffic_automation_Deploy/venv/bin"
ExecStart=/path/to/Traffic_automation_Deploy/venv/bin/streamlit run app.py --server.port=8501 --server.address=0.0.0.0
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable traffic-bot
sudo systemctl start traffic-bot
sudo systemctl status traffic-bot

# View logs
sudo journalctl -u traffic-bot -f
```

### Accessing the Dashboard

1. **Local Access**: http://localhost:8501
2. **Remote Access**: http://your-server-ip:8501
3. **With SSH Tunnel**: 
   ```bash
   ssh -L 8501:localhost:8501 user@your-server-ip
   # Then access: http://localhost:8501
   ```

---

## 📊 Monitoring & Maintenance

### Log Files

```bash
# Application log
tail -f traffic_bot.log

# Streamlit log (if using nohup)
tail -f streamlit.log

# System log (if using systemd)
sudo journalctl -u traffic-bot -f
```

### Resource Monitoring

Built-in monitoring in the app shows:
- CPU usage
- Memory usage
- Browser count
- Proxy health

**Critical Thresholds:**
- Memory > 85% → Warning logged
- CPU > 90% → Warning logged
- Memory > 95% → Consider reducing concurrent proxies

### Regular Maintenance Tasks

1. **Daily**:
   - Check dashboard for errors
   - Monitor resource usage
   - Verify proxies are working

2. **Weekly**:
   - Review `traffic_history.json` size
   - Clear old logs if needed
   - Check proxy health report

3. **Monthly**:
   - Update dependencies (test first!)
   - Review and optimize configuration
   - Analyze traffic statistics

### Backup Important Files

```bash
# Backup data files (before updates)
mkdir -p backups/$(date +%Y%m%d)
cp traffic_history.json backups/$(date +%Y%m%d)/
cp traffic_stats.json backups/$(date +%Y%m%d)/
cp bot_status.json backups/$(date +%Y%m%d)/
cp config.json backups/$(date +%Y%m%d)/

# Backup .env (securely)
cp .env backups/$(date +%Y%m%d)/.env
chmod 600 backups/$(date +%Y%m%d)/.env
```

---

## 🔧 Troubleshooting

### Issue: "Proxy API key not configured"

**Solution:**
```bash
# Check .env file exists
cat .env | grep PROXY_API_KEY

# Verify it's loaded
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('PROXY_API_KEY'))"

# Restart application
```

### Issue: "Browser startup timeout"

**Causes:**
- Missing Playwright browsers
- Missing system dependencies
- Insufficient RAM

**Solution:**
```bash
# Reinstall browsers
playwright install chromium --force

# Check system dependencies
playwright install-deps chromium

# Reduce concurrent browsers in config.json
# Change max_concurrent_proxies from 50 to 25
```

### Issue: High Memory Usage

**Solution:**
```bash
# 1. Check current usage
free -h
htop

# 2. Reduce concurrent proxies in config.json
"max_concurrent_proxies": 25  # Instead of 50

# 3. Increase browser pool size
"browser_pool_size": 15  # Instead of 10

# 4. Restart application
```

### Issue: "Excel file not found"

**Solution:**
```bash
# Upload Excel file through web interface
# OR place file manually:
cp your_file.xlsx /path/to/Traffic_automation_Deploy/
# Update config.json: "excel_file": "your_file.xlsx"
```

### Issue: Proxies Not Working

**Solution:**
```bash
# 1. Test API key
curl -H "Authorization: Token YOUR_API_KEY" https://proxy.webshare.io/api/v2/proxy/list/

# 2. Check proxy validation
# Look for validation logs in traffic_bot.log

# 3. Test single proxy manually
# Use dashboard to view proxy performance report
```

### Issue: Application Crashes

**Common causes:**
1. Out of memory → Reduce concurrent proxies
2. Network timeout → Check internet connection
3. Proxy failures → Check proxy subscription

**Debug steps:**
```bash
# Check logs
tail -100 traffic_bot.log

# Check system resources
free -h
df -h

# Restart with verbose logging
# Change in config.json: "log_level": "DEBUG"
```

---

## 🔒 Security Best Practices

1. **Never commit secrets**:
   ```bash
   # Ensure .gitignore includes
   echo ".env" >> .gitignore
   echo "config.json" >> .gitignore
   ```

2. **Restrict file permissions**:
   ```bash
   chmod 600 .env
   chmod 600 config.json
   ```

3. **Use firewall**:
   ```bash
   # Allow only SSH and application port
   sudo ufw allow 22/tcp
   sudo ufw allow 8501/tcp
   sudo ufw enable
   ```

4. **Keep system updated**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

5. **Regular backups** (see maintenance section)

---

## 📞 Support & Contact

**Issues:** Check logs first, then review this guide

**Performance:** Monitor resource usage and adjust config

**Updates:** Test in development before production

---

## ✨ Performance Optimization Tips

### For 8GB RAM Server (50 concurrent)
```json
{
  "parallel_mode": {
    "max_concurrent_proxies": 50,
    "max_concurrent_browser_starts": 10
  },
  "memory_optimization": {
    "browser_pool_size": 10,
    "cleanup_interval_seconds": 60
  },
  "resource_monitoring": {
    "max_memory_percent": 85.0
  }
}
```

### For 16GB RAM Server (100 concurrent)
```json
{
  "parallel_mode": {
    "max_concurrent_proxies": 100,
    "max_concurrent_browser_starts": 20
  },
  "memory_optimization": {
    "browser_pool_size": 20,
    "cleanup_interval_seconds": 30
  },
  "resource_monitoring": {
    "max_memory_percent": 90.0
  }
}
```

---

**Last Updated:** 2024
**Version:** Production-Ready v2.0

