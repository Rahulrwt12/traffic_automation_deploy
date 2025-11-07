#!/usr/bin/env python3
"""
Health Check Script for Traffic Automation
Can be used by monitoring services and load balancers
"""
import json
import os
import sys
from datetime import datetime

def check_health():
    """Check application health and return status"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    all_healthy = True
    
    # Check 1: Config file exists
    if os.path.exists('config.json'):
        health_status["checks"]["config_file"] = "ok"
    else:
        health_status["checks"]["config_file"] = "missing"
        all_healthy = False
    
    # Check 2: Environment variables
    env_vars_ok = True
    if not os.getenv('PROXY_API_KEY'):
        env_vars_ok = False
    health_status["checks"]["environment_variables"] = "ok" if env_vars_ok else "warning"
    
    # Check 3: Data files
    data_files_status = []
    if os.path.exists('traffic_history.json'):
        data_files_status.append("history")
    if os.path.exists('traffic_stats.json'):
        data_files_status.append("stats")
    if os.path.exists('bot_status.json'):
        data_files_status.append("bot_status")
    
    health_status["checks"]["data_files"] = data_files_status if data_files_status else "none"
    
    # Check 4: Bot status
    if os.path.exists('bot_status.json'):
        try:
            with open('bot_status.json', 'r') as f:
                bot_status = json.load(f)
            health_status["checks"]["bot_running"] = bot_status.get('is_running', False)
            health_status["checks"]["bot_error"] = bot_status.get('error_message', None)
        except Exception as e:
            health_status["checks"]["bot_status_error"] = str(e)
    
    # Check 5: Disk space
    try:
        import psutil
        disk = psutil.disk_usage('.')
        disk_free_gb = disk.free / (1024**3)
        health_status["checks"]["disk_space_gb"] = round(disk_free_gb, 2)
        if disk_free_gb < 1:
            health_status["checks"]["disk_warning"] = "low_space"
    except ImportError:
        health_status["checks"]["disk_space"] = "unable_to_check"
    
    # Check 6: Memory
    try:
        import psutil
        memory = psutil.virtual_memory()
        memory_available_gb = memory.available / (1024**3)
        health_status["checks"]["memory_available_gb"] = round(memory_available_gb, 2)
        health_status["checks"]["memory_percent"] = memory.percent
        if memory.percent > 90:
            health_status["checks"]["memory_warning"] = "high_usage"
    except ImportError:
        health_status["checks"]["memory"] = "unable_to_check"
    
    # Overall status
    if not all_healthy:
        health_status["status"] = "unhealthy"
    elif not env_vars_ok:
        health_status["status"] = "degraded"
    
    return health_status

def main():
    """Main entry point"""
    try:
        health = check_health()
        
        # Print JSON for programmatic use
        if "--json" in sys.argv:
            print(json.dumps(health, indent=2))
        else:
            # Print human-readable format
            print("=" * 60)
            print("🏥 Health Check Report")
            print("=" * 60)
            print(f"Status: {health['status'].upper()}")
            print(f"Timestamp: {health['timestamp']}")
            print()
            print("Checks:")
            for check, status in health['checks'].items():
                print(f"  {check}: {status}")
            print("=" * 60)
        
        # Exit with appropriate code
        if health['status'] == 'healthy':
            sys.exit(0)
        elif health['status'] == 'degraded':
            sys.exit(1)
        else:
            sys.exit(2)
    
    except Exception as e:
        print(f"ERROR: Health check failed: {e}", file=sys.stderr)
        sys.exit(3)

if __name__ == "__main__":
    main()

