"""Comprehensive error handling utilities"""
import asyncio
import logging
import traceback
from typing import Callable, Any, Optional, TypeVar, List
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorHandler:
    """Comprehensive error handling with retry logic"""
    
    @staticmethod
    async def retry_async(
        func: Callable,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,),
        error_context: Optional[str] = None
    ) -> Any:
        """
        Retry an async function with exponential backoff
        
        Args:
            func: Async function to retry
            max_retries: Maximum number of retries
            delay: Initial delay between retries (seconds)
            backoff: Backoff multiplier
            exceptions: Tuple of exceptions to catch
            error_context: Context string for logging
            
        Returns:
            Function result
        
        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return await func()
            except exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = delay * (backoff ** attempt)
                    context_str = f" [{error_context}]" if error_context else ""
                    logger.warning(
                        f"⚠️  Attempt {attempt + 1}/{max_retries + 1} failed{context_str}: {str(e)[:100]}"
                    )
                    logger.debug(f"   Retrying in {wait_time:.1f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    context_str = f" [{error_context}]" if error_context else ""
                    logger.error(
                        f"❌ All {max_retries + 1} attempts failed{context_str}: {str(e)[:100]}"
                    )
                    logger.debug(f"   Full traceback:\n{traceback.format_exc()}")
        
        # Safety check: raise last exception if we have one, otherwise raise RuntimeError
        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError(f"retry_async failed but no exception was caught{f' [{error_context}]' if error_context else ''}")
    
    @staticmethod
    def retry_sync(
        func: Callable,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,),
        error_context: Optional[str] = None
    ) -> Any:
        """
        Retry a sync function with exponential backoff
        
        Args:
            func: Sync function to retry
            max_retries: Maximum number of retries
            delay: Initial delay between retries (seconds)
            backoff: Backoff multiplier
            exceptions: Tuple of exceptions to catch
            error_context: Context string for logging
            
        Returns:
            Function result
        
        Raises:
            Last exception if all retries fail
        """
        import time
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except exceptions as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = delay * (backoff ** attempt)
                    context_str = f" [{error_context}]" if error_context else ""
                    logger.warning(
                        f"⚠️  Attempt {attempt + 1}/{max_retries + 1} failed{context_str}: {str(e)[:100]}"
                    )
                    logger.debug(f"   Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    context_str = f" [{error_context}]" if error_context else ""
                    logger.error(
                        f"❌ All {max_retries + 1} attempts failed{context_str}: {str(e)[:100]}"
                    )
                    logger.debug(f"   Full traceback:\n{traceback.format_exc()}")
        
        # Safety check: raise last exception if we have one, otherwise raise RuntimeError
        if last_exception is not None:
            raise last_exception
        else:
            raise RuntimeError(f"retry_sync failed but no exception was caught{f' [{error_context}]' if error_context else ''}")
    
    @staticmethod
    def safe_execute(
        func: Callable,
        default_return: Any = None,
        exceptions: tuple = (Exception,),
        error_context: Optional[str] = None,
        log_error: bool = True
    ) -> Any:
        """
        Safely execute a function, returning default on error
        
        Args:
            func: Function to execute
            default_return: Value to return on error
            exceptions: Tuple of exceptions to catch
            error_context: Context string for logging
            log_error: Whether to log errors
            
        Returns:
            Function result or default_return
        """
        try:
            return func()
        except exceptions as e:
            if log_error:
                context_str = f" [{error_context}]" if error_context else ""
                logger.error(f"Error in safe_execute{context_str}: {str(e)[:100]}")
                logger.debug(f"   Full traceback:\n{traceback.format_exc()}")
            return default_return
    
    @staticmethod
    async def safe_execute_async(
        func: Callable,
        default_return: Any = None,
        exceptions: tuple = (Exception,),
        error_context: Optional[str] = None,
        log_error: bool = True
    ) -> Any:
        """
        Safely execute an async function, returning default on error
        
        Args:
            func: Async function to execute
            default_return: Value to return on error
            exceptions: Tuple of exceptions to catch
            error_context: Context string for logging
            log_error: Whether to log errors
            
        Returns:
            Function result or default_return
        """
        try:
            return await func()
        except exceptions as e:
            if log_error:
                context_str = f" [{error_context}]" if error_context else ""
                logger.error(f"Error in safe_execute_async{context_str}: {str(e)[:100]}")
                logger.debug(f"   Full traceback:\n{traceback.format_exc()}")
            return default_return
    
    @staticmethod
    def handle_browser_error(error: Exception, context: str = "") -> bool:
        """
        Handle browser-related errors with appropriate logging
        
        Args:
            error: Exception that occurred
            context: Additional context information
            
        Returns:
            True if error is recoverable, False otherwise
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Categorize errors
        recoverable_errors = [
            'TimeoutError',
            'NetworkError',
            'ConnectionError',
            'PageNotFound',
            'NavigationTimeout'
        ]
        
        is_recoverable = any(err_type in error_type for err_type in recoverable_errors)
        
        context_str = f" [{context}]" if context else ""
        
        if is_recoverable:
            logger.warning(f"⚠️  Recoverable browser error{context_str}: {error_type} - {error_msg[:100]}")
        else:
            logger.error(f"❌ Browser error{context_str}: {error_type} - {error_msg[:100]}")
        
        return is_recoverable


def error_handler_decorator(
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,),
    default_return: Any = None
):
    """
    Decorator for automatic error handling and retry
    
    Usage:
        @error_handler_decorator(max_retries=3, delay=1.0)
        async def my_function():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await ErrorHandler.retry_async(
                    lambda: func(*args, **kwargs),
                    max_retries=max_retries,
                    delay=delay,
                    exceptions=exceptions,
                    error_context=func.__name__
                )
            except Exception as e:
                logger.error(f"Function {func.__name__} failed after retries: {e}")
                return default_return
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return ErrorHandler.retry_sync(
                    lambda: func(*args, **kwargs),
                    max_retries=max_retries,
                    delay=delay,
                    exceptions=exceptions,
                    error_context=func.__name__
                )
            except Exception as e:
                logger.error(f"Function {func.__name__} failed after retries: {e}")
                return default_return
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

