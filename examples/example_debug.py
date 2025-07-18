#!/usr/bin/env python3
"""
Example Python script for debugging demonstration
"""

def factorial(n):
    """Calculate factorial of n"""
    if n <= 1:
        return 1
    else:
        return n * factorial(n - 1)

def fibonacci(n):
    """Calculate nth Fibonacci number"""
    if n <= 1:
        return n
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)

def divide_numbers(a, b):
    """Divide two numbers with potential error"""
    # This might cause a division by zero error
    return a / b

def main():
    print("Starting calculations...")
    
    # Test factorial
    fact_result = factorial(5)
    print(f"Factorial of 5: {fact_result}")
    
    # Test fibonacci
    fib_result = fibonacci(10)
    print(f"Fibonacci of 10: {fib_result}")
    
    # Test division (potential error)
    try:
        div_result = divide_numbers(10, 2)
        print(f"Division result: {div_result}")
        
        # This will cause an error
        error_result = divide_numbers(10, 0)
        print(f"Error result: {error_result}")
    except ZeroDivisionError as e:
        print(f"Error caught: {e}")
    
    print("Calculations completed!")

if __name__ == "__main__":
    main()