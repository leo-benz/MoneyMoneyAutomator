import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from llm_client import LMStudioClient


class TestLMStudioClient:
    
    def setup_method(self):
        self.client = LMStudioClient()
        self.sample_transaction = {
            'name': 'STARBUCKS STORE #12345',
            'amount': -4.50,
            'purpose': 'Coffee purchase'
        }
        self.sample_categories = [
            {'uuid': '123', 'full_name': 'Food & Dining\\Coffee', 'name': 'Coffee'},
            {'uuid': '456', 'full_name': 'Transportation\\Gas', 'name': 'Gas'},
            {'uuid': '789', 'full_name': 'Shopping\\Groceries', 'name': 'Groceries'}
        ]
    
    def test_init(self):
        assert self.client.base_url == 'http://localhost:1234/v1'
        assert self.client.session is not None
        assert self.client.session.headers['Content-Type'] == 'application/json'
    
    @patch('llm_client.Config.LM_STUDIO_BASE_URL', 'http://custom:8080/v1')
    def test_custom_base_url(self):
        client = LMStudioClient()
        assert client.base_url == 'http://custom:8080/v1'
    
    def test_format_categories_for_prompt(self):
        result = self.client._format_categories_for_prompt(self.sample_categories)
        expected_lines = [
            '- Food & Dining\\Coffee (UUID: 123)',
            '- Transportation\\Gas (UUID: 456)',
            '- Shopping\\Groceries (UUID: 789)'
        ]
        assert result == '\n'.join(expected_lines)
    
    def test_build_categorization_prompt(self):
        category_list = "- Food & Dining\\Coffee (UUID: 123)"
        prompt = self.client._build_categorization_prompt(self.sample_transaction, category_list)
        
        assert 'STARBUCKS STORE #12345' in prompt
        assert '-4.5' in prompt
        assert 'Coffee purchase' in prompt
        assert 'Food & Dining\\Coffee' in prompt
        assert '"suggestions":' in prompt
    
    def test_build_categorization_prompt_missing_fields(self):
        incomplete_transaction = {'name': 'Test Transaction'}
        category_list = "- Category (UUID: 123)"
        prompt = self.client._build_categorization_prompt(incomplete_transaction, category_list)
        
        assert 'Test Transaction' in prompt
        assert 'Amount: 0' in prompt
        # With new format, description is only included if purpose has meaningful content
        assert 'Merchant/Name: Test Transaction' in prompt
    
    @patch('requests.Session.post')
    def test_call_llm_success(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'test response'}}]
        }
        mock_post.return_value = mock_response
        
        result = self.client._call_llm("test prompt")
        
        assert result == 'test response'
        mock_post.assert_called_once()
        
        call_args = mock_post.call_args
        assert 'json' in call_args[1]
        payload = call_args[1]['json']
        assert payload['messages'][0]['content'] == 'test prompt'
        assert payload['temperature'] == 0.3
        assert payload['max_tokens'] == 4000
    
    @patch('requests.Session.post')
    def test_call_llm_network_error(self, mock_post):
        mock_post.side_effect = Exception("Network error")
        
        with pytest.raises(Exception, match="Network error"):
            self.client._call_llm("test prompt")
    
    def test_parse_suggestions_valid_json(self):
        llm_response = json.dumps({
            "suggestions": [
                {
                    "category_path": "Food & Dining\\Coffee",
                    "uuid": "123",
                    "confidence": 0.9,
                    "reasoning": "Starbucks is a coffee shop"
                }
            ]
        })
        
        result = self.client._parse_suggestions(llm_response, self.sample_categories)
        
        assert len(result) == 1
        assert result[0]['category']['uuid'] == '123'
        assert result[0]['confidence'] == 0.9
        assert result[0]['reasoning'] == "Starbucks is a coffee shop"
    
    def test_parse_suggestions_invalid_json(self):
        invalid_json = "Not valid JSON"
        result = self.client._parse_suggestions(invalid_json, self.sample_categories)
        assert result == []
    
    def test_parse_suggestions_no_matching_category(self):
        llm_response = json.dumps({
            "suggestions": [
                {
                    "category_path": "Nonexistent Category",
                    "uuid": "999",
                    "confidence": 0.8,
                    "reasoning": "Test"
                }
            ]
        })
        
        result = self.client._parse_suggestions(llm_response, self.sample_categories)
        assert result == []
    
    def test_find_category_by_uuid(self):
        result = self.client._find_category_by_path_or_uuid(
            self.sample_categories, "", "123"
        )
        assert result['uuid'] == '123'
        assert result['full_name'] == 'Food & Dining\\Coffee'
    
    def test_find_category_by_path(self):
        result = self.client._find_category_by_path_or_uuid(
            self.sample_categories, "Food & Dining\\Coffee", ""
        )
        assert result['uuid'] == '123'
    
    def test_find_category_by_partial_path(self):
        result = self.client._find_category_by_path_or_uuid(
            self.sample_categories, "coffee", ""
        )
        assert result['uuid'] == '123'
    
    def test_find_category_not_found(self):
        result = self.client._find_category_by_path_or_uuid(
            self.sample_categories, "Nonexistent", "999"
        )
        assert result is None
    
    @patch('requests.Session.get')
    def test_test_connection_success(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'data': [{'id': 'test-model'}]
        }
        mock_get.return_value = mock_response
        
        result = self.client.test_connection()
        
        assert result is True
        mock_get.assert_called_once_with(
            'http://localhost:1234/v1/models', timeout=5
        )
    
    @patch('requests.Session.get')
    def test_test_connection_failure(self, mock_get):
        mock_get.side_effect = Exception("Connection failed")
        
        result = self.client.test_connection()
        assert result is False
    
    @patch.object(LMStudioClient, '_call_llm')
    @patch.object(LMStudioClient, '_parse_suggestions')
    def test_categorize_transaction_success(self, mock_parse, mock_call):
        mock_call.return_value = "mock llm response"
        mock_suggestions = [{'category': {'uuid': '123'}, 'confidence': 0.9}]
        mock_parse.return_value = mock_suggestions
        
        result = self.client.categorize_transaction(
            self.sample_transaction, self.sample_categories
        )
        
        assert result == mock_suggestions[:5]
        mock_call.assert_called_once()
        mock_parse.assert_called_once_with("mock llm response", self.sample_categories)
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_categorize_transaction_llm_error(self, mock_call):
        mock_call.side_effect = Exception("LLM error")
        
        result = self.client.categorize_transaction(
            self.sample_transaction, self.sample_categories
        )
        
        assert result == []
    
    @patch('requests.Session.get')
    def test_get_available_models_success(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {
            'data': [
                {'id': 'deepseek/deepseek-r1-0528-qwen3-8b'},
                {'id': 'google/gemma-3-1b'}
            ]
        }
        mock_get.return_value = mock_response
        
        models = self.client._get_available_models()
        
        assert len(models) == 2
        assert 'deepseek/deepseek-r1-0528-qwen3-8b' in models
        assert 'google/gemma-3-1b' in models
    
    @patch('requests.Session.get')
    def test_get_available_models_error(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        
        models = self.client._get_available_models()
        
        assert models == []
    
    @patch.object(LMStudioClient, '_get_available_models')
    def test_get_model_to_use_configured(self, mock_get_models):
        self.client.model = 'configured-model'
        
        model = self.client._get_model_to_use()
        
        assert model == 'configured-model'
        mock_get_models.assert_not_called()
    
    @patch.object(LMStudioClient, '_get_available_models')
    def test_get_model_to_use_single_model(self, mock_get_models):
        self.client.model = None
        mock_get_models.return_value = ['single-model']
        
        model = self.client._get_model_to_use()
        
        assert model == 'single-model'
    
    @patch.object(LMStudioClient, '_get_available_models')
    def test_get_model_to_use_prefer_chat_model(self, mock_get_models):
        self.client.model = None
        mock_get_models.return_value = ['text-model', 'chat-model', 'instruct-model']
        
        model = self.client._get_model_to_use()
        
        assert model == 'chat-model'
    
    @patch.object(LMStudioClient, '_get_available_models')
    def test_get_model_to_use_first_model_fallback(self, mock_get_models):
        self.client.model = None
        mock_get_models.return_value = ['first-model', 'second-model']
        
        model = self.client._get_model_to_use()
        
        assert model == 'first-model'
    
    @patch.object(LMStudioClient, '_get_available_models')
    def test_get_model_to_use_no_models(self, mock_get_models):
        self.client.model = None
        mock_get_models.return_value = []
        
        model = self.client._get_model_to_use()
        
        assert model is None
    
    @patch.object(LMStudioClient, '_get_model_to_use')
    @patch('requests.Session.post')
    def test_call_llm_with_model(self, mock_post, mock_get_model):
        mock_get_model.return_value = 'test-model'
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'test response'}}]
        }
        mock_post.return_value = mock_response
        
        result = self.client._call_llm("test prompt")
        
        assert result == 'test response'
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['model'] == 'test-model'