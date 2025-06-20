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
                'categories': [
                    {'name': 'Coffee', 'uuid': 'coffee-uuid'},
                    {'name': 'Restaurants', 'uuid': 'restaurant-uuid'}
                ]
            },
            {
                'name': 'Transportation',
                'uuid': 'transport-uuid',
                'categories': []
            }
        ]
        
        self.sample_transactions = [
            {
                'id': 12345,
                'name': 'STARBUCKS',
                'amount': -4.50,
                'currency': 'EUR',
                'date': '2024-01-15',
                'purpose': 'Coffee'
            },
            {
                'id': 12346,
                'name': 'SHELL',
                'amount': -60.00,
                'currency': 'EUR',
                'date': '2024-01-16',
                'purpose': 'Gas'
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
    
    def test_flatten_categories_nested(self):
        result = self.client._flatten_categories(self.sample_categories_plist)
        
        # Only leaf nodes should be included (Coffee, Restaurants, Transportation)
        # Food & Dining should be excluded as it has subcategories
        assert len(result) == 3
        
        # Food & Dining should not be in results as it's a parent category
        food_names = [c['name'] for c in result]
        assert 'Food & Dining' not in food_names
        
        coffee_category = next(c for c in result if c['name'] == 'Coffee')
        assert coffee_category['path'] == 'Food & Dining\\Coffee'
        assert coffee_category['uuid'] == 'coffee-uuid'
        
        restaurant_category = next(c for c in result if c['name'] == 'Restaurants')
        assert restaurant_category['path'] == 'Food & Dining\\Restaurants'
        
        transport_category = next(c for c in result if c['name'] == 'Transportation')
        assert transport_category['path'] == 'Transportation'
    
    @patch.object(MoneyMoneyClient, '_run_applescript')
    def test_get_categories_success(self, mock_run):
        plist_data = plistlib.dumps(self.sample_categories_plist).decode('utf-8')
        mock_run.return_value = plist_data
        
        result = self.client.get_categories()
        
        # Only leaf nodes should be returned (3 instead of 4)
        assert len(result) == 3
        mock_run.assert_called_once_with('tell application "MoneyMoney" to export categories')
    
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