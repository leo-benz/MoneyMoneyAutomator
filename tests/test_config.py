import os
import pytest
from unittest.mock import patch
from config import Config


class TestConfig:
    
    def test_default_values(self):
        assert Config.LM_STUDIO_BASE_URL == 'http://localhost:1234/v1'
        assert Config.NUM_SUGGESTIONS == 5
        assert Config.LOG_LEVEL == 'INFO'
        assert Config.SEARCH_MIN_CHARS == 2
        assert Config.MAX_SEARCH_RESULTS == 10
    
    @patch.dict(os.environ, {'LM_STUDIO_URL': 'http://custom:8080/v1'})
    def test_custom_lm_studio_url(self):
        from importlib import reload
        import config
        reload(config)
        assert config.Config.LM_STUDIO_BASE_URL == 'http://custom:8080/v1'
    
    @patch.dict(os.environ, {'NUM_SUGGESTIONS': '3'})
    def test_custom_num_suggestions(self):
        from importlib import reload
        import config
        reload(config)
        assert config.Config.NUM_SUGGESTIONS == 3
    
    @patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'})
    def test_custom_log_level(self):
        from importlib import reload
        import config
        reload(config)
        assert config.Config.LOG_LEVEL == 'DEBUG'
    
    def test_default_from_date_format(self):
        from datetime import datetime
        date_str = Config.DEFAULT_FROM_DATE
        datetime.strptime(date_str, '%Y-%m-%d')