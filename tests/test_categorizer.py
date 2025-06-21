import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
import sys
import tempfile
import os
from categorizer import TransactionCategorizer, main


class TestTransactionCategorizer:
    
    def setup_method(self):
        self.sample_categories = [
            {'uuid': '1', 'full_name': 'Food & Dining\\Coffee'},
            {'uuid': '2', 'full_name': 'Transportation\\Gas'}
        ]
        
        self.sample_transactions = [
            {
                'id': 12345,
                'name': 'STARBUCKS',
                'amount': -4.50,
                'currency': 'EUR',
                'date': '2024-01-15'
            },
            {
                'id': 12346,
                'name': 'SHELL',
                'amount': -60.00,
                'currency': 'EUR',
                'date': '2024-01-16'
            }
        ]
        
        self.sample_suggestions = [
            {
                'category': {'uuid': '1', 'full_name': 'Food & Dining\\Coffee'},
                'confidence': 0.9,
                'reasoning': 'Coffee shop transaction'
            }
        ]
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    def test_init_default_values(self, mock_llm, mock_money):
        categorizer = TransactionCategorizer('2024-01-01')
        
        assert categorizer.from_date == '2024-01-01'
        assert categorizer.to_date is None
        assert categorizer.dry_run is False
        assert categorizer.stats['processed'] == 0
        assert categorizer.stats['categorized'] == 0
        assert categorizer.stats['skipped'] == 0
        assert categorizer.stats['errors'] == 0
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    def test_init_with_all_params(self, mock_llm, mock_money):
        categorizer = TransactionCategorizer('2024-01-01', '2024-01-31', True)
        
        assert categorizer.from_date == '2024-01-01'
        assert categorizer.to_date == '2024-01-31'
        assert categorizer.dry_run is True
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('builtins.input', return_value='')
    @patch('sys.stdout', new_callable=StringIO)
    def test_initialize_success(self, mock_stdout, mock_input, mock_llm, mock_money):
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm.return_value = mock_llm_instance
        
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = self.sample_categories
        mock_money.return_value = mock_money_instance
        
        categorizer = TransactionCategorizer('2024-01-01')
        result = categorizer._initialize()
        
        assert result is True
        assert len(categorizer.categories) == 2
        assert categorizer.category_selector is not None
        
        output = mock_stdout.getvalue()
        assert 'Initializing...' in output
        assert 'Loaded 2 categories' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_initialize_llm_connection_failure(self, mock_stdout, mock_llm, mock_money):
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = False
        mock_llm.return_value = mock_llm_instance
        
        categorizer = TransactionCategorizer('2024-01-01')
        result = categorizer._initialize()
        
        assert result is False
        output = mock_stdout.getvalue()
        assert 'Cannot connect to LM Studio' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_initialize_no_categories(self, mock_stdout, mock_llm, mock_money):
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm.return_value = mock_llm_instance
        
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = []
        mock_money.return_value = mock_money_instance
        
        categorizer = TransactionCategorizer('2024-01-01')
        result = categorizer._initialize()
        
        assert result is False
        output = mock_stdout.getvalue()
        assert 'No categories found in MoneyMoney' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    def test_load_transactions_success(self, mock_llm, mock_money):
        mock_money_instance = Mock()
        mock_money_instance.get_uncategorized_transactions.return_value = self.sample_transactions
        mock_money.return_value = mock_money_instance
        
        categorizer = TransactionCategorizer('2024-01-01', '2024-01-31')
        result = categorizer._load_transactions()
        
        assert len(result) == 2
        mock_money_instance.get_uncategorized_transactions.assert_called_once_with('2024-01-01', '2024-01-31')
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_load_transactions_error(self, mock_stdout, mock_llm, mock_money):
        mock_money_instance = Mock()
        mock_money_instance.get_uncategorized_transactions.side_effect = Exception("Database error")
        mock_money.return_value = mock_money_instance
        
        categorizer = TransactionCategorizer('2024-01-01')
        result = categorizer._load_transactions()
        
        assert result == []
        output = mock_stdout.getvalue()
        assert 'Error loading transactions: Database error' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CategorySelector')
    def test_process_single_transaction_success(self, mock_selector_class, mock_llm, mock_money):
        mock_llm_instance = Mock()
        mock_llm_instance.categorize_transaction.return_value = self.sample_suggestions
        mock_llm.return_value = mock_llm_instance
        
        mock_money_instance = Mock()
        mock_money_instance.set_transaction_category.return_value = True
        mock_money.return_value = mock_money_instance
        
        mock_selector = Mock()
        mock_selector.get_user_choice.return_value = {
            'action': 'categorize',
            'category': {'uuid': '1', 'full_name': 'Food & Dining > Coffee', 'moneymoney_path': 'Food & Dining\\Coffee'}
        }
        mock_selector_class.return_value = mock_selector
        
        categorizer = TransactionCategorizer('2024-01-01')
        categorizer.categories = self.sample_categories
        categorizer.category_selector = mock_selector
        
        result = categorizer._process_single_transaction(self.sample_transactions[0])
        
        assert result is True
        mock_llm_instance.categorize_transaction.assert_called_once()
        mock_selector.display_suggestions.assert_called_once_with(self.sample_suggestions)
        mock_money_instance.set_transaction_category.assert_called_once_with(12345, 'Food & Dining\\Coffee')
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CategorySelector')
    def test_process_single_transaction_skip(self, mock_selector_class, mock_llm, mock_money):
        mock_llm_instance = Mock()
        mock_llm_instance.categorize_transaction.return_value = self.sample_suggestions
        mock_llm.return_value = mock_llm_instance
        
        mock_selector = Mock()
        mock_selector.get_user_choice.return_value = {'action': 'skip'}
        mock_selector_class.return_value = mock_selector
        
        categorizer = TransactionCategorizer('2024-01-01')
        categorizer.categories = self.sample_categories
        categorizer.category_selector = mock_selector
        
        result = categorizer._process_single_transaction(self.sample_transactions[0])
        
        assert result is False
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_apply_categorization_success(self, mock_stdout, mock_llm, mock_money):
        mock_money_instance = Mock()
        mock_money_instance.set_transaction_category.return_value = True
        mock_money.return_value = mock_money_instance
        
        categorizer = TransactionCategorizer('2024-01-01')
        category = {'full_name': 'Food & Dining > Coffee', 'moneymoney_path': 'Food & Dining\\Coffee'}
        
        result = categorizer._apply_categorization(self.sample_transactions[0], category)
        
        assert result is True
        output = mock_stdout.getvalue()
        assert 'Applying category: Food & Dining > Coffee' in output
        assert '✅ Category applied successfully' in output
        mock_money_instance.set_transaction_category.assert_called_once_with(12345, 'Food & Dining\\Coffee')
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_apply_categorization_dry_run(self, mock_stdout, mock_llm, mock_money):
        categorizer = TransactionCategorizer('2024-01-01', dry_run=True)
        category = {'full_name': 'Food & Dining\\Coffee'}
        
        result = categorizer._apply_categorization(self.sample_transactions[0], category)
        
        assert result is True
        output = mock_stdout.getvalue()
        assert 'DRY RUN: Would categorize transaction' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_apply_categorization_no_transaction_id(self, mock_stdout, mock_llm, mock_money):
        categorizer = TransactionCategorizer('2024-01-01')
        category = {'full_name': 'Food & Dining\\Coffee'}
        transaction_without_id = {'name': 'Test'}
        
        result = categorizer._apply_categorization(transaction_without_id, category)
        
        assert result is False
        output = mock_stdout.getvalue()
        assert 'Transaction ID not found' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_apply_categorization_failure(self, mock_stdout, mock_llm, mock_money):
        mock_money_instance = Mock()
        mock_money_instance.set_transaction_category.return_value = False
        mock_money.return_value = mock_money_instance
        
        categorizer = TransactionCategorizer('2024-01-01')
        category = {'full_name': 'Food & Dining\\Coffee'}
        
        result = categorizer._apply_categorization(self.sample_transactions[0], category)
        
        assert result is False
        output = mock_stdout.getvalue()
        assert '❌ Failed to apply category' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_print_summary(self, mock_stdout, mock_llm, mock_money):
        categorizer = TransactionCategorizer('2024-01-01')
        categorizer.stats = {
            'processed': 10,
            'categorized': 8,
            'skipped': 1,
            'errors': 1
        }
        
        categorizer._print_summary()
        
        output = mock_stdout.getvalue()
        assert 'SUMMARY' in output
        assert 'Transactions processed:' in output and '10' in output
        assert 'Successfully categorized:' in output and '8' in output
        assert 'Skipped:' in output and '1' in output
        assert 'Errors:' in output and '1' in output
        assert 'Success rate:' in output and '80.0%' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('sys.stdout', new_callable=StringIO)
    def test_print_summary_no_transactions(self, mock_stdout, mock_llm, mock_money):
        categorizer = TransactionCategorizer('2024-01-01')
        
        categorizer._print_summary()
        
        output = mock_stdout.getvalue()
        assert 'Transactions processed:' in output and '0' in output
        assert 'Success rate:' not in output


class TestMain:
    
    @patch('categorizer.TransactionCategorizer')
    @patch('sys.argv', ['categorizer.py'])
    def test_main_default_args(self, mock_categorizer_class):
        mock_categorizer = Mock()
        mock_categorizer_class.return_value = mock_categorizer
        
        main()
        
        mock_categorizer_class.assert_called_once()
        call_args = mock_categorizer_class.call_args[1]
        assert 'from_date' in call_args
        assert call_args['to_date'] is None
        assert call_args['dry_run'] is False
        mock_categorizer.run.assert_called_once()
    
    @patch('categorizer.TransactionCategorizer')
    @patch('sys.argv', ['categorizer.py', '--from-date', '2024-01-01', '--to-date', '2024-01-31', '--dry-run'])
    def test_main_with_all_args(self, mock_categorizer_class):
        mock_categorizer = Mock()
        mock_categorizer_class.return_value = mock_categorizer
        
        main()
        
        call_args = mock_categorizer_class.call_args[1]
        assert call_args['from_date'] == '2024-01-01'
        assert call_args['to_date'] == '2024-01-31'
        assert call_args['dry_run'] is True
    
    @patch('categorizer.TransactionCategorizer')
    @patch('sys.argv', ['categorizer.py'])
    @patch('sys.exit')
    def test_main_keyboard_interrupt(self, mock_exit, mock_categorizer_class):
        mock_categorizer = Mock()
        mock_categorizer.run.side_effect = KeyboardInterrupt()
        mock_categorizer_class.return_value = mock_categorizer
        
        with patch('builtins.print') as mock_print:
            main()
        
        mock_print.assert_called_with("\nOperation cancelled by user.")
        mock_exit.assert_called_with(1)
    
    @patch('categorizer.TransactionCategorizer')
    @patch('sys.argv', ['categorizer.py'])
    @patch('sys.exit')
    def test_main_general_exception(self, mock_exit, mock_categorizer_class):
        mock_categorizer = Mock()
        mock_categorizer.run.side_effect = Exception("Test error")
        mock_categorizer_class.return_value = mock_categorizer
        
        with patch('builtins.print') as mock_print:
            main()
        
        mock_print.assert_called_with("Error: Test error")
        mock_exit.assert_called_with(1)


class TestCombinedModeWorkflow:
    """Test the combined pre-run + apply mode functionality."""
    
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cache_file = os.path.join(self.temp_dir, 'test_cache.json')
        
        self.sample_transactions = [
            {
                'id': 12345,
                'name': 'STARBUCKS',
                'amount': -4.50,
                'currency': 'EUR',
                'date': '2024-01-15'
            },
            {
                'id': 12346,
                'name': 'SHELL',
                'amount': -60.00,
                'currency': 'EUR',
                'date': '2024-01-16'
            }
        ]
        
        self.sample_suggestions = [
            {
                'category': {'uuid': '1', 'full_name': 'Food & Dining\\Coffee'},
                'confidence': 0.9,
                'reasoning': 'Coffee shop transaction'
            }
        ]
    
    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CategorySelector')
    @patch('categorizer.CacheManager')
    @patch('sys.stdout', new_callable=StringIO)
    def test_combined_mode_default_behavior(self, mock_stdout, mock_cache_manager, mock_selector, mock_llm, mock_money):
        """Test that combined mode is the default behavior without flags."""
        # Setup mocks
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = [{'uuid': '1', 'full_name': 'Food\\Coffee'}]
        mock_money_instance.get_uncategorized_transactions.return_value = self.sample_transactions
        mock_money.return_value = mock_money_instance
        
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm_instance.categorize_transaction.return_value = self.sample_suggestions
        mock_llm.return_value = mock_llm_instance
        
        mock_cache_instance = Mock()
        mock_cache_manager.return_value = mock_cache_instance
        
        mock_selector_instance = Mock()
        mock_selector_instance.get_user_choice.return_value = {'action': 'skip'}
        mock_selector.return_value = mock_selector_instance
        
        # Test combined mode (default)
        categorizer = TransactionCategorizer('2024-01-01', combined_mode=True)
        
        with patch.object(categorizer, '_run_combined_mode') as mock_combined:
            categorizer.run()
            mock_combined.assert_called_once()
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CacheManager')
    @patch('sys.stdout', new_callable=StringIO)
    def test_pre_run_only_mode(self, mock_stdout, mock_cache_manager, mock_llm, mock_money):
        """Test pre-run only mode generates and caches suggestions."""
        # Setup mocks
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = [{'uuid': '1', 'full_name': 'Food\\Coffee'}]
        mock_money_instance.get_uncategorized_transactions.return_value = self.sample_transactions
        mock_money.return_value = mock_money_instance
        
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm_instance.categorize_transaction.return_value = self.sample_suggestions
        mock_llm.return_value = mock_llm_instance
        
        mock_cache_instance = Mock()
        mock_cache_manager.return_value = mock_cache_instance
        
        # Test pre-run only mode
        categorizer = TransactionCategorizer('2024-01-01', pre_run_only=True)
        
        with patch.object(categorizer, '_run_pre_run_only') as mock_pre_run:
            categorizer.run()
            mock_pre_run.assert_called_once()
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CategorySelector')
    @patch('categorizer.CacheManager')
    @patch('sys.stdout', new_callable=StringIO)
    def test_apply_only_mode_with_cache(self, mock_stdout, mock_cache_manager, mock_selector, mock_llm, mock_money):
        """Test apply-only mode uses cached suggestions."""
        # Setup mocks
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = [{'uuid': '1', 'full_name': 'Food\\Coffee'}]
        mock_money_instance.get_uncategorized_transactions.return_value = self.sample_transactions
        mock_money.return_value = mock_money_instance
        
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm.return_value = mock_llm_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get_suggestions.return_value = self.sample_suggestions
        mock_cache_instance.get_cached_transaction_ids.return_value = ['12345', '12346']
        mock_cache_manager.return_value = mock_cache_instance
        
        mock_selector_instance = Mock()
        mock_selector_instance.get_user_choice.return_value = {'action': 'skip'}
        mock_selector.return_value = mock_selector_instance
        
        # Test apply-only mode
        categorizer = TransactionCategorizer('2024-01-01', apply_only=True)
        
        with patch.object(categorizer, '_run_apply_only') as mock_apply:
            categorizer.run()
            mock_apply.assert_called_once()
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CacheManager')
    @patch('sys.stdout', new_callable=StringIO)
    def test_apply_only_mode_without_cache(self, mock_stdout, mock_cache_manager, mock_llm, mock_money):
        """Test apply-only mode fails gracefully without cache."""
        # Setup mocks
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = [{'uuid': '1', 'full_name': 'Food\\Coffee'}]
        mock_money_instance.get_uncategorized_transactions.return_value = self.sample_transactions
        mock_money.return_value = mock_money_instance
        
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm.return_value = mock_llm_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get_cached_transaction_ids.return_value = []
        mock_cache_manager.return_value = mock_cache_instance
        
        # Test apply-only mode without cache
        categorizer = TransactionCategorizer('2024-01-01', apply_only=True)
        categorizer.run()
        
        output = mock_stdout.getvalue()
        assert 'No cached suggestions found' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CacheManager')
    @patch('sys.stdout', new_callable=StringIO)
    def test_progress_display_during_pre_run(self, mock_stdout, mock_cache_manager, mock_llm, mock_money):
        """Test that progress is displayed during pre-run phase."""
        # Setup mocks
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = [{'uuid': '1', 'full_name': 'Food\\Coffee'}]
        mock_money_instance.get_uncategorized_transactions.return_value = self.sample_transactions
        mock_money.return_value = mock_money_instance
        
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm_instance.categorize_transaction.return_value = self.sample_suggestions
        mock_llm.return_value = mock_llm_instance
        
        mock_cache_instance = Mock()
        mock_cache_manager.return_value = mock_cache_instance
        
        # Test progress display
        categorizer = TransactionCategorizer('2024-01-01', pre_run_only=True)
        categorizer._initialize()
        categorizer._run_pre_run_only()
        
        output = mock_stdout.getvalue()
        assert 'Processing transaction' in output or 'Pre-processing' in output
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CategorySelector')
    @patch('categorizer.CacheManager')
    def test_cache_cleanup_on_transaction_completion(self, mock_cache_manager, mock_selector, mock_llm, mock_money):
        """Test that cache entries are cleaned up after transaction processing."""
        # Setup mocks
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = [{'uuid': '1', 'full_name': 'Food\\Coffee'}]
        mock_money_instance.set_transaction_category.return_value = True
        mock_money.return_value = mock_money_instance
        
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm.return_value = mock_llm_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get_suggestions.return_value = self.sample_suggestions
        mock_cache_manager.return_value = mock_cache_instance
        
        mock_selector_instance = Mock()
        mock_selector_instance.get_user_choice.return_value = {
            'action': 'categorize',
            'category': {'uuid': '1', 'full_name': 'Food\\Coffee'}
        }
        mock_selector.return_value = mock_selector_instance
        
        # Test cache cleanup using the cached transaction method
        categorizer = TransactionCategorizer('2024-01-01')
        categorizer.cache_manager = mock_cache_instance
        categorizer.category_selector = mock_selector_instance
        
        # Simulate processing a transaction with cache
        success = categorizer._process_single_transaction_cached(self.sample_transactions[0])
        
        # Verify cache cleanup was called
        assert success is True
        mock_cache_instance.remove_suggestions.assert_called_with(12345)


class TestRuleProposalWorkflow:
    """Test AI rule proposal functionality."""
    
    def setup_method(self):
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
        
        self.sample_rule = {
            'rule': 'name:"STARBUCKS"',
            'explanation': 'Matches all Starbucks transactions for coffee categorization',
            'confidence': 0.90
        }
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CategorySelector')
    @patch('categorizer.CacheManager')
    @patch('sys.stdout', new_callable=StringIO)
    def test_rule_proposal_after_categorization(self, mock_stdout, mock_cache_manager, mock_selector, mock_llm, mock_money):
        """Test that rule proposal is offered after successful categorization."""
        # Setup mocks
        mock_money_instance = Mock()
        mock_money_instance.get_categories.return_value = [self.sample_category]
        mock_money_instance.set_transaction_category.return_value = True
        mock_money.return_value = mock_money_instance
        
        mock_llm_instance = Mock()
        mock_llm_instance.test_connection.return_value = True
        mock_llm_instance.generate_categorization_rule.return_value = self.sample_rule
        mock_llm.return_value = mock_llm_instance
        
        mock_cache_instance = Mock()
        mock_cache_instance.get_suggestions.return_value = []
        mock_cache_manager.return_value = mock_cache_instance
        
        mock_selector_instance = Mock()
        mock_selector_instance.get_user_choice.return_value = {
            'action': 'categorize',
            'category': self.sample_category
        }
        mock_selector_instance.offer_rule_generation.return_value = True
        mock_selector.return_value = mock_selector_instance
        
        # Test rule proposal workflow
        categorizer = TransactionCategorizer('2024-01-01')
        categorizer.cache_manager = mock_cache_instance
        categorizer.category_selector = mock_selector_instance
        categorizer.llm_client = mock_llm_instance
        
        # Process transaction with rule proposal
        with patch.object(categorizer, '_propose_rule_generation') as mock_propose:
            success = categorizer._process_single_transaction_cached(self.sample_transaction)
            
            assert success is True
            mock_propose.assert_called_once()
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CategorySelector')
    @patch('subprocess.run')
    def test_rule_proposal_user_acceptance(self, mock_subprocess, mock_selector, mock_llm, mock_money):
        """Test user accepting rule proposal and copying to clipboard."""
        # Setup mocks
        mock_subprocess.return_value.returncode = 0  # pbcopy success
        
        mock_llm_instance = Mock()
        mock_llm_instance.generate_categorization_rule.return_value = self.sample_rule
        mock_llm.return_value = mock_llm_instance
        
        mock_selector_instance = Mock()
        mock_selector_instance.offer_rule_generation.return_value = True
        mock_selector_instance.display_rule_proposal.return_value = 'copy'
        mock_selector.return_value = mock_selector_instance
        
        # Test rule proposal acceptance
        categorizer = TransactionCategorizer('2024-01-01')
        categorizer.llm_client = mock_llm_instance
        categorizer.category_selector = mock_selector_instance
        
        categorizer._propose_rule_generation(self.sample_transaction, self.sample_category)
        
        mock_llm_instance.generate_categorization_rule.assert_called_once()
        mock_selector_instance.display_rule_proposal.assert_called_once()
        # Note: clipboard copy is handled by the category selector, not the categorizer
    
    @patch('categorizer.MoneyMoneyClient')
    @patch('categorizer.LMStudioClient')
    @patch('categorizer.CategorySelector')
    def test_rule_proposal_user_rejection(self, mock_selector, mock_llm, mock_money):
        """Test user rejecting rule proposal."""
        mock_llm_instance = Mock()
        mock_llm.return_value = mock_llm_instance
        
        mock_selector_instance = Mock()
        mock_selector_instance.offer_rule_generation.return_value = False
        mock_selector.return_value = mock_selector_instance
        
        # Test rule proposal rejection
        categorizer = TransactionCategorizer('2024-01-01')
        categorizer.llm_client = mock_llm_instance
        categorizer.category_selector = mock_selector_instance
        
        categorizer._propose_rule_generation(self.sample_transaction, self.sample_category)
        
        # Should not generate rule if user rejects
        mock_llm_instance.generate_categorization_rule.assert_not_called()
    
    @patch('subprocess.run')
    def test_clipboard_copy_functionality(self, mock_subprocess):
        """Test clipboard copy functionality."""
        mock_subprocess.return_value.returncode = 0
        
        categorizer = TransactionCategorizer('2024-01-01')
        test_rule = 'name:"STARBUCKS"'
        
        success = categorizer._copy_to_clipboard(test_rule)
        
        assert success is True
        mock_subprocess.assert_called_once()
        call_args = mock_subprocess.call_args
        assert 'pbcopy' in call_args[0][0]
        assert test_rule.encode() == call_args[1]['input']
    
    @patch('subprocess.run')
    def test_clipboard_copy_failure(self, mock_subprocess):
        """Test clipboard copy failure handling."""
        mock_subprocess.side_effect = Exception("pbcopy failed")
        
        categorizer = TransactionCategorizer('2024-01-01')
        test_rule = 'name:"STARBUCKS"'
        
        success = categorizer._copy_to_clipboard(test_rule)
        
        assert success is False