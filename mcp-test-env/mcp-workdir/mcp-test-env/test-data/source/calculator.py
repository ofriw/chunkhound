def calculate_sum(a, b):
    """Calculate the sum of two numbers"""
    return a + b

def calculate_product(a, b):
    """Calculate the product of two numbers"""
    return a * b

class Calculator:
    def __init__(self):
        self.history = []
    
    def add(self, a, b):
        result = calculate_sum(a, b)
        self.history.append(f"add({a}, {b}) = {result}")
        return result
    
    def multiply(self, a, b):
        result = calculate_product(a, b)
        self.history.append(f"multiply({a}, {b}) = {result}")
        return result
    
    def get_history(self):
        return self.history
EOF < /dev/null