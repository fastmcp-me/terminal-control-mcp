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

def buggy_function():
    """A function with a deliberate bug for debugging demonstration"""
    data = [1, 2, 3, 4, 5]
    result = 0

    # Bug: index will go out of bounds
    for i in range(len(data) + 1):  # This +1 causes the bug
        result += data[i]  # Will fail on the last iteration

    return result

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

    # Test buggy function for debugging demonstration
    print("Testing buggy function...")
    try:
        buggy_result = buggy_function()
        print(f"Buggy function result: {buggy_result}")
    except IndexError as e:
        print(f"Bug found: {e}")

    print("Calculations completed!")

if __name__ == "__main__":
    main()
