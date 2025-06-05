import tempfile
import time
from pathlib import Path
import pytest
from chunkhound.database import Database


def test_unchanged_file_not_reprocessed():
    """Test that unchanged files are not reprocessed after initial indexing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""def hello():
    '''A test function that does something useful.'''
    message = 'world'
    result = f'Hello, {message}!'
    return result
""")
        file_path = Path(f.name)
    
    try:
        # Use in-memory database for testing
        db = Database(":memory:")
        db.connect()
        
        # First processing - should succeed
        result1 = db.process_file(file_path)
        assert result1["status"] == "success"
        assert result1["chunks"] > 0
        first_chunks = result1["chunks"]
        
        # Second processing (unchanged file) - should be skipped
        result2 = db.process_file(file_path)
        assert result2["status"] == "up_to_date"
        assert result2["chunks"] == 0
        
        # Verify file record exists with correct mtime
        file_record = db.get_file_by_path(str(file_path))
        assert file_record is not None
        assert file_record["mtime"] is not None
        
        # Verify mtime matches file system
        current_mtime = file_path.stat().st_mtime
        db_mtime = file_record["mtime"].timestamp()
        assert abs(db_mtime - current_mtime) < 1.0  # Allow small float precision differences
        
    finally:
        file_path.unlink(missing_ok=True)


def test_changed_file_gets_reprocessed():
    """Test that changed files are reprocessed with updated mtime."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""def hello():
    '''A test function that does something useful.'''
    message = 'world'
    result = f'Hello, {message}!'
    return result
""")
        file_path = Path(f.name)
    
    try:
        # Use in-memory database for testing
        db = Database(":memory:")
        db.connect()
        
        # First processing
        result1 = db.process_file(file_path)
        assert result1["status"] == "success"
        original_chunks = result1["chunks"]
        
        # Get original mtime from database
        file_record1 = db.get_file_by_path(str(file_path))
        original_mtime = file_record1["mtime"].timestamp()
        
        # Wait and modify file to ensure different mtime
        time.sleep(1.1)
        with open(file_path, 'w') as f:
            f.write("""def hello():
    '''A test function that does something useful.'''
    message = 'world'
    result = f'Hello, {message}!'
    return result

def goodbye():
    '''Another test function.'''
    message = 'moon'
    result = f'Goodbye, {message}!'
    return result
""")
        
        # Second processing (changed file) - should reprocess
        result2 = db.process_file(file_path)
        assert result2["status"] == "success"
        assert result2["chunks"] > original_chunks  # Should have more chunks now
        
        # Verify mtime was updated in database
        file_record2 = db.get_file_by_path(str(file_path))
        updated_mtime = file_record2["mtime"].timestamp()
        assert updated_mtime > original_mtime
        
        # Verify new mtime matches file system
        current_mtime = file_path.stat().st_mtime
        assert abs(updated_mtime - current_mtime) < 1.0
        
    finally:
        file_path.unlink(missing_ok=True)


def test_new_file_processing():
    """Test that new files are processed normally."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""def new_function():
    '''A new test function.'''
    value = 42
    result = value * 2
    return result
""")
        file_path = Path(f.name)
    
    try:
        # Use in-memory database for testing
        db = Database(":memory:")
        db.connect()
        
        # Processing new file should succeed
        result = db.process_file(file_path)
        assert result["status"] == "success"
        assert result["chunks"] > 0
        
        # Verify file record was created with correct mtime
        file_record = db.get_file_by_path(str(file_path))
        assert file_record is not None
        assert file_record["mtime"] is not None
        
        current_mtime = file_path.stat().st_mtime
        db_mtime = file_record["mtime"].timestamp()
        assert abs(db_mtime - current_mtime) < 1.0
        
    finally:
        file_path.unlink(missing_ok=True)


def test_mtime_update_logic():
    """Test the mtime update logic through the integrated process_file workflow."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("""def test():
    '''A test function for mtime logic.'''
    value = 123
    result = value + 456
    return result
""")
        file_path = Path(f.name)
    
    try:
        # Use in-memory database for testing
        db = Database(":memory:")
        db.connect()
        
        # Process file first time
        result1 = db.process_file(file_path)
        assert result1["status"] == "success"
        
        # Verify initial record
        file_record1 = db.get_file_by_path(str(file_path))
        original_mtime = file_record1["mtime"].timestamp()
        
        # Wait and touch file to change mtime
        time.sleep(1.1)
        file_path.touch()
        
        # Process same file with newer mtime
        result2 = db.process_file(file_path)
        assert result2["status"] == "success"
        
        # Verify mtime was updated in database
        file_record2 = db.get_file_by_path(str(file_path))
        updated_mtime = file_record2["mtime"].timestamp()
        assert updated_mtime > original_mtime
        
        # Verify new mtime matches file system
        current_mtime = file_path.stat().st_mtime
        assert abs(updated_mtime - current_mtime) < 1.0
        
    finally:
        file_path.unlink(missing_ok=True)


def test_directory_processing_efficiency():
    """Test that directory processing only handles changed files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create test files
        file1 = tmpdir / "file1.py"
        file2 = tmpdir / "file2.py"
        file1.write_text("""def func1():
    '''Function 1 for testing.'''
    value = 100
    result = value * 2
    return result
""")
        file2.write_text("""def func2():
    '''Function 2 for testing.'''
    value = 200
    result = value * 3
    return result
""")
        
        # Use in-memory database for testing
        db = Database(":memory:")
        db.connect()
        
        # First processing - should process both files
        result1 = db.process_directory(tmpdir)
        assert result1["processed"] == 2
        assert result1["total_chunks"] > 0
        
        # Second processing (no changes) - should skip both files
        result2 = db.process_directory(tmpdir)
        assert result2["processed"] == 0  # No files should be processed
        assert result2["skipped"] == 2    # Both files should be skipped
        
        # Modify one file
        time.sleep(1.1)
        file1.write_text("""def func1():
    '''Function 1 for testing.'''
    value = 100
    result = value * 2
    return result

def func1_modified():
    '''Modified function 1.'''
    value = 150
    result = value * 4
    return result
""")
        
        # Third processing - should only process modified file
        result3 = db.process_directory(tmpdir)
        assert result3["processed"] == 1  # Only modified file
        assert result3["skipped"] == 1    # Unchanged file skipped


def test_performance_improvement():
    """Test that processing time improves significantly for unchanged files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create multiple test files
        for i in range(10):
            file_path = tmpdir / f"file_{i:02d}.py"
            file_path.write_text(f"""
def function_{i}():
    '''Function number {i}'''
    return {i}

class Class_{i}:
    def method_{i}(self):
        return self.function_{i}()
""")
        
        # Use in-memory database for testing
        db = Database(":memory:")
        db.connect()
        
        # First processing (baseline)
        import time as time_module
        start_time = time_module.time()
        result1 = db.process_directory(tmpdir)
        first_duration = time_module.time() - start_time
        
        assert result1["processed"] == 10
        
        # Second processing (should be much faster)
        start_time = time_module.time()
        result2 = db.process_directory(tmpdir)
        second_duration = time_module.time() - start_time
        
        assert result2["processed"] == 0
        assert result2["skipped"] == 10
        
        # Second run should be significantly faster
        # (Allow some tolerance for test environment variations)
        if first_duration > 0.1:  # Only check if first run took meaningful time
            improvement_ratio = first_duration / max(second_duration, 0.001)
            assert improvement_ratio > 2.0, f"Expected >2x improvement, got {improvement_ratio:.1f}x"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])