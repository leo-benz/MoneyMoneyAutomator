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
        assert payload['max_tokens'] == 8000
    
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
    
    def test_parse_suggestions_removes_duplicate_uuids(self):
        """Test that duplicate category UUIDs are filtered out."""
        llm_response = json.dumps({
            "suggestions": [
                {
                    "category_path": "Food & Dining\\Coffee",
                    "uuid": "123",
                    "confidence": 0.9,
                    "reasoning": "First suggestion"
                },
                {
                    "category_path": "Food & Dining\\Coffee",
                    "uuid": "123",
                    "confidence": 0.8,
                    "reasoning": "Duplicate suggestion"
                },
                {
                    "category_path": "Entertainment\\Movies",
                    "uuid": "456",
                    "confidence": 0.7,
                    "reasoning": "Different category"
                }
            ]
        })
        
        result = self.client._parse_suggestions(llm_response, self.sample_categories)
        
        # Should only have 2 suggestions (duplicate UUID removed)
        assert len(result) == 2
        
        # Should have only unique UUIDs
        uuids = [suggestion['category']['uuid'] for suggestion in result]
        assert len(set(uuids)) == len(uuids)
        assert '123' in uuids
        assert '456' in uuids
        
        # First occurrence should be kept (highest confidence)
        coffee_suggestion = next(s for s in result if s['category']['uuid'] == '123')
        assert coffee_suggestion['confidence'] == 0.9
        assert coffee_suggestion['reasoning'] == "First suggestion"
    
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


class TestRuleGeneration:
    """Test AI rule generation functionality."""
    
    def setup_method(self):
        with patch('llm_client.Config') as mock_config:
            mock_config.LM_STUDIO_BASE_URL = 'http://localhost:1234/v1'
            mock_config.LM_STUDIO_MODEL = None
            mock_config.NUM_SUGGESTIONS = 5
            self.client = LMStudioClient()
        
        self.sample_transaction = {
            'id': 12345,
            'name': 'STARBUCKS STORE #12345',
            'amount': -4.50,
            'currency': 'EUR',
            'date': '2024-01-15',
            'purpose': 'Coffee purchase'
        }
        
        self.sample_category = {
            'uuid': 'coffee-uuid',
            'full_name': 'Food & Dining\\Coffee'
        }
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_generate_categorization_rule_basic(self, mock_call_llm):
        """Test basic rule generation."""
        mock_call_llm.return_value = '''
        {
            "rule": "name:\\"STARBUCKS\\"",
            "explanation": "Matches all Starbucks transactions",
            "confidence": 0.9
        }
        '''
        
        result = self.client.generate_categorization_rule(self.sample_transaction, self.sample_category)
        
        assert result is not None
        assert 'rule' in result
        assert 'explanation' in result
        assert 'confidence' in result
        assert 'STARBUCKS' in result['rule']
        mock_call_llm.assert_called_once()
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_rule_generation_with_merchant_name(self, mock_call_llm):
        """Test rule generation focusing on merchant name."""
        mock_call_llm.return_value = '''
        {
            "rule": "name:\\"STARBUCKS\\"",
            "explanation": "Categorizes all Starbucks transactions as coffee purchases",
            "confidence": 0.95
        }
        '''
        
        result = self.client.generate_categorization_rule(self.sample_transaction, self.sample_category)
        
        assert 'name:' in result['rule']
        assert 'STARBUCKS' in result['rule']
        assert result['confidence'] >= 0.9
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_rule_generation_with_purpose_keywords(self, mock_call_llm):
        """Test rule generation using purpose keywords."""
        transaction_with_purpose = {
            **self.sample_transaction,
            'purpose': 'COFFEE SHOP PURCHASE VISA-DEB'
        }
        
        mock_call_llm.return_value = '''
        {
            "rule": "purpose:\\"COFFEE\\"",
            "explanation": "Matches transactions with coffee-related keywords in purpose",
            "confidence": 0.85
        }
        '''
        
        result = self.client.generate_categorization_rule(transaction_with_purpose, self.sample_category)
        
        assert 'purpose:' in result['rule']
        assert 'COFFEE' in result['rule']
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_rule_generation_with_amount_conditions(self, mock_call_llm):
        """Test rule generation with amount-based conditions."""
        small_transaction = {
            **self.sample_transaction,
            'amount': -5.50
        }
        
        mock_call_llm.return_value = '''
        {
            "rule": "name:\\"STARBUCKS\\" AND amount<10.00",
            "explanation": "Matches small Starbucks purchases typically for coffee",
            "confidence": 0.80
        }
        '''
        
        result = self.client.generate_categorization_rule(small_transaction, self.sample_category)
        
        assert 'amount<' in result['rule'] or 'amount>' in result['rule']
        assert 'STARBUCKS' in result['rule']
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_rule_validation_moneymoney_syntax(self, mock_call_llm):
        """Test that generated rules follow MoneyMoney syntax."""
        mock_call_llm.return_value = '''
        {
            "rule": "name:\\"STARBUCKS\\" OR name:\\"COSTA\\"",
            "explanation": "Matches multiple coffee chain merchants",
            "confidence": 0.90
        }
        '''
        
        result = self.client.generate_categorization_rule(self.sample_transaction, self.sample_category)
        
        rule = result['rule']
        # Check for valid MoneyMoney syntax patterns
        assert any(pattern in rule for pattern in ['name:', 'purpose:', 'amount', 'AND', 'OR'])
        # Check for proper quoting
        if 'name:' in rule:
            assert '"' in rule  # Should have quoted values
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_rule_generation_error_handling(self, mock_call_llm):
        """Test error handling in rule generation."""
        # Test JSON parsing error
        mock_call_llm.return_value = 'invalid json'
        
        result = self.client.generate_categorization_rule(self.sample_transaction, self.sample_category)
        
        assert result is None
        
        # Test LLM call failure
        mock_call_llm.side_effect = Exception("LLM call failed")
        
        result = self.client.generate_categorization_rule(self.sample_transaction, self.sample_category)
        
        assert result is None
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_rule_generation_complex_scenarios(self, mock_call_llm):
        """Test rule generation for complex transaction scenarios."""
        complex_transaction = {
            'id': 12346,
            'name': 'SHELL 1234567',
            'amount': -85.50,
            'purpose': 'FUEL PURCHASE CONTACTLESS',
            'bookingText': 'DEBIT CARD PAYMENT'
        }
        
        gas_category = {
            'uuid': 'gas-uuid',
            'full_name': 'Transportation\\Gas'
        }
        
        mock_call_llm.return_value = '''
        {
            "rule": "name:\\"SHELL\\" AND purpose:\\"FUEL\\" AND amount>50.00",
            "explanation": "Matches Shell gas station purchases over $50 for fuel",
            "confidence": 0.92
        }
        '''
        
        result = self.client.generate_categorization_rule(complex_transaction, gas_category)
        
        assert 'SHELL' in result['rule']
        assert 'FUEL' in result['rule']
        assert 'amount>' in result['rule']
        assert result['confidence'] > 0.9


class TestEnhancedCategorization:
    """Test enhanced categorization with hierarchical category context."""
    
    def setup_method(self):
        with patch('llm_client.Config') as mock_config:
            mock_config.LM_STUDIO_BASE_URL = 'http://localhost:1234/v1'
            mock_config.LM_STUDIO_MODEL = None
            mock_config.NUM_SUGGESTIONS = 5
            self.client = LMStudioClient()
        
        self.sample_transaction = {
            'id': 12345,
            'name': 'STARBUCKS STORE #12345',
            'amount': -4.50,
            'currency': 'EUR',
            'date': '2024-01-15',
            'purpose': 'Coffee purchase'
        }
        
        # Enhanced categories with parent context
        self.enhanced_categories = [
            {
                'uuid': 'starbucks-uuid',
                'name': 'Starbucks',
                'full_name': 'Food & Dining\\Coffee Shops\\Starbucks',
                'parent_path': 'Food & Dining\\Coffee Shops',
                'hierarchy_level': 3
            },
            {
                'uuid': 'coffee-uuid',
                'name': 'Coffee',
                'full_name': 'Food & Dining\\Coffee',
                'parent_path': 'Food & Dining',
                'hierarchy_level': 2
            },
            {
                'uuid': 'gas-uuid',
                'name': 'Gas',
                'full_name': 'Transportation\\Gas',
                'parent_path': 'Transportation',
                'hierarchy_level': 2
            }
        ]
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_enhanced_categorization_prompt_with_hierarchy(self, mock_call_llm):
        """Test that categorization prompts include hierarchical context."""
        mock_call_llm.return_value = '''
        {
            "suggestions": [
                {
                    "category_path": "Food & Dining\\\\Coffee Shops\\\\Starbucks",
                    "uuid": "starbucks-uuid",
                    "confidence": 0.95,
                    "reasoning": "Direct match with Starbucks coffee shop"
                }
            ]
        }
        '''
        
        result = self.client.categorize_transaction(self.sample_transaction, self.enhanced_categories)
        
        assert len(result) == 1
        assert result[0]['category']['full_name'] == 'Food & Dining\\Coffee Shops\\Starbucks'
        
        # Check that the prompt included hierarchical information
        call_args = mock_call_llm.call_args[0][0]
        assert 'Food & Dining\\Coffee Shops\\Starbucks' in call_args
        assert 'parent context' in call_args.lower() or 'hierarchy' in call_args.lower()
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_category_context_in_ai_suggestions(self, mock_call_llm):
        """Test that AI suggestions benefit from category hierarchy context."""
        mock_call_llm.return_value = '''
        {
            "suggestions": [
                {
                    "category_path": "Food & Dining\\\\Coffee",
                    "uuid": "coffee-uuid",
                    "confidence": 0.90,
                    "reasoning": "Coffee purchase, specific coffee shop subcategory may be more appropriate"
                }
            ]
        }
        '''
        
        result = self.client.categorize_transaction(self.sample_transaction, self.enhanced_categories)
        
        # Should find the coffee category with parent context
        assert len(result) == 1
        assert result[0]['category']['parent_path'] == 'Food & Dining'
        assert result[0]['category']['hierarchy_level'] == 2
    
    @patch.object(LMStudioClient, '_call_llm')
    def test_hierarchical_category_matching(self, mock_call_llm):
        """Test that hierarchical category matching works correctly."""
        mock_call_llm.return_value = '''
        {
            "suggestions": [
                {
                    "category_path": "Food & Dining\\\\Coffee Shops\\\\Starbucks",
                    "uuid": "starbucks-uuid",
                    "confidence": 0.95,
                    "reasoning": "Exact match for Starbucks transactions"
                },
                {
                    "category_path": "Food & Dining\\\\Coffee",
                    "uuid": "coffee-uuid",
                    "confidence": 0.85,
                    "reasoning": "General coffee category"
                }
            ]
        }
        '''
        
        result = self.client.categorize_transaction(self.sample_transaction, self.enhanced_categories)
        
        # Should return both suggestions with correct hierarchy info
        assert len(result) == 2
        
        # First suggestion (Starbucks) should be more specific
        starbucks_suggestion = result[0]
        assert starbucks_suggestion['category']['name'] == 'Starbucks'
        assert starbucks_suggestion['category']['hierarchy_level'] == 3
        
        # Second suggestion (Coffee) should be less specific
        coffee_suggestion = result[1]
        assert coffee_suggestion['category']['name'] == 'Coffee'
        assert coffee_suggestion['category']['hierarchy_level'] == 2
    
    def test_format_categories_for_prompt_includes_hierarchy(self):
        """Test that category formatting includes hierarchical information."""
        formatted = self.client._format_categories_for_prompt(self.enhanced_categories)
        
        # Should include full hierarchical paths
        assert 'Food & Dining\\Coffee Shops\\Starbucks' in formatted
        assert 'Food & Dining\\Coffee' in formatted
        assert 'Transportation\\Gas' in formatted
        
        # Should include parent context information
        lines = formatted.split('\n')
        starbucks_line = next(line for line in lines if 'Starbucks' in line)
        assert 'Food & Dining\\Coffee Shops\\Starbucks' in starbucks_line
        assert 'starbucks-uuid' in starbucks_line