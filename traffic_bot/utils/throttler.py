"""Request throttling and rate limiting module"""
import asyncio
import time
import logging
from typing import Dict, Optional, List
from collections import defaultdict, deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RequestThrottler:
    """Throttles requests to prevent rate limiting and reduce detection"""
    
    def __init__(self, config: dict):
        """
        Initialize request throttler
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        throttling_config = config.get('throttling', {})
        
        # Throttling settings
        self.enabled = throttling_config.get('enabled', True)
        self.requests_per_minute = throttling_config.get('requests_per_minute', 30)
        self.requests_per_second = throttling_config.get('requests_per_second', 2)
        self.burst_size = throttling_config.get('burst_size', 5)
        self.adaptive_delays = throttling_config.get('adaptive_delays', True)
        
        # Per-domain throttling
        self.per_domain_limit = throttling_config.get('per_domain_limit', True)
        self.domain_requests_per_minute = throttling_config.get('domain_requests_per_minute', 10)
        
        # Token bucket for rate limiting
        self.tokens = self.requests_per_second
        self.last_refill = time.time()
        self.token_refill_rate = self.requests_per_second / 60.0  # tokens per second
        
        # Request history tracking
        self.request_history: deque = deque(maxlen=1000)
        self.domain_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Adaptive delay tracking
        self.response_times: deque = deque(maxlen=100)
        self.failure_count = 0
        self.success_count = 0
        
        # Lock for thread safety
        self.lock = asyncio.Lock()
    
    async def wait_if_needed(self, domain: Optional[str] = None) -> float:
        """
        Wait if needed based on rate limiting rules
        
        Args:
            domain: Domain name for per-domain throttling
            
        Returns:
            Actual wait time in seconds
        """
        if not self.enabled:
            return 0.0
        
        async with self.lock:
            now = time.time()
            wait_time = 0.0
            
            # Refill tokens
            elapsed = now - self.last_refill
            self.tokens = min(
                self.requests_per_second,
                self.tokens + elapsed * self.token_refill_rate
            )
            self.last_refill = now
            
            # Check token bucket
            if self.tokens < 1.0:
                wait_time = max(wait_time, (1.0 - self.tokens) / self.token_refill_rate)
            
            # Check global rate limit (requests per minute)
            recent_requests = [
                req_time for req_time in self.request_history
                if now - req_time < 60.0
            ]
            if len(recent_requests) >= self.requests_per_minute:
                oldest_request = min(recent_requests)
                wait_time = max(wait_time, 60.0 - (now - oldest_request))
            
            # Check per-domain rate limit
            if self.per_domain_limit and domain:
                domain_recent = [
                    req_time for req_time in self.domain_history[domain]
                    if now - req_time < 60.0
                ]
                if len(domain_recent) >= self.domain_requests_per_minute:
                    oldest_domain_request = min(domain_recent)
                    wait_time = max(wait_time, 60.0 - (now - oldest_domain_request))
            
            # Check burst limit
            recent_burst = [
                req_time for req_time in self.request_history
                if now - req_time < 1.0
            ]
            if len(recent_burst) >= self.burst_size:
                oldest_burst = min(recent_burst)
                wait_time = max(wait_time, 1.0 - (now - oldest_burst))
            
            # Wait if needed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # Record request
            self.request_history.append(time.time())
            if domain:
                self.domain_history[domain].append(time.time())
            
            # Consume token
            self.tokens = max(0, self.tokens - 1.0)
            
            return wait_time
    
    def record_response(self, response_time: float, success: bool):
        """
        Record response time for adaptive throttling
        
        Args:
            response_time: Response time in seconds
            success: Whether request was successful
        """
        if not self.adaptive_delays:
            return
        
        self.response_times.append(response_time)
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
    
    def get_adaptive_delay(self, base_delay: float) -> float:
        """
        Calculate adaptive delay based on response times and failures
        
        Args:
            base_delay: Base delay in seconds
            
        Returns:
            Adjusted delay based on performance
        """
        if not self.adaptive_delays or not self.response_times:
            return base_delay
        
        # Calculate average response time
        avg_response_time = sum(self.response_times) / len(self.response_times)
        
        # If responses are slow, increase delay
        if avg_response_time > 5.0:
            delay_multiplier = 1.5
        elif avg_response_time > 3.0:
            delay_multiplier = 1.2
        else:
            delay_multiplier = 1.0
        
        # If failure rate is high, increase delay
        total_requests = self.success_count + self.failure_count
        if total_requests > 10:
            failure_rate = self.failure_count / total_requests
            if failure_rate > 0.3:
                delay_multiplier *= 1.5
            elif failure_rate > 0.2:
                delay_multiplier *= 1.2
        
        return base_delay * delay_multiplier
    
    def reset_adaptive_throttling(self):
        """Reset adaptive throttling counters"""
        self.response_times.clear()
        self.failure_count = 0
        self.success_count = 0
    
    def get_throttle_stats(self) -> Dict[str, any]:
        """
        Get current throttling statistics
        
        Returns:
            Dictionary with throttle stats
        """
        now = time.time()
        recent_requests = [
            req_time for req_time in self.request_history
            if now - req_time < 60.0
        ]
        
        return {
            'requests_last_minute': len(recent_requests),
            'available_tokens': self.tokens,
            'domain_limits': {
                domain: len([r for r in requests if now - r < 60.0])
                for domain, requests in self.domain_history.items()
            },
            'avg_response_time': sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            'failure_rate': self.failure_count / (self.success_count + self.failure_count) if (self.success_count + self.failure_count) > 0 else 0
        }

