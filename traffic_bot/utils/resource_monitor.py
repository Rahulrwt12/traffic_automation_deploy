"""Resource monitoring module for tracking system resources"""
import psutil
import logging
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Monitors system resources (CPU, memory, browser instances)"""
    
    def __init__(self, config: dict):
        """
        Initialize resource monitor
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.monitoring_enabled = config.get('resource_monitoring', {}).get('enabled', True)
        self.check_interval = config.get('resource_monitoring', {}).get('check_interval_seconds', 30)
        self.max_memory_percent = config.get('resource_monitoring', {}).get('max_memory_percent', 85)
        self.max_cpu_percent = config.get('resource_monitoring', {}).get('max_cpu_percent', 90)
        self.alert_on_high_usage = config.get('resource_monitoring', {}).get('alert_on_high_usage', True)
        
        # Resource tracking
        self.monitoring_task: Optional[asyncio.Task] = None
        self.resource_history: deque = deque(maxlen=100)  # Keep last 100 readings
        self.browser_processes: List[int] = []
        self.alerts_sent = set()  # Track alerts to avoid spam
        
        # Get process ID for this Python process
        self.process = psutil.Process()
    
    def register_browser_process(self, pid: int):
        """Register a browser process for monitoring"""
        if pid not in self.browser_processes:
            self.browser_processes.append(pid)
            logger.debug(f"Registered browser process PID: {pid}")
    
    def unregister_browser_process(self, pid: int):
        """Unregister a browser process"""
        if pid in self.browser_processes:
            self.browser_processes.remove(pid)
            logger.debug(f"Unregistered browser process PID: {pid}")
    
    def get_current_resources(self) -> Dict[str, float]:
        """
        Get current resource usage
        
        Returns:
            Dictionary with CPU and memory usage percentages
        """
        try:
            # System-wide CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # System-wide memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Process-specific memory (this Python process + browsers)
            process_memory = self.process.memory_info().rss / (1024 * 1024)  # MB
            
            # Browser processes memory
            browser_memory = 0
            browser_processes_alive = []
            for pid in self.browser_processes[:]:  # Copy list to avoid modification during iteration
                try:
                    browser_proc = psutil.Process(pid)
                    browser_memory += browser_proc.memory_info().rss / (1024 * 1024)  # MB
                    browser_processes_alive.append(pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process no longer exists
                    self.browser_processes.remove(pid)
            
            self.browser_processes = browser_processes_alive
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'process_memory_mb': process_memory,
                'browser_memory_mb': browser_memory,
                'total_memory_mb': process_memory + browser_memory,
                'browser_count': len(self.browser_processes),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return {
                'cpu_percent': 0,
                'memory_percent': 0,
                'process_memory_mb': 0,
                'browser_memory_mb': 0,
                'total_memory_mb': 0,
                'browser_count': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    def check_resource_limits(self, resources: Dict[str, float]) -> bool:
        """
        Check if resources are within limits
        
        Args:
            resources: Current resource usage dictionary
            
        Returns:
            True if within limits, False otherwise
        """
        if not self.alert_on_high_usage:
            return True
        
        warnings = []
        
        # Check memory
        if resources['memory_percent'] > self.max_memory_percent:
            warnings.append(f"High system memory usage: {resources['memory_percent']:.1f}%")
        
        # Check CPU
        if resources['cpu_percent'] > self.max_cpu_percent:
            warnings.append(f"High CPU usage: {resources['cpu_percent']:.1f}%")
        
        # Check browser memory
        if resources['browser_memory_mb'] > 10000:  # 10GB threshold
            warnings.append(f"High browser memory usage: {resources['browser_memory_mb']:.1f}MB")
        
        if warnings:
            alert_key = f"{resources['memory_percent']:.0f}_{resources['cpu_percent']:.0f}"
            if alert_key not in self.alerts_sent:
                logger.warning("⚠️  RESOURCE WARNING:")
                for warning in warnings:
                    logger.warning(f"   {warning}")
                logger.warning(f"   Browser instances: {resources['browser_count']}")
                logger.warning(f"   Total memory (process+browsers): {resources['total_memory_mb']:.1f}MB")
                self.alerts_sent.add(alert_key)
            
            # Clear old alerts periodically
            if len(self.alerts_sent) > 10:
                self.alerts_sent.clear()
            
            return False
        
        return True
    
    async def monitor_loop(self):
        """Main monitoring loop"""
        if not self.monitoring_enabled:
            return
        
        logger.info("🔍 Resource monitoring started")
        
        while True:
            try:
                resources = self.get_current_resources()
                self.resource_history.append(resources)
                
                # Check limits
                within_limits = self.check_resource_limits(resources)
                
                # Log periodic summary (every 5 checks = ~2.5 minutes)
                if len(self.resource_history) % 5 == 0:
                    logger.info(
                        f"📊 Resources: CPU {resources['cpu_percent']:.1f}% | "
                        f"Memory {resources['memory_percent']:.1f}% | "
                        f"Browsers {resources['browser_count']} | "
                        f"Browser Memory {resources['browser_memory_mb']:.1f}MB"
                    )
                
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Resource monitoring stopped")
                break
            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    def start_monitoring(self):
        """Start background monitoring task"""
        if self.monitoring_enabled and self.monitoring_task is None:
            self.monitoring_task = asyncio.create_task(self.monitor_loop())
            logger.info("✅ Resource monitoring enabled")
    
    def stop_monitoring(self):
        """Stop background monitoring task"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.monitoring_task = None
            logger.info("Resource monitoring stopped")
    
    def get_summary(self) -> Dict[str, any]:
        """
        Get resource usage summary
        
        Returns:
            Dictionary with summary statistics
        """
        if not self.resource_history:
            return {'status': 'no_data'}
        
        cpu_values = [r['cpu_percent'] for r in self.resource_history]
        memory_values = [r['memory_percent'] for r in self.resource_history]
        
        return {
            'status': 'active',
            'cpu_avg': sum(cpu_values) / len(cpu_values),
            'cpu_max': max(cpu_values),
            'memory_avg': sum(memory_values) / len(memory_values),
            'memory_max': max(memory_values),
            'browser_count': self.resource_history[-1]['browser_count'],
            'total_readings': len(self.resource_history)
        }

