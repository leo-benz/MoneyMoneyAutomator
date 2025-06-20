import pytest
from unittest.mock import Mock, patch, MagicMock
from io import StringIO
from category_selector import CategorySelector


class TestCategorySelector:
    
    def setup_method(self):
        self.sample_categories = [
            {'uuid': '1', 'name': 'Coffee', 'full_name': 'Food & Dining\\Coffee'},
            {'uuid': '2', 'name': 'Gas', 'full_name': 'Transportation\\Gas'},
            {'uuid': '3', 'name': 'Groceries', 'full_name': 'Shopping\\Groceries'},
            {'uuid': '4', 'name': 'Restaurants', 'full_name': 'Food & Dining\\Restaurants'},
            {'uuid': '5', 'name': 'Utilities', 'full_name': 'Bills\\Utilities'}
        ]
        self.selector = CategorySelector(self.sample_categories)
        
        self.sample_suggestions = [
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
    
    def test_init(self):
        assert len(self.selector.categories) == 5
        assert len(self.selector.sorted_categories) == 5
        assert self.selector.sorted_categories[0]['full_name'] == 'Bills\\Utilities'
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_suggestions(self, mock_stdout):
        self.selector.display_suggestions(self.sample_suggestions)
        
        output = mock_stdout.getvalue()
        assert 'AI Category Suggestions:' in output
        assert 'Food & Dining\\Coffee' in output
        assert 'Transportation\\Gas' in output
        assert '90%' in output
        assert '70%' in output
        assert 'Transaction at coffee shop' in output
        assert 'Gas station transaction' in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_suggestions_empty(self, mock_stdout):
        self.selector.display_suggestions([])
        
        output = mock_stdout.getvalue()
        assert 'No LLM suggestions available.' in output
    
    @patch('builtins.input', return_value='1')
    def test_get_user_choice_accept_suggestion(self, mock_input):
        result = self.selector.get_user_choice(self.sample_suggestions)
        
        assert result['action'] == 'categorize'
        assert result['category']['uuid'] == '1'
    
    @patch('builtins.input', return_value='2')
    def test_get_user_choice_accept_second_suggestion(self, mock_input):
        result = self.selector.get_user_choice(self.sample_suggestions)
        
        assert result['action'] == 'categorize'
        assert result['category']['uuid'] == '2'
    
    @patch('builtins.input', return_value='3')
    @patch('sys.stdout', new_callable=StringIO)
    def test_get_user_choice_invalid_selection(self, mock_stdout, mock_input):
        mock_input.side_effect = ['3', 'n']
        
        result = self.selector.get_user_choice(self.sample_suggestions)
        
        output = mock_stdout.getvalue()
        assert 'Invalid selection' in output
        assert result['action'] == 'skip'
    
    @patch('builtins.input', return_value='n')
    def test_get_user_choice_skip(self, mock_input):
        result = self.selector.get_user_choice(self.sample_suggestions)
        assert result['action'] == 'skip'
    
    @patch('builtins.input', return_value='q')
    def test_get_user_choice_quit(self, mock_input):
        result = self.selector.get_user_choice(self.sample_suggestions)
        assert result is None
    
    @patch('builtins.input')
    @patch.object(CategorySelector, '_search_categories')
    def test_get_user_choice_search(self, mock_search, mock_input):
        mock_input.return_value = 's'
        mock_search.return_value = {'action': 'categorize', 'category': {'uuid': '1'}}
        
        result = self.selector.get_user_choice(self.sample_suggestions)
        
        assert result['action'] == 'categorize'
        mock_search.assert_called_once()
    
    @patch('builtins.input', side_effect=KeyboardInterrupt())
    def test_get_user_choice_keyboard_interrupt(self, mock_input):
        result = self.selector.get_user_choice(self.sample_suggestions)
        assert result is None
    
    def test_find_matching_categories_exact_match(self):
        matches = self.selector._find_matching_categories('Coffee')
        
        assert len(matches) >= 1
        assert any(cat['name'] == 'Coffee' for cat in matches)
    
    def test_find_matching_categories_partial_match(self):
        matches = self.selector._find_matching_categories('food')
        
        assert len(matches) >= 2
        food_matches = [cat for cat in matches if 'Food' in cat['full_name']]
        assert len(food_matches) >= 2
    
    def test_find_matching_categories_case_insensitive(self):
        matches = self.selector._find_matching_categories('COFFEE')
        
        assert len(matches) >= 1
        assert any(cat['name'] == 'Coffee' for cat in matches)
    
    def test_find_matching_categories_no_match(self):
        matches = self.selector._find_matching_categories('xyz123')
        assert len(matches) == 0
    
    def test_find_matching_categories_max_results(self):
        with patch('config.Config.MAX_SEARCH_RESULTS', 2):
            matches = self.selector._find_matching_categories('a')
            assert len(matches) <= 2
    
    @patch('builtins.input', return_value='1')
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_search_results(self, mock_stdout, mock_input):
        matches = [self.sample_categories[0], self.sample_categories[1]]
        
        result = self.selector._display_search_results(matches)
        
        output = mock_stdout.getvalue()
        assert 'Found 2 matching categories:' in output
        assert 'Food & Dining\\Coffee' in output
        assert 'Transportation\\Gas' in output
        
        assert result['action'] == 'categorize'
        assert result['category']['uuid'] == '1'
    
    @patch('builtins.input', return_value='b')
    def test_display_search_results_back(self, mock_input):
        matches = [self.sample_categories[0]]
        result = self.selector._display_search_results(matches)
        assert result is None
    
    @patch('builtins.input', return_value='r')
    def test_display_search_results_return(self, mock_input):
        matches = [self.sample_categories[0]]
        result = self.selector._display_search_results(matches)
        assert result['action'] == 'back'
    
    @patch('builtins.input', return_value='99')
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_search_results_invalid_number(self, mock_stdout, mock_input):
        mock_input.side_effect = ['99', 'b']
        matches = [self.sample_categories[0]]
        
        result = self.selector._display_search_results(matches)
        
        output = mock_stdout.getvalue()
        assert 'Invalid selection' in output
        assert result is None
    
    @patch('builtins.input')
    @patch.object(CategorySelector, '_find_matching_categories')
    @patch.object(CategorySelector, '_display_search_results')
    def test_search_categories_success(self, mock_display, mock_find, mock_input):
        mock_input.return_value = 'coffee'
        mock_find.return_value = [self.sample_categories[0]]
        mock_display.return_value = {'action': 'categorize', 'category': self.sample_categories[0]}
        
        result = self.selector._search_categories()
        
        assert result['action'] == 'categorize'
        mock_find.assert_called_once_with('coffee')
        mock_display.assert_called_once()
    
    @patch('builtins.input', return_value='back')
    def test_search_categories_back(self, mock_input):
        result = self.selector._search_categories()
        assert result['action'] == 'back'
    
    @patch('builtins.input', return_value='a')
    @patch('sys.stdout', new_callable=StringIO)
    def test_search_categories_too_short(self, mock_stdout, mock_input):
        mock_input.side_effect = ['a', 'back']
        
        result = self.selector._search_categories()
        
        output = mock_stdout.getvalue()
        assert 'Please enter at least 2 characters' in output
        assert result['action'] == 'back'
    
    @patch('builtins.input', return_value='xyz123')
    @patch('sys.stdout', new_callable=StringIO)
    def test_search_categories_no_matches(self, mock_stdout, mock_input):
        mock_input.side_effect = ['xyz123', 'back']
        
        result = self.selector._search_categories()
        
        output = mock_stdout.getvalue()
        assert 'No matching categories found' in output
        assert result['action'] == 'back'
    
    @patch('builtins.input', side_effect=KeyboardInterrupt())
    def test_search_categories_keyboard_interrupt(self, mock_input):
        result = self.selector._search_categories()
        assert result['action'] == 'back'
    
    def test_build_category_tree(self):
        tree = self.selector._build_category_tree()
        
        assert 'Food & Dining' in tree
        assert 'Transportation' in tree
        assert 'Shopping' in tree
        assert 'Bills' in tree
        
        assert 'Coffee' in tree['Food & Dining']
        assert 'Restaurants' in tree['Food & Dining']
        assert 'Gas' in tree['Transportation']
        assert 'Groceries' in tree['Shopping']
        assert 'Utilities' in tree['Bills']
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_category_tree(self, mock_stdout):
        self.selector.display_category_tree(max_depth=2)
        
        output = mock_stdout.getvalue()
        assert '- Bills' in output
        assert '  - Utilities' in output
        assert '- Food & Dining' in output
        assert '  - Coffee' in output
        assert '  - Restaurants' in output
    
    @patch('sys.stdout', new_callable=StringIO)
    def test_display_category_tree_limited_depth(self, mock_stdout):
        self.selector.display_category_tree(max_depth=1)
        
        output = mock_stdout.getvalue()
        assert '- Bills' in output
        assert '- Food & Dining' in output
        assert '  - Coffee' not in output