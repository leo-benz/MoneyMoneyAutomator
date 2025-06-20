import pytest
import sys
import os
from unittest.mock import patch

# Add the parent directory to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def mock_config():
    """Mock configuration for tests"""
    with patch('config.Config') as mock:
        mock.LM_STUDIO_BASE_URL = 'http://localhost:1234/v1'
        mock.NUM_SUGGESTIONS = 5
        mock.DEFAULT_FROM_DATE = '2024-01-01'
        mock.LOG_LEVEL = 'INFO'
        mock.SEARCH_MIN_CHARS = 2
        mock.MAX_SEARCH_RESULTS = 10
        yield mock

@pytest.fixture
def sample_transaction():
    """Sample transaction for testing"""
    return {
        'id': 12345,
        'name': 'STARBUCKS STORE #12345',
        'amount': -4.50,
        'currency': 'EUR',
        'date': '2024-01-15',
        'purpose': 'Coffee purchase'
    }

@pytest.fixture
def sample_categories():
    """Sample categories for testing"""
    return [
        {'uuid': '1', 'name': 'Coffee', 'full_name': 'Food & Dining\\Coffee'},
        {'uuid': '2', 'name': 'Gas', 'full_name': 'Transportation\\Gas'},
        {'uuid': '3', 'name': 'Groceries', 'full_name': 'Shopping\\Groceries'},
        {'uuid': '4', 'name': 'Restaurants', 'full_name': 'Food & Dining\\Restaurants'},
        {'uuid': '5', 'name': 'Utilities', 'full_name': 'Bills\\Utilities'}
    ]

@pytest.fixture
def sample_suggestions():
    """Sample AI suggestions for testing"""
    return [
        {
            'category': {'uuid': '1', 'full_name': 'Food & Dining\\Coffee'},
            'confidence': 0.9,
            'reasoning': 'Transaction at coffee shop'
        },
        {
            'category': {'uuid': '2', 'full_name': 'Transportation\\Gas'},
            'confidence': 0.7,
            'reasoning': 'Gas station transaction'
        }
    ]

@pytest.fixture
def mock_logger():
    """Mock logger for testing"""
    with patch('logging.getLogger') as mock:
        yield mock.return_value