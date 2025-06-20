import logging
import sys
import tty
import termios
from typing import List, Dict, Optional
from fuzzywuzzy import fuzz
from config import Config

logger = logging.getLogger(__name__)

class CategorySelector:
    
    def __init__(self, categories: List[Dict], test_mode: bool = False):
        self.categories = categories
        self.sorted_categories = sorted(categories, key=lambda x: x['full_name'])
        self.test_mode = test_mode
    
    def _getch(self) -> str:
        """Get a single character from stdin without requiring Enter."""
        if sys.stdin.isatty():
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch
        else:
            # Fallback for non-tty environments
            return input().strip().lower()[:1]
    
    def display_suggestions(self, suggestions: List[Dict]) -> None:
        # Color codes
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        BLUE = '\033[94m'
        MAGENTA = '\033[95m'
        BOLD = '\033[1m'
        RESET = '\033[0m'
        
        if not suggestions:
            print(f"\n🤖 {YELLOW}No LLM suggestions available.{RESET}")
            return
        
        print(f"\n🤖 {CYAN}{BOLD}AI Category Suggestions:{RESET}")
        print("─" * 60)
        
        for i, suggestion in enumerate(suggestions, 1):
            category = suggestion['category']
            confidence = suggestion.get('confidence', 0.0)
            reasoning = suggestion.get('reasoning', '')
            
            # Confidence color coding
            if confidence >= 0.8:
                conf_color = GREEN
                conf_icon = "🟢"
            elif confidence >= 0.6:
                conf_color = YELLOW
                conf_icon = "🟡"
            else:
                conf_color = '\033[91m'  # Red
                conf_icon = "🔴"
            
            print(f"{BOLD}{i}.{RESET} 📂 {BLUE}{category['full_name']}{RESET}")
            print(f"   {conf_icon} {BOLD}Confidence:{RESET} {conf_color}{confidence:.0%}{RESET}")
            if reasoning:
                print(f"   💭 {BOLD}Reasoning:{RESET} {reasoning}")
            print()
    
    def get_user_choice(self, suggestions: List[Dict]) -> Optional[Dict]:
        # Color codes
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        BOLD = '\033[1m'
        RESET = '\033[0m'
        
        # In test mode, automatically skip the transaction
        if self.test_mode:
            print(f"\n🧪 {BOLD}Test mode: Automatically skipping transaction{RESET}")
            return {'action': 'skip'}
        
        while True:
            try:
                print(f"\n⚡ {BOLD}Options:{RESET}")
                if suggestions:
                    print(f"   {GREEN}[1-{len(suggestions)}]{RESET} 🎯 Accept suggestion")
                print(f"   {CYAN}[s]{RESET} 🔍 Search all categories")
                print(f"   {YELLOW}[n]{RESET} ⏭️  Skip this transaction")
                print(f"   \033[91m[q]{RESET} 🚪 Quit")
                
                print(f"\n👉 {BOLD}Your choice (no Enter needed):{RESET} ", end='', flush=True)
                choice = self._getch().lower()
                print(f"{BOLD}{choice}{RESET}")  # Echo the choice with formatting
                
                if choice == 'q':
                    return None
                elif choice == 'n':
                    return {'action': 'skip'}
                elif choice == 's':
                    return self._search_categories()
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(suggestions):
                        return {
                            'action': 'categorize',
                            'category': suggestions[idx]['category']
                        }
                    else:
                        print(f"Invalid selection. Please choose 1-{len(suggestions)}")
                else:
                    print("Invalid input. Please try again.")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                return None
            except Exception as e:
                logger.error(f"Error in user choice: {e}")
                print("An error occurred. Please try again.")
    
    def _search_categories(self) -> Optional[Dict]:
        print("\nCategory Search")
        print("-" * 30)
        print("Enter search terms (minimum 2 characters), or 'back' to return:")
        
        while True:
            try:
                query = input("Search: ").strip()
                
                if query.lower() == 'back':
                    return {'action': 'back'}
                
                if len(query) < Config.SEARCH_MIN_CHARS:
                    print(f"Please enter at least {Config.SEARCH_MIN_CHARS} characters")
                    continue
                
                matches = self._find_matching_categories(query)
                
                if not matches:
                    print("No matching categories found. Try different search terms.")
                    continue
                
                selected = self._display_search_results(matches)
                if selected:
                    return selected
                    
            except KeyboardInterrupt:
                return {'action': 'back'}
    
    def _find_matching_categories(self, query: str) -> List[Dict]:
        matches = []
        query_lower = query.lower()
        
        for category in self.categories:
            full_name = category['full_name'].lower()
            name = category['name'].lower()
            
            if query_lower in full_name or query_lower in name:
                score = max(
                    fuzz.partial_ratio(query_lower, full_name),
                    fuzz.partial_ratio(query_lower, name)
                )
                matches.append((category, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return [match[0] for match in matches[:Config.MAX_SEARCH_RESULTS]]
    
    def _display_search_results(self, matches: List[Dict]) -> Optional[Dict]:
        print(f"\nFound {len(matches)} matching categories:")
        print("-" * 40)
        
        for i, category in enumerate(matches, 1):
            print(f"{i:2d}. {category['full_name']}")
        
        print(f"\n[1-{len(matches)}] Select category")
        print("[b] Back to search")
        print("[r] Return to suggestions")
        
        while True:
            try:
                print("Choice (no Enter needed): ", end='', flush=True)
                choice = self._getch().lower()
                print(choice)  # Echo the choice
                
                if choice == 'b':
                    return None
                elif choice == 'r':
                    return {'action': 'back'}
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(matches):
                        return {
                            'action': 'categorize',
                            'category': matches[idx]
                        }
                    else:
                        print(f"Invalid selection. Please choose 1-{len(matches)}")
                else:
                    print("Invalid input. Please try again.")
                    
            except ValueError:
                print("Invalid input. Please enter a number or command.")
    
    def display_category_tree(self, max_depth: int = 2) -> None:
        tree = self._build_category_tree()
        self._print_tree(tree, max_depth=max_depth)
    
    def _build_category_tree(self) -> Dict:
        tree = {}
        
        for category in self.categories:
            parts = category['full_name'].split('\\')
            current = tree
            
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        return tree
    
    def _print_tree(self, tree: Dict, indent: str = "", max_depth: int = 2, current_depth: int = 0) -> None:
        if current_depth >= max_depth:
            return
            
        for name, subtree in sorted(tree.items()):
            print(f"{indent}- {name}")
            if subtree and current_depth < max_depth - 1:
                self._print_tree(subtree, indent + "  ", max_depth, current_depth + 1)