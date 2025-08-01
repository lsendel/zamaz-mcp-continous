"""
Tests for test helper utilities and fixtures.
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta


class TestAsyncHelpers:
    """Test async helper utilities."""
    
    @pytest.mark.asyncio
    async def test_async_mock_creation(self):
        """Test creating async mocks."""
        mock_func = AsyncMock(return_value="test_result")
        result = await mock_func()
        assert result == "test_result"
        mock_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_async_mock_side_effect(self):
        """Test async mock with side effects."""
        mock_func = AsyncMock(side_effect=["result1", "result2", "result3"])
        
        result1 = await mock_func()
        result2 = await mock_func()
        result3 = await mock_func()
        
        assert result1 == "result1"
        assert result2 == "result2"
        assert result3 == "result3"
        assert mock_func.call_count == 3
    
    @pytest.mark.asyncio
    async def test_async_mock_exception(self):
        """Test async mock raising exceptions."""
        mock_func = AsyncMock(side_effect=ValueError("Test error"))
        
        with pytest.raises(ValueError, match="Test error"):
            await mock_func()


class TestTempFileHelpers:
    """Test temporary file and directory helpers."""
    
    def test_temp_file_creation(self):
        """Test creating temporary files."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("test content")
            temp_path = temp_file.name
        
        try:
            assert os.path.exists(temp_path)
            with open(temp_path, 'r') as f:
                content = f.read()
            assert content == "test content"
        finally:
            os.unlink(temp_path)
    
    def test_temp_directory_creation(self):
        """Test creating temporary directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            assert os.path.exists(temp_dir)
            assert os.path.isdir(temp_dir)
            
            # Create a file in the temp directory
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, 'w') as f:
                f.write("test")
            
            assert os.path.exists(test_file)
        
        # Directory should be cleaned up
        assert not os.path.exists(temp_dir)
    
    def test_temp_file_with_suffix(self):
        """Test creating temporary files with specific suffixes."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            assert temp_path.endswith('.json')
            assert os.path.exists(temp_path)
        finally:
            os.unlink(temp_path)


class TestMockHelpers:
    """Test mock helper utilities."""
    
    def test_mock_creation(self):
        """Test creating basic mocks."""
        mock_obj = MagicMock()
        mock_obj.test_method.return_value = "test_result"
        
        result = mock_obj.test_method()
        assert result == "test_result"
        mock_obj.test_method.assert_called_once()
    
    def test_mock_with_spec(self):
        """Test creating mocks with specifications."""
        class TestClass:
            def method1(self):
                pass
            
            def method2(self, arg):
                pass
        
        mock_obj = MagicMock(spec=TestClass)
        mock_obj.method1.return_value = "result1"
        mock_obj.method2.return_value = "result2"
        
        assert mock_obj.method1() == "result1"
        assert mock_obj.method2("test") == "result2"
    
    def test_mock_side_effects(self):
        """Test mock side effects."""
        mock_func = MagicMock(side_effect=[1, 2, 3, ValueError("Error")])
        
        assert mock_func() == 1
        assert mock_func() == 2
        assert mock_func() == 3
        
        with pytest.raises(ValueError, match="Error"):
            mock_func()
    
    def test_mock_call_tracking(self):
        """Test tracking mock calls."""
        mock_func = MagicMock()
        
        mock_func("arg1", "arg2", keyword="value")
        mock_func("arg3")
        
        assert mock_func.call_count == 2
        mock_func.assert_any_call("arg1", "arg2", keyword="value")
        mock_func.assert_any_call("arg3")


class TestPatchHelpers:
    """Test patch helper utilities."""
    
    @patch('os.path.exists')
    def test_patch_function(self, mock_exists):
        """Test patching functions."""
        mock_exists.return_value = True
        
        result = os.path.exists("/fake/path")
        assert result is True
        mock_exists.assert_called_once_with("/fake/path")
    
    @patch('builtins.open', create=True)
    def test_patch_builtin(self, mock_open):
        """Test patching built-in functions."""
        mock_file = MagicMock()
        mock_file.read.return_value = "test content"
        mock_open.return_value.__enter__.return_value = mock_file
        
        with open("test.txt", 'r') as f:
            content = f.read()
        
        assert content == "test content"
        mock_open.assert_called_once_with("test.txt", 'r')
    
    def test_patch_as_context_manager(self):
        """Test using patch as context manager."""
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            result = os.path.exists("/fake/path")
            assert result is False
            mock_exists.assert_called_once_with("/fake/path")
    
    def test_patch_object(self):
        """Test patching object methods."""
        class TestClass:
            def method(self):
                return "original"
        
        obj = TestClass()
        
        with patch.object(obj, 'method') as mock_method:
            mock_method.return_value = "patched"
            
            result = obj.method()
            assert result == "patched"
            mock_method.assert_called_once()


class TestDateTimeHelpers:
    """Test datetime helper utilities."""
    
    def test_datetime_creation(self):
        """Test creating datetime objects."""
        dt = datetime(2023, 12, 25, 15, 30, 45)
        assert dt.year == 2023
        assert dt.month == 12
        assert dt.day == 25
        assert dt.hour == 15
        assert dt.minute == 30
        assert dt.second == 45
    
    def test_datetime_arithmetic(self):
        """Test datetime arithmetic."""
        dt1 = datetime(2023, 12, 25, 12, 0, 0)
        dt2 = dt1 + timedelta(hours=2, minutes=30)
        
        assert dt2.hour == 14
        assert dt2.minute == 30
        
        diff = dt2 - dt1
        assert diff.total_seconds() == 2.5 * 3600  # 2.5 hours in seconds
    
    def test_datetime_comparison(self):
        """Test datetime comparisons."""
        dt1 = datetime(2023, 12, 25, 12, 0, 0)
        dt2 = datetime(2023, 12, 25, 13, 0, 0)
        dt3 = datetime(2023, 12, 25, 12, 0, 0)
        
        assert dt2 > dt1
        assert dt1 < dt2
        assert dt1 == dt3
        assert dt1 != dt2
    
    def test_datetime_formatting(self):
        """Test datetime formatting."""
        dt = datetime(2023, 12, 25, 15, 30, 45)
        
        iso_format = dt.isoformat()
        assert iso_format == "2023-12-25T15:30:45"
        
        custom_format = dt.strftime("%Y-%m-%d %H:%M:%S")
        assert custom_format == "2023-12-25 15:30:45"


class TestAssertionHelpers:
    """Test assertion helper utilities."""
    
    def test_basic_assertions(self):
        """Test basic assertion patterns."""
        value = 42
        assert value == 42
        assert value != 0
        assert value > 0
        assert value < 100
        assert value >= 42
        assert value <= 42
    
    def test_collection_assertions(self):
        """Test collection assertion patterns."""
        test_list = [1, 2, 3, 4, 5]
        
        assert len(test_list) == 5
        assert 3 in test_list
        assert 6 not in test_list
        assert test_list[0] == 1
        assert test_list[-1] == 5
    
    def test_string_assertions(self):
        """Test string assertion patterns."""
        test_string = "Hello, World!"
        
        assert "Hello" in test_string
        assert test_string.startswith("Hello")
        assert test_string.endswith("World!")
        assert len(test_string) == 13
        assert test_string.lower() == "hello, world!"
    
    def test_exception_assertions(self):
        """Test exception assertion patterns."""
        def divide_by_zero():
            return 1 / 0
        
        with pytest.raises(ZeroDivisionError):
            divide_by_zero()
        
        def custom_error():
            raise ValueError("Custom error message")
        
        with pytest.raises(ValueError, match="Custom error message"):
            custom_error()
    
    def test_approximate_assertions(self):
        """Test approximate value assertions."""
        value = 0.1 + 0.2  # Floating point precision issue
        
        assert value == pytest.approx(0.3)
        assert value == pytest.approx(0.3, abs=1e-10)
        assert value == pytest.approx(0.3, rel=1e-10)


class TestFixtureHelpers:
    """Test fixture helper patterns."""
    
    @pytest.fixture
    def sample_data(self):
        """Sample data fixture."""
        return {
            "name": "Test User",
            "email": "test@example.com",
            "age": 30,
            "active": True
        }
    
    @pytest.fixture
    def temp_file(self):
        """Temporary file fixture."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    def test_using_sample_data_fixture(self, sample_data):
        """Test using sample data fixture."""
        assert sample_data["name"] == "Test User"
        assert sample_data["email"] == "test@example.com"
        assert sample_data["age"] == 30
        assert sample_data["active"] is True
    
    def test_using_temp_file_fixture(self, temp_file):
        """Test using temporary file fixture."""
        assert os.path.exists(temp_file)
        
        with open(temp_file, 'r') as f:
            content = f.read()
        
        assert content == "test content"


class TestParametrizedTests:
    """Test parametrized test patterns."""
    
    @pytest.mark.parametrize("input_value,expected", [
        (1, 2),
        (2, 4),
        (3, 6),
        (4, 8),
        (5, 10)
    ])
    def test_double_function(self, input_value, expected):
        """Test parametrized function testing."""
        def double(x):
            return x * 2
        
        result = double(input_value)
        assert result == expected
    
    @pytest.mark.parametrize("text,expected_length", [
        ("hello", 5),
        ("world", 5),
        ("", 0),
        ("a", 1),
        ("testing", 7)
    ])
    def test_string_length(self, text, expected_length):
        """Test parametrized string length testing."""
        assert len(text) == expected_length
    
    @pytest.mark.parametrize("value,is_positive", [
        (1, True),
        (-1, False),
        (0, False),
        (100, True),
        (-100, False)
    ])
    def test_positive_numbers(self, value, is_positive):
        """Test parametrized positive number checking."""
        result = value > 0
        assert result == is_positive


class TestAsyncTestPatterns:
    """Test async testing patterns."""
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test basic async function."""
        async def async_add(a, b):
            await asyncio.sleep(0.001)  # Simulate async work
            return a + b
        
        result = await async_add(2, 3)
        assert result == 5
    
    @pytest.mark.asyncio
    async def test_async_exception(self):
        """Test async function that raises exception."""
        async def async_error():
            await asyncio.sleep(0.001)
            raise ValueError("Async error")
        
        with pytest.raises(ValueError, match="Async error"):
            await async_error()
    
    @pytest.mark.asyncio
    async def test_async_timeout(self):
        """Test async function with timeout."""
        async def slow_function():
            await asyncio.sleep(1.0)  # 1 second delay
            return "done"
        
        # Test with timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_function(), timeout=0.1)
    
    @pytest.mark.asyncio
    async def test_async_mock_integration(self):
        """Test integration of async functions with mocks."""
        mock_async_func = AsyncMock(return_value="mocked_result")
        
        result = await mock_async_func("test_arg")
        assert result == "mocked_result"
        mock_async_func.assert_called_once_with("test_arg")