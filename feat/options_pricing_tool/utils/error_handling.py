import logging
import functools
import time
from typing import Any, Callable, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class OptionsAnalysisError(Exception):
    """Base exception for options analysis errors"""
    pass

class ValidationError(OptionsAnalysisError):
    """Raised when input validation fails"""
    pass

class DataFetchError(OptionsAnalysisError):
    """Raised when data fetching fails"""
    pass

class CalculationError(OptionsAnalysisError):
    """Raised when pricing calculations fail"""
    pass

def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry function calls on failure with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for delay
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay:.1f} seconds..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}")
            
            raise last_exception
        return wrapper
    return decorator

def log_performance(func: Callable) -> Callable:
    """
    Decorator to log function execution time and performance metrics
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(
                f"{func.__name__} completed successfully in {execution_time:.2f}s"
            )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"{func.__name__} failed after {execution_time:.2f}s: {e}"
            )
            raise
            
    return wrapper

def validate_numeric_range(value: float, min_val: float, max_val: float, name: str) -> None:
    """
    Validate that a numeric value is within a specified range
    
    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        name: Name of the parameter for error messages
        
    Raises:
        ValidationError: If value is outside the valid range
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a number, got {type(value).__name__}")
    
    if not (min_val <= value <= max_val):
        raise ValidationError(f"{name} must be between {min_val} and {max_val}, got {value}")

def validate_positive(value: float, name: str) -> None:
    """
    Validate that a value is positive
    
    Args:
        value: Value to validate
        name: Name of the parameter for error messages
        
    Raises:
        ValidationError: If value is not positive
    """
    if not isinstance(value, (int, float)):
        raise ValidationError(f"{name} must be a number, got {type(value).__name__}")
    
    if value <= 0:
        raise ValidationError(f"{name} must be positive, got {value}")

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default value if denominator is zero
    
    Args:
        numerator: Numerator
        denominator: Denominator
        default: Value to return if division by zero
        
    Returns:
        Result of division or default value
    """
    if abs(denominator) < 1e-10:
        return default
    return numerator / denominator

def safe_log(value: float, default: float = 0.0) -> float:
    """
    Safely calculate natural logarithm, returning default for invalid inputs
    
    Args:
        value: Value to take log of
        default: Value to return for invalid inputs
        
    Returns:
        Natural logarithm or default value
    """
    import math
    
    if value <= 0:
        return default
    
    try:
        return math.log(value)
    except (ValueError, OverflowError):
        return default

def safe_power(base: float, exponent: float, default: float = 0.0) -> float:
    """
    Safely calculate power, handling edge cases
    
    Args:
        base: Base value
        exponent: Exponent
        default: Value to return for invalid calculations
        
    Returns:
        base^exponent or default value
    """
    try:
        # Handle negative base with fractional exponent
        if base < 0 and exponent != int(exponent):
            return default
        
        result = base ** exponent
        
        # Check for overflow/underflow
        if not (-1e10 <= result <= 1e10):
            return default
        
        return result
        
    except (ValueError, OverflowError, ZeroDivisionError):
        return default

class PerformanceMonitor:
    """
    Context manager for monitoring performance metrics
    """
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.metrics = {}
    
    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"Starting {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time
        
        if exc_type is None:
            logger.info(f"{self.operation_name} completed in {execution_time:.2f}s")
        else:
            logger.error(f"{self.operation_name} failed after {execution_time:.2f}s: {exc_val}")
        
        self.metrics['execution_time'] = execution_time
        self.metrics['success'] = exc_type is None
    
    def add_metric(self, name: str, value: Any):
        """Add a custom metric"""
        self.metrics[name] = value

def handle_api_errors(func: Callable) -> Callable:
    """
    Decorator to handle and format API errors consistently
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            logger.warning(f"Validation error in {func.__name__}: {e}")
            raise
        except DataFetchError as e:
            logger.error(f"Data fetch error in {func.__name__}: {e}")
            raise
        except CalculationError as e:
            logger.error(f"Calculation error in {func.__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            raise OptionsAnalysisError(f"Internal error: {str(e)}")
    
    return wrapper