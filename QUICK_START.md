# ⚡ Quick Start Guide - Traffic Automation

**Get up and running in 5 minutes!**

---

## 🎯 Prerequisites

- Ubuntu 20.04/22.04 LTS (or similar Linux)
- 8GB+ RAM
- Python 3.9+
- Webshare proxy API key

---

## 🚀 Installation (Copy-Paste Commands)

```bash
# 1. Navigate to project directory
cd /path/to/Traffic_automation_Deploy

# 2. Install system dependencies
sudo apt update && sudo apt install -y python3 python3-pip python3-venv \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2

# 3. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Install Playwright browsers
playwright install chromium
playwright install-deps chromium

# 6. Configure environment
cp .env.example .env
nano .env  # Edit with your credentials

# 7. Start application
./start.sh
```

---

## ⚙️ Configuration (.env file)

Edit `.env` file with your credentials:

```bash
# REQUIRED
PROXY_API_KEY=your_webshare_api_key_here

# REQUIRED for QA environment
BROWSER_AUTH_USERNAME=your_username
BROWSER_AUTH_PASSWORD=your_password

# Optional (defaults are already optimized)
MAX_CONCURRENT_PROXIES=50
MAX_PROXIES=100
LOG_LEVEL=INFO
PORT=8501
```

---

## 📊 Access Dashboard

**Local:** http://localhost:8501  
**Remote:** http://your-server-ip:8501

---

## 🎮 Usage

1. **Upload Excel File**
   - Click "Excel File Upload" in sidebar
   - Upload file with product URLs
   - Click "Save & Apply Excel File"

2. **Configure Settings**
   - Select proxy count (10, 25, 50, or 100)
   - Choose run mode
   - Adjust delays if needed

3. **Start Bot**
   - Click "Start Bot" button
   - Monitor progress in dashboard
   - View logs in "Live Log Viewer"

4. **Stop Bot**
   - Click "Stop Bot" button
   - Bot stops gracefully within 2 seconds

---

## 🔧 Troubleshooting

### Bot won't start
```bash
# Check logs
tail -f traffic_bot.log

# Verify environment
python3 health_check.py

# Test proxy API
curl -H "Authorization: Token YOUR_API_KEY" \
  https://proxy.webshare.io/api/v2/proxy/list/
```

### High memory usage
```bash
# Check resources
free -h
htop

# Reduce concurrent proxies
# Edit config.json: "max_concurrent_proxies": 25
```

### Proxy errors
```bash
# Check proxy validation in logs
grep "PROXY HEALTH CHECK" traffic_bot.log

# Verify API key is set
echo $PROXY_API_KEY
```

---

## 📝 Common Commands

```bash
# Start application
./start.sh

# Check health
python3 health_check.py

# View logs
tail -f traffic_bot.log

# Stop application (if using start.sh)
Ctrl+C

# Stop application (if using background)
pkill -f "streamlit run"

# Check if running
ps aux | grep streamlit
```

---

## 🎯 Performance Tips

**For 8GB RAM:**
- Max 50 concurrent proxies ✅
- Browser pool size: 10
- Monitor memory: `watch free -h`

**For 16GB RAM:**
- Max 100 concurrent proxies ✅
- Browser pool size: 20
- Increase if stable

**For 4GB RAM:**
- Max 25 concurrent proxies ⚠️
- Browser pool size: 5
- Close other applications

---

## 📞 Need Help?

1. Check logs: `tail -100 traffic_bot.log`
2. Run health check: `python3 health_check.py`
3. Review DEPLOYMENT.md for detailed guide
4. Check resource usage: `htop` or `free -h`

---

## ✅ Checklist

- [ ] System dependencies installed
- [ ] Python dependencies installed
- [ ] Playwright browsers installed
- [ ] .env file configured with API key
- [ ] config.json reviewed
- [ ] Excel file ready with URLs
- [ ] Server has 8GB+ RAM
- [ ] Port 8501 is accessible
- [ ] Proxy subscription is active

---

**Ready to deploy? Run `./start.sh` and you're good to go! 🚀**

