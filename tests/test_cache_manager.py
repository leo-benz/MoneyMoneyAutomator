import pytest
import json
import os
import tempfile
from unittest.mock import patch, mock_open
import sys
import shutil

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cache_manager import CacheManager


class TestCacheManager:
    
    def setup_method(self):
        """Setup test environment with temporary cache file."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.temp_dir, 'test_cache.json')
        self.cache_manager = CacheManager(self.cache_file)
        
    def teardown_method(self):
        """Clean up temporary files."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_cache_creation_and_storage(self):
        """Test that cache can be created and data stored."""
        transaction_id = 12345
        suggestions = [
            {
                'category': {'uuid': '1', 'full_name': 'Food & Dining\\Coffee'},
                'confidence': 0.9,
                'reasoning': 'Coffee shop transaction'
            }
        ]
        
        # Store suggestions
        self.cache_manager.store_suggestions(transaction_id, suggestions)
        
        # Verify cache file was created
        assert os.path.exists(self.cache_file)
        
        # Verify data was stored correctly
        with open(self.cache_file, 'r') as f:
            cache_data = json.load(f)
        
        assert str(transaction_id) in cache_data
        assert cache_data[str(transaction_id)] == suggestions
    
    def test_cache_retrieval_by_transaction_id(self):
        """Test that cached suggestions can be retrieved by transaction ID."""
        transaction_id = 12345
        suggestions = [
            {
                'category': {'uuid': '2', 'full_name': 'Transportation\\Gas'},
                'confidence': 0.8,
                'reasoning': 'Gas station transaction'
            }
        ]
        
        # Store and retrieve
        self.cache_manager.store_suggestions(transaction_id, suggestions)
        retrieved = self.cache_manager.get_suggestions(transaction_id)
        
        assert retrieved == suggestions
    
    def test_cache_retrieval_nonexistent_transaction(self):
        """Test that retrieving non-existent transaction returns None."""
        result = self.cache_manager.get_suggestions(99999)
        assert result is None
    
    def test_cache_cleanup_after_categorization(self):
        """Test that cache entry is removed after transaction is processed."""
        transaction_id = 12345
        suggestions = [
            {
                'category': {'uuid': '1', 'full_name': 'Food & Dining\\Coffee'},
                'confidence': 0.9,
                'reasoning': 'Coffee shop transaction'
            }
        ]
        
        # Store suggestions
        self.cache_manager.store_suggestions(transaction_id, suggestions)
        assert self.cache_manager.get_suggestions(transaction_id) is not None
        
        # Clean up entry
        self.cache_manager.remove_suggestions(transaction_id)
        assert self.cache_manager.get_suggestions(transaction_id) is None
    
    def test_cache_cleanup_after_skip(self):
        """Test that cache entry is removed when transaction is skipped."""
        transaction_id = 12345
        suggestions = [
            {
                'category': {'uuid': '1', 'full_name': 'Food & Dining\\Coffee'},
                'confidence': 0.9,
                'reasoning': 'Coffee shop transaction'
            }
        ]
        
        # Store and then remove (simulating skip)
        self.cache_manager.store_suggestions(transaction_id, suggestions)
        self.cache_manager.remove_suggestions(transaction_id)
        
        # Verify removal
        assert self.cache_manager.get_suggestions(transaction_id) is None
    
    def test_invalid_cache_file_handling(self):
        """Test handling of corrupted or invalid cache files."""
        # Create invalid JSON file
        with open(self.cache_file, 'w') as f:
            f.write('invalid json content')
        
        # Should handle gracefully and create new cache
        cache_manager = CacheManager(self.cache_file)
        transaction_id = 12345
        suggestions = [{'test': 'data'}]
        
        # Should work despite corrupted file
        cache_manager.store_suggestions(transaction_id, suggestions)
        result = cache_manager.get_suggestions(transaction_id)
        
        assert result == suggestions
    
    def test_multiple_transactions_in_cache(self):
        """Test storing and retrieving multiple transactions."""
        transactions = {
            12345: [{'category': {'uuid': '1', 'full_name': 'Food\\Coffee'}, 'confidence': 0.9}],
            12346: [{'category': {'uuid': '2', 'full_name': 'Transport\\Gas'}, 'confidence': 0.8}],
            12347: [{'category': {'uuid': '3', 'full_name': 'Shopping\\Groceries'}, 'confidence': 0.7}]
        }
        
        # Store all transactions
        for tid, suggestions in transactions.items():
            self.cache_manager.store_suggestions(tid, suggestions)
        
        # Verify all can be retrieved
        for tid, expected_suggestions in transactions.items():
            retrieved = self.cache_manager.get_suggestions(tid)
            assert retrieved == expected_suggestions
        
        # Remove one and verify others remain
        self.cache_manager.remove_suggestions(12346)
        assert self.cache_manager.get_suggestions(12346) is None
        assert self.cache_manager.get_suggestions(12345) is not None
        assert self.cache_manager.get_suggestions(12347) is not None
    
    def test_cache_persistence_across_instances(self):
        """Test that cache persists across different CacheManager instances."""
        transaction_id = 12345
        suggestions = [{'test': 'persistence'}]
        
        # Store with first instance
        self.cache_manager.store_suggestions(transaction_id, suggestions)
        
        # Create new instance with same cache file
        new_cache_manager = CacheManager(self.cache_file)
        retrieved = new_cache_manager.get_suggestions(transaction_id)
        
        assert retrieved == suggestions
    
    def test_empty_suggestions_handling(self):
        """Test handling of empty suggestions list."""
        transaction_id = 12345
        empty_suggestions = []
        
        self.cache_manager.store_suggestions(transaction_id, empty_suggestions)
        retrieved = self.cache_manager.get_suggestions(transaction_id)
        
        assert retrieved == empty_suggestions
    
    def test_get_all_cached_transaction_ids(self):
        """Test retrieving all cached transaction IDs."""
        transaction_ids = [12345, 12346, 12347]
        
        for tid in transaction_ids:
            self.cache_manager.store_suggestions(tid, [{'test': f'data_{tid}'}])
        
        cached_ids = self.cache_manager.get_cached_transaction_ids()
        
        # Convert to int for comparison (cache stores as strings)
        cached_ids_int = [int(tid) for tid in cached_ids]
        
        for tid in transaction_ids:
            assert tid in cached_ids_int
    
    def test_clear_all_cache(self):
        """Test clearing entire cache."""
        # Store multiple transactions
        for tid in [12345, 12346, 12347]:
            self.cache_manager.store_suggestions(tid, [{'test': f'data_{tid}'}])
        
        # Verify cache has data
        assert len(self.cache_manager.get_cached_transaction_ids()) == 3
        
        # Clear cache
        self.cache_manager.clear_cache()
        
        # Verify cache is empty
        assert len(self.cache_manager.get_cached_transaction_ids()) == 0
        assert self.cache_manager.get_suggestions(12345) is None