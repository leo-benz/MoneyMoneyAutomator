import pytest
import plistlib
from unittest.mock import Mock, patch, MagicMock
from moneymoney_client import MoneyMoneyClient


class TestMoneyMoneyClient:
    
    def setup_method(self):
        self.client = MoneyMoneyClient()
        self.sample_categories_plist = [
            {
                'name': 'Food & Dining',
                'uuid': 'food-uuid',
                'group': True,
                'indentation': 0
            },
            {
                'name': 'Coffee',
                'uuid': 'coffee-uuid',
                'group': False,
                'indentation': 1
            },
            {
                'name': 'Restaurants',
                'uuid': 'restaurant-uuid',
                'group': False,
                'indentation': 1
            },
            {
                'name': 'Transportation',
                'uuid': 'transport-uuid',
                'group': False,
                'indentation': 0
            }
        ]
        
        self.sample_transactions = [
            {
                'id': 12345,
                'name': 'STARBUCKS',
                'amount': -4.50,
                'currency': 'EUR',
                'date': '2024-01-15',
                'purpose': 'Coffee',
                'category': '',  # Uncategorized
                'booked': True   # Fully booked
            },
            {
                'id': 12346,
                'name': 'SHELL',
                'amount': -60.00,
                'currency': 'EUR',
                'date': '2024-01-16',
                'purpose': 'Gas',
                'category': '',  # Uncategorized
                'booked': True   # Fully booked
            }
        ]
    
    def test_init(self):
        assert self.client.app_name == "MoneyMoney"
    
    @patch('subprocess.run')
    def test_run_applescript_success(self, mock_run):
        mock_result = Mock()
        mock_result.stdout = "test output"
        mock_run.return_value = mock_result
        
        result = self.client._run_applescript('test script')
        
        assert result == "test output"
        mock_run.assert_called_once_with(
            ['osascript', '-e', 'test script'],
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('subprocess.run')
    def test_run_applescript_error(self, mock_run):
        from subprocess import CalledProcessError
        mock_run.side_effect = CalledProcessError(1, 'osascript', stderr='Script error')
        
        with pytest.raises(Exception, match="AppleScript execution failed"):
            self.client._run_applescript('test script')
    
    def test_flatten_categories_simple(self):
        categories = [{'name': 'Test', 'uuid': 'test-uuid'}]
        result = self.client._flatten_categories(categories)
        
        assert len(result) == 1
        assert result[0]['name'] == 'Test'
        assert result[0]['uuid'] == 'test-uuid'
        assert result[0]['path'] == 'Test'
        assert result[0]['full_name'] == 'Test'
    
    def test_process_indentation_hierarchy(self):
        result = self.client._process_indentation_hierarchy(self.sample_categories_plist)
        
        # Only leaf nodes should be included (Coffee, Restaurants, Transportation)
        # Food & Dining should be excluded as it's a group category
        assert len(result) == 3
        
        # Food & Dining should not be in results as it's a parent category
        food_names = [c['name'] for c in result]
        assert 'Food & Dining' not in food_names
        
        coffee_category = next(c for c in result if c['name'] == 'Coffee')
        assert coffee_category['full_name'] == 'Food & Dining > Coffee'
        assert coffee_category['moneymoney_path'] == 'Food & Dining\\Coffee'
        assert coffee_category['uuid'] == 'coffee-uuid'
        
        restaurant_category = next(c for c in result if c['name'] == 'Restaurants')
        assert restaurant_category['full_name'] == 'Food & Dining > Restaurants'
        
        transport_category = next(c for c in result if c['name'] == 'Transportation')
        assert transport_category['full_name'] == 'Transportation'
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_get_categories_success(self, mock_run):
        plist_data = plistlib.dumps(self.sample_categories_plist).decode('utf-8')
        mock_run.return_value = plist_data
        
        result = self.client.get_categories()
        
        # Only leaf nodes should be returned (3: Coffee, Restaurants, Transportation)
        assert len(result) == 3
        mock_run.assert_called_once_with('tell application "MoneyMoney" to export categories')
        
        # Verify the hierarchical structure
        coffee_cat = next(cat for cat in result if cat['name'] == 'Coffee')
        assert coffee_cat['full_name'] == 'Food & Dining > Coffee'
        assert coffee_cat['moneymoney_path'] == 'Food & Dining\\Coffee'
        
        restaurants_cat = next(cat for cat in result if cat['name'] == 'Restaurants')
        assert restaurants_cat['full_name'] == 'Food & Dining > Restaurants'
        
        transport_cat = next(cat for cat in result if cat['name'] == 'Transportation')
        assert transport_cat['full_name'] == 'Transportation'  # Top-level category
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_get_categories_parse_error(self, mock_run):
        mock_run.return_value = "invalid plist data"
        
        result = self.client.get_categories()
        assert result == []
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_get_uncategorized_transactions_success(self, mock_run):
        plist_data = plistlib.dumps(self.sample_transactions).decode('utf-8')
        mock_run.return_value = plist_data
        
        result = self.client.get_uncategorized_transactions('2024-01-01')
        
        assert len(result) == 2
        assert result[0]['name'] == 'STARBUCKS'
        assert result[1]['name'] == 'SHELL'
        
        expected_script = '''tell application "MoneyMoney"
export transactions from category "" from date "2024-01-01" as "plist"
end tell'''
        mock_run.assert_called_once_with(expected_script)
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_get_uncategorized_transactions_with_to_date(self, mock_run):
        plist_data = plistlib.dumps(self.sample_transactions).decode('utf-8')
        mock_run.return_value = plist_data
        
        result = self.client.get_uncategorized_transactions('2024-01-01', '2024-01-31')
        
        expected_script = '''tell application "MoneyMoney"
export transactions from category "" from date "2024-01-01" to date "2024-01-31" as "plist"
end tell'''
        mock_run.assert_called_once_with(expected_script)
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_get_uncategorized_transactions_empty(self, mock_run):
        mock_run.return_value = plistlib.dumps([]).decode('utf-8')
        
        result = self.client.get_uncategorized_transactions('2024-01-01')
        assert result == []
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_get_uncategorized_transactions_parse_error(self, mock_run):
        mock_run.return_value = "invalid plist"
        
        result = self.client.get_uncategorized_transactions('2024-01-01')
        assert result == []
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_set_transaction_category_success(self, mock_run):
        mock_run.return_value = ""
        
        result = self.client.set_transaction_category(12345, "Food & Dining\\Coffee")
        
        assert result is True
        expected_script = '''tell application "MoneyMoney"
    set transaction id 12345 category to "Food & Dining\\Coffee"
end tell'''
        mock_run.assert_called_once_with(expected_script)
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_set_transaction_category_error(self, mock_run):
        mock_run.side_effect = Exception("AppleScript error")
        
        result = self.client.set_transaction_category(12345, "Food & Dining\\Coffee")
        assert result is False
    
    def test_format_transaction_complete(self):
        transaction = {
            'name': 'STARBUCKS',
            'amount': -4.50,
            'currency': 'EUR',
            'bookingDate': '2024-01-15',
            'purpose': 'Coffee purchase',
            'accountUuid': 'test-account-uuid'
        }
        
        # Mock the get_accounts method
        self.client._accounts_cache = {'test-account-uuid': 'Test Account'}
        
        result = self.client.format_transaction(transaction)
        
        # Check for key content rather than exact formatting
        assert 'STARBUCKS' in result
        assert '-4.50 EUR' in result
        assert 'Coffee purchase' in result
        assert 'Test Account' in result
    
    def test_format_transaction_minimal(self):
        transaction = {}
        
        result = self.client.format_transaction(transaction)
        
        # Check for key content rather than exact formatting
        assert 'Unknown' in result  # Name and Account should be Unknown
        assert '0.00 EUR' in result
        assert 'Date:' in result
        assert 'Account:' in result
    
    def test_format_transaction_no_purpose(self):
        transaction = {
            'name': 'STARBUCKS',
            'amount': -4.50,
            'currency': 'USD',
            'bookingDate': '2024-01-15'
        }
        
        result = self.client.format_transaction(transaction)
        
        # Check for key content rather than exact formatting
        assert 'STARBUCKS' in result
        assert '-4.50 USD' in result
        assert 'Purpose:' not in result  # Should not show purpose when not provided


class TestPendingTransactionFiltering:
    """Test filtering of pending transactions."""
    
    def setup_method(self):
        self.client = MoneyMoneyClient()
        
        # Sample transactions with different booking statuses
        self.mixed_transactions = [
            {
                'id': 12345,
                'name': 'BOOKED MERCHANT',
                'amount': -30.00,
                'currency': 'EUR',
                'date': '2024-01-15',
                'purpose': 'Completed purchase',
                'booked': True,
                'bookingDate': '2024-01-15'
            },
            {
                'id': 12346,
                'name': 'PENDING MERCHANT',
                'amount': -25.00,
                'currency': 'EUR',
                'date': '2024-01-15',
                'purpose': 'Pending purchase',
                'booked': False
            },
            {
                'id': 12347,
                'name': 'UNBOOKED TRANSACTION',
                'amount': -50.00,
                'currency': 'EUR',
                'date': '2024-01-16',
                'purpose': 'Unbooked transaction'
            },
            {
                'id': 12348,
                'name': 'FULLY PROCESSED',
                'amount': -40.00,
                'currency': 'EUR',
                'date': '2024-01-16',
                'purpose': 'Processed transaction',
                'booked': True,
                'bookingDate': '2024-01-16'
            }
        ]
    
    @patch('moneymoney_client.Config')
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_exclude_pending_transactions_default(self, mock_applescript, mock_config):
        """Test that pending transactions are excluded by default."""
        mock_config.EXCLUDE_PENDING_TRANSACTIONS = True
        
        # Mock the AppleScript response with mixed transactions
        mock_response_data = {'transactions': self.mixed_transactions}
        mock_applescript.return_value = plistlib.dumps(mock_response_data).decode('utf-8')
        
        result = self.client.get_uncategorized_transactions('2024-01-01', '2024-01-31')
        
        # Should only include booked transactions (ids 12345 and 12348)
        assert len(result) == 2
        result_ids = [t['id'] for t in result]
        assert 12345 in result_ids  # Booked transaction
        assert 12348 in result_ids  # Fully processed transaction
        assert 12346 not in result_ids  # Pending transaction (booked=False)
        assert 12347 not in result_ids  # Unbooked transaction (bookingDate=None)
    
    @patch('moneymoney_client.Config')
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_pending_transaction_identification(self, mock_applescript, mock_config):
        """Test correct identification of pending vs booked transactions."""
        mock_config.EXCLUDE_PENDING_TRANSACTIONS = True
        
        # Test various pending scenarios
        pending_scenarios = [
            {'id': 1, 'booked': False},  # Explicitly not booked
            {'id': 2},  # No booking date or booked flag
            {'id': 3, 'booked': False},  # Explicitly not booked
            {'id': 4},  # Missing both fields (should be treated as pending)
        ]
        
        mock_response_data = {'transactions': pending_scenarios}
        mock_applescript.return_value = plistlib.dumps(mock_response_data).decode('utf-8')
        
        result = self.client.get_uncategorized_transactions('2024-01-01')
        
        # All should be filtered out as pending
        assert len(result) == 0
    
    @patch('moneymoney_client.Config')
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_booked_vs_pending_transaction_filtering(self, mock_applescript, mock_config):
        """Test filtering between booked and pending transactions."""
        mock_config.EXCLUDE_PENDING_TRANSACTIONS = True
        
        # Test various booked scenarios
        booked_scenarios = [
            {'id': 1, 'booked': True, 'bookingDate': '2024-01-15'},  # Fully booked
            {'id': 2, 'booked': True},  # Booked but no date
            {'id': 3, 'bookingDate': '2024-01-15'},  # Has booking date but no booked flag
        ]
        
        mock_response_data = {'transactions': booked_scenarios}
        mock_applescript.return_value = plistlib.dumps(mock_response_data).decode('utf-8')
        
        result = self.client.get_uncategorized_transactions('2024-01-01')
        
        # All should be included as they have indicators of being booked
        assert len(result) == 3
        result_ids = [t['id'] for t in result]
        assert all(id in result_ids for id in [1, 2, 3])
    
    @patch('moneymoney_client.Config')
    @patch.object(MoneyMoneyClient, '_run_applescript')
    @patch('moneymoney_client.logger')
    def test_logging_of_excluded_pending_count(self, mock_logger, mock_applescript, mock_config):
        """Test that excluded pending transaction count is logged."""
        mock_config.EXCLUDE_PENDING_TRANSACTIONS = True
        
        mock_response_data = {'transactions': self.mixed_transactions}
        mock_applescript.return_value = plistlib.dumps(mock_response_data).decode('utf-8')
        
        self.client.get_uncategorized_transactions('2024-01-01', '2024-01-31')
        
        # Check that logging includes pending transaction exclusion info
        # Look for calls that mention pending transactions
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        pending_log_found = any('pending' in call.lower() for call in log_calls)
        assert pending_log_found, f"Expected pending transaction log message. Actual calls: {log_calls}"
    
    @patch('moneymoney_client.Config')
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_empty_result_when_all_pending(self, mock_applescript, mock_config):
        """Test empty result when all transactions are pending."""
        mock_config.EXCLUDE_PENDING_TRANSACTIONS = True
        
        # All transactions are pending
        all_pending = [
            {'id': 1, 'booked': False},
            {'id': 2},  # No booking indicators
            {'id': 3, 'booked': False}
        ]
        
        mock_response_data = {'transactions': all_pending}
        mock_applescript.return_value = plistlib.dumps(mock_response_data).decode('utf-8')
        
        result = self.client.get_uncategorized_transactions('2024-01-01')
        
        assert len(result) == 0
    
    @patch('moneymoney_client.Config')
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_exclude_pending_disabled(self, mock_applescript, mock_config):
        """Test that all transactions are included when exclude pending is disabled."""
        mock_config.EXCLUDE_PENDING_TRANSACTIONS = False
        
        mock_response_data = {'transactions': self.mixed_transactions}
        mock_applescript.return_value = plistlib.dumps(mock_response_data).decode('utf-8')
        
        result = self.client.get_uncategorized_transactions('2024-01-01', '2024-01-31')
        
        # All transactions should be included when filtering is disabled
        assert len(result) == 4
        result_ids = [t['id'] for t in result]
        assert all(tid in result_ids for tid in [12345, 12346, 12347, 12348])
    
    @patch('moneymoney_client.Config')
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_categorized_transactions_still_filtered(self, mock_applescript, mock_config):
        """Test that categorized transactions are still filtered by uncategorized logic."""
        mock_config.EXCLUDE_PENDING_TRANSACTIONS = True
        
        # Mix of categorized and uncategorized transactions, some pending
        mixed_categorized = [
            {'id': 1, 'booked': True, 'category': ''},  # Uncategorized, booked
            {'id': 2, 'booked': False, 'category': ''},  # Uncategorized, pending
            {'id': 3, 'booked': True, 'category': 'Food & Dining\\Coffee'},  # Categorized, booked
            {'id': 4, 'booked': False, 'category': 'Shopping\\Groceries'}  # Categorized, pending
        ]
        
        mock_response_data = {'transactions': mixed_categorized}
        mock_applescript.return_value = plistlib.dumps(mock_response_data).decode('utf-8')
        
        result = self.client.get_uncategorized_transactions('2024-01-01')
        
        # Should only return uncategorized, booked transactions (id 1)
        assert len(result) == 1
        assert result[0]['id'] == 1


class TestHierarchicalCategoryStructure:
    """Test enhanced category flattening with parent context."""
    
    def setup_method(self):
        self.client = MoneyMoneyClient()
        
        # Complex hierarchical category structure
        self.hierarchical_categories = [
            {
                'name': 'Food & Dining',
                'uuid': 'food-uuid',
                'categories': [
                    {
                        'name': 'Coffee Shops',
                        'uuid': 'coffee-shops-uuid',
                        'categories': [
                            {'name': 'Starbucks', 'uuid': 'starbucks-uuid'},
                            {'name': 'Local Coffee', 'uuid': 'local-coffee-uuid'}
                        ]
                    },
                    {'name': 'Restaurants', 'uuid': 'restaurants-uuid'},
                    {'name': 'Fast Food', 'uuid': 'fast-food-uuid'}
                ]
            },
            {
                'name': 'Transportation',
                'uuid': 'transport-uuid',
                'categories': [
                    {'name': 'Gas', 'uuid': 'gas-uuid'},
                    {'name': 'Public Transit', 'uuid': 'transit-uuid'}
                ]
            },
            {
                'name': 'Bills',
                'uuid': 'bills-uuid',
                'categories': []  # No subcategories - should be included as leaf
            }
        ]
    
    def test_category_flattening_with_parent_context(self):
        """Test that flattened categories include parent context information."""
        result = self.client._flatten_categories_with_context(self.hierarchical_categories)
        
        # Should have 6 leaf categories: Starbucks, Local Coffee, Restaurants, Fast Food, Gas, Public Transit, Bills
        assert len(result) == 7
        
        # Check Starbucks has full parent context
        starbucks = next(c for c in result if c['name'] == 'Starbucks')
        assert starbucks['full_name'] == 'Food & Dining > Coffee Shops > Starbucks'
        assert starbucks['parent_path'] == 'Food & Dining > Coffee Shops'
        assert starbucks['hierarchy_level'] == 3
        
        # Check Bills (top-level with no subcategories)
        bills = next(c for c in result if c['name'] == 'Bills')
        assert bills['full_name'] == 'Bills'
        assert bills['parent_path'] == ''
        assert bills['hierarchy_level'] == 1
        
        # Check Gas (second level)
        gas = next(c for c in result if c['name'] == 'Gas')
        assert gas['full_name'] == 'Transportation > Gas'
        assert gas['parent_path'] == 'Transportation'
        assert gas['hierarchy_level'] == 2
    
    def test_hierarchical_category_structure_preservation(self):
        """Test that parent-child relationships are preserved."""
        result = self.client._flatten_categories_with_context(self.hierarchical_categories)
        
        # All categories under Food & Dining should have that as part of their parent path
        food_categories = [c for c in result if 'Food & Dining' in c['parent_path'] or c['full_name'] == 'Food & Dining']
        
        # Should include: Starbucks, Local Coffee, Restaurants, Fast Food (not Food & Dining itself as it has children)
        assert len(food_categories) == 4
        
        for cat in food_categories:
            if cat['name'] in ['Starbucks', 'Local Coffee']:
                assert cat['parent_path'] == 'Food & Dining > Coffee Shops'
            elif cat['name'] in ['Restaurants', 'Fast Food']:
                assert cat['parent_path'] == 'Food & Dining'
    
    def test_parent_path_inclusion_in_category_objects(self):
        """Test that parent path is correctly included in category objects."""
        result = self.client._flatten_categories_with_context(self.hierarchical_categories)
        
        for category in result:
            # All categories should have parent_path and hierarchy_level fields
            assert 'parent_path' in category
            assert 'hierarchy_level' in category
            assert isinstance(category['hierarchy_level'], int)
            assert category['hierarchy_level'] >= 1
            
            # Parent path should be empty only for top-level categories with no subcategories
            if category['hierarchy_level'] == 1:
                assert category['parent_path'] == ''
            else:
                assert category['parent_path'] != ''
    
    def test_category_depth_calculation(self):
        """Test that hierarchy levels are correctly calculated."""
        result = self.client._flatten_categories_with_context(self.hierarchical_categories)
        
        # Bills should be level 1 (top-level, no children)
        bills = next(c for c in result if c['name'] == 'Bills')
        assert bills['hierarchy_level'] == 1
        
        # Gas should be level 2 (Transportation > Gas)
        gas = next(c for c in result if c['name'] == 'Gas')
        assert gas['hierarchy_level'] == 2
        
        # Starbucks should be level 3 (Food & Dining > Coffee Shops > Starbucks)
        starbucks = next(c for c in result if c['name'] == 'Starbucks')
        assert starbucks['hierarchy_level'] == 3
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_get_categories_uses_indentation_processing(self, mock_applescript):
        """Test that get_categories uses the indentation hierarchy processing method."""
        mock_applescript.return_value = plistlib.dumps(self.hierarchical_categories).decode('utf-8')
        
        with patch.object(self.client, '_process_indentation_hierarchy') as mock_process:
            mock_process.return_value = [
                {
                    'uuid': 'test-uuid',
                    'name': 'Test Category',
                    'full_name': 'Parent > Test Category',
                    'moneymoney_path': 'Parent\\Test Category',
                    'parent_path': 'Parent',
                    'hierarchy_level': 2
                }
            ]
            
            result = self.client.get_categories()
            
            # Should call indentation processing method
            mock_process.assert_called_once_with(self.hierarchical_categories)
            assert len(result) == 1
            assert result[0]['parent_path'] == 'Parent'
    
    def test_empty_categories_handling(self):
        """Test handling of empty category lists."""
        result = self.client._flatten_categories_with_context([])
        assert result == []
    
    def test_single_level_categories(self):
        """Test handling of categories with no hierarchy."""
        flat_categories = [
            {'name': 'Category1', 'uuid': 'uuid1'},
            {'name': 'Category2', 'uuid': 'uuid2'}
        ]
        
        result = self.client._flatten_categories_with_context(flat_categories)
        
        assert len(result) == 2
        for cat in result:
            assert cat['hierarchy_level'] == 1
            assert cat['parent_path'] == ''
            assert cat['full_name'] == cat['name']