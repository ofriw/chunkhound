#!/usr/bin/env python3
"""
QA Test File - Session 3 Different Location
Created: 2025-06-14T16:22:00+03:00
Purpose: Testing search indexing in different directory location
"""

class DifferentLocationTestClass:
    """Test class in tests directory for QA validation"""

    def __init__(self):
        self.location_marker = "DIFFERENT_LOCATION_TEST_MARKER_SESSION3"
        self.unique_id = "tests_directory_qa_validation_2025_06_14"

    def different_location_method(self):
        """Method with unique signature for search testing"""
        return "DIFFERENT_LOCATION_METHOD_RESULT_SESSION3"

# Global constant for different location testing
TESTS_DIR_GLOBAL_CONSTANT = "TESTS_DIRECTORY_QA_CONSTANT_SESSION3"

def tests_directory_function():
    """Function in tests directory for search validation"""
    unique_variable = "tests_dir_unique_content_session3"
    return f"Tests directory result: {unique_variable}"

if __name__ == "__main__":
    test_obj = DifferentLocationTestClass()
    print(f"Location marker: {test_obj.location_marker}")
    print(f"Unique ID: {test_obj.unique_id}")
    print(f"Method result: {test_obj.different_location_method()}")
    print(f"Global constant: {TESTS_DIR_GLOBAL_CONSTANT}")
    print(f"Function result: {tests_directory_function()}")
