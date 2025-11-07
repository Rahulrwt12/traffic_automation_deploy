#!/bin/bash
# ============================================================================
# Traffic Automation - Real-time Monitoring Script
# ============================================================================
# Provides real-time monitoring of system resources and application health

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to get memory usage
get_memory() {
    free -m | awk 'NR==2{printf "%.1f%%", $3*100/$2}'
}

# Function to get CPU usage
get_cpu() {
    top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1"%"}'
}

# Function to get disk usage
get_disk() {
    df -h . | awk 'NR==2{print $5}'
}

# Function to check if streamlit is running
check_streamlit() {
    if pgrep -f "streamlit run" > /dev/null; then
        echo "${GREEN}RUNNING${NC}"
    else
        echo "${RED}STOPPED${NC}"
    fi
}

# Function to get browser count
get_browser_count() {
    pgrep -f "chromium\|firefox" | wc -l
}

# Function to get bot status
get_bot_status() {
    if [ -f "bot_status.json" ]; then
        local is_running=$(python3 -c "import json; f=open('bot_status.json'); d=json.load(f); print(d.get('is_running', False))" 2>/dev/null || echo "false")
        if [ "$is_running" == "True" ]; then
            echo "${GREEN}RUNNING${NC}"
        else
            echo "${YELLOW}IDLE${NC}"
        fi
    else
        echo "${YELLOW}UNKNOWN${NC}"
    fi
}

# Function to get recent error count
get_error_count() {
    if [ -f "traffic_bot.log" ]; then
        tail -100 traffic_bot.log | grep -i "error\|failed" | wc -l
    else
        echo "0"
    fi
}

# Function to get traffic stats
get_traffic_stats() {
    if [ -f "traffic_stats.json" ]; then
        python3 -c "
import json
try:
    with open('traffic_stats.json', 'r') as f:
        stats = json.load(f)
    print(f\"Visits: {stats.get('total_visits', 0)} | Sessions: {stats.get('total_sessions', 0)}\")
except:
    print('Unable to read stats')
" 2>/dev/null || echo "Unable to read stats"
    else
        echo "No stats available"
    fi
}

# Main monitoring loop
echo ""
echo "============================================================================"
echo "      🚦 Traffic Automation - Real-time Monitoring Dashboard"
echo "============================================================================"
echo ""
echo "Press Ctrl+C to exit"
echo ""

while true; do
    clear
    
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}      🚦 Traffic Automation - Live Monitor${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    echo ""
    
    # Current time
    echo -e "${BLUE}Time:${NC} $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    # System Resources
    echo -e "${BLUE}📊 SYSTEM RESOURCES${NC}"
    echo "────────────────────────────────────────────────────────────────────────────"
    MEMORY=$(get_memory)
    CPU=$(get_cpu)
    DISK=$(get_disk)
    
    echo -e "Memory:    ${MEMORY}"
    echo -e "CPU:       ${CPU}"
    echo -e "Disk:      ${DISK}"
    echo ""
    
    # Application Status
    echo -e "${BLUE}🎮 APPLICATION STATUS${NC}"
    echo "────────────────────────────────────────────────────────────────────────────"
    echo -e "Streamlit: $(check_streamlit)"
    echo -e "Bot:       $(get_bot_status)"
    echo -e "Browsers:  $(get_browser_count) instances"
    echo ""
    
    # Traffic Statistics
    echo -e "${BLUE}📈 TRAFFIC STATISTICS${NC}"
    echo "────────────────────────────────────────────────────────────────────────────"
    echo -e "$(get_traffic_stats)"
    echo ""
    
    # Recent Errors
    ERROR_COUNT=$(get_error_count)
    echo -e "${BLUE}⚠️  RECENT ACTIVITY${NC}"
    echo "────────────────────────────────────────────────────────────────────────────"
    if [ "$ERROR_COUNT" -gt "0" ]; then
        echo -e "Errors in last 100 lines: ${RED}${ERROR_COUNT}${NC}"
    else
        echo -e "Errors in last 100 lines: ${GREEN}0${NC}"
    fi
    echo ""
    
    # Health Check
    echo -e "${BLUE}🏥 HEALTH CHECK${NC}"
    echo "────────────────────────────────────────────────────────────────────────────"
    if command -v python3 &> /dev/null && [ -f "health_check.py" ]; then
        HEALTH_STATUS=$(python3 health_check.py 2>/dev/null && echo "${GREEN}HEALTHY${NC}" || echo "${RED}ISSUES DETECTED${NC}")
        echo -e "Status: ${HEALTH_STATUS}"
    else
        echo -e "Status: ${YELLOW}Health check unavailable${NC}"
    fi
    echo ""
    
    # Quick Actions
    echo -e "${BLUE}⌨️  QUICK ACTIONS${NC}"
    echo "────────────────────────────────────────────────────────────────────────────"
    echo "  View Logs:      tail -f traffic_bot.log"
    echo "  Stop Bot:       pkill -f streamlit"
    echo "  Restart Bot:    ./start.sh"
    echo "  Health Check:   python3 health_check.py"
    echo ""
    
    echo -e "${BLUE}============================================================================${NC}"
    echo -e "${BLUE}Auto-refreshing every 5 seconds... (Ctrl+C to exit)${NC}"
    echo -e "${BLUE}============================================================================${NC}"
    
    # Wait 5 seconds before next update
    sleep 5
done

