import os
from datetime import datetime, timedelta

class Config:
    LM_STUDIO_BASE_URL = os.getenv('LM_STUDIO_URL', 'http://localhost:1234/v1')
    
    NUM_SUGGESTIONS = int(os.getenv('NUM_SUGGESTIONS', '5'))
    
    DEFAULT_FROM_DATE = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    SEARCH_MIN_CHARS = 2
    
    MAX_SEARCH_RESULTS = 10