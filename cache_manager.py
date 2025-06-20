import json
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages caching of AI suggestions for transactions."""
    
    def __init__(self, cache_file_path: str = "ai_cache.json"):
        self.cache_file_path = cache_file_path
        self._cache = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from file if it exists."""
        if os.path.exists(self.cache_file_path):
            try:
                with open(self.cache_file_path, 'r') as f:
                    self._cache = json.load(f)
                logger.info(f"Loaded cache with {len(self._cache)} entries from {self.cache_file_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cache file {self.cache_file_path}: {e}")
                logger.info("Starting with empty cache")
                self._cache = {}
        else:
            logger.info("No cache file found, starting with empty cache")
            self._cache = {}
    
    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            # Create directory if it doesn't exist
            cache_dir = os.path.dirname(self.cache_file_path)
            if cache_dir and not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
            
            with open(self.cache_file_path, 'w') as f:
                json.dump(self._cache, f, indent=2)
            logger.debug(f"Saved cache with {len(self._cache)} entries to {self.cache_file_path}")
        except IOError as e:
            logger.error(f"Failed to save cache to {self.cache_file_path}: {e}")
    
    def store_suggestions(self, transaction_id: int, suggestions: List[Dict]) -> None:
        """Store AI suggestions for a transaction."""
        transaction_key = str(transaction_id)
        self._cache[transaction_key] = suggestions
        self._save_cache()
        logger.debug(f"Cached {len(suggestions)} suggestions for transaction {transaction_id}")
    
    def get_suggestions(self, transaction_id: int) -> Optional[List[Dict]]:
        """Retrieve cached suggestions for a transaction."""
        transaction_key = str(transaction_id)
        suggestions = self._cache.get(transaction_key)
        if suggestions is not None:
            logger.debug(f"Retrieved {len(suggestions)} cached suggestions for transaction {transaction_id}")
        else:
            logger.debug(f"No cached suggestions found for transaction {transaction_id}")
        return suggestions
    
    def remove_suggestions(self, transaction_id: int) -> None:
        """Remove cached suggestions for a transaction."""
        transaction_key = str(transaction_id)
        if transaction_key in self._cache:
            del self._cache[transaction_key]
            self._save_cache()
            logger.debug(f"Removed cached suggestions for transaction {transaction_id}")
        else:
            logger.debug(f"No cached suggestions to remove for transaction {transaction_id}")
    
    def get_cached_transaction_ids(self) -> List[str]:
        """Get all transaction IDs that have cached suggestions."""
        return list(self._cache.keys())
    
    def clear_cache(self) -> None:
        """Clear all cached suggestions."""
        self._cache = {}
        self._save_cache()
        logger.info("Cleared all cached suggestions")
    
    def has_suggestions(self, transaction_id: int) -> bool:
        """Check if transaction has cached suggestions."""
        return str(transaction_id) in self._cache
    
    def get_cache_size(self) -> int:
        """Get the number of cached transactions."""
        return len(self._cache)