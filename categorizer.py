#!/usr/bin/env python3

import warnings
import logging
import sys
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Suppress urllib3 OpenSSL warning
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+.*')

from config import Config
from moneymoney_client import MoneyMoneyClient
from llm_client import LMStudioClient
from category_selector import CategorySelector

def setup_logging():
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    parser = argparse.ArgumentParser(
        description='AI-powered MoneyMoney transaction categorizer'
    )
    parser.add_argument(
        '--from-date',
        default=Config.DEFAULT_FROM_DATE,
        help='Start date for transactions (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--to-date',
        help='End date for transactions (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Non-interactive test mode: skip one transaction and quit'
    )
    
    args = parser.parse_args()
    
    try:
        categorizer = TransactionCategorizer(
            from_date=args.from_date,
            to_date=args.to_date,
            dry_run=args.dry_run,
            test_mode=args.test
        )
        categorizer.run()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"Error: {e}")
        sys.exit(1)

class TransactionCategorizer:
    
    def __init__(self, from_date: str, to_date: Optional[str] = None, dry_run: bool = False, test_mode: bool = False):
        self.from_date = from_date
        self.to_date = to_date
        self.dry_run = dry_run
        self.test_mode = test_mode
        
        self.logger = logging.getLogger(__name__)
        
        self.money_client = MoneyMoneyClient()
        self.llm_client = LMStudioClient()
        
        self.categories = []
        self.category_selector = None
        
        self.stats = {
            'processed': 0,
            'categorized': 0,
            'skipped': 0,
            'errors': 0
        }
    
    def run(self):
        print("MoneyMoney AI Transaction Categorizer")
        print("=" * 40)
        
        if not self._initialize():
            return
        
        transactions = self._load_transactions()
        if not transactions:
            print("No uncategorized transactions found.")
            return
        
        print(f"\nFound {len(transactions)} uncategorized transactions")
        print(f"Date range: {self.from_date} to {self.to_date or 'today'}")
        
        if self.dry_run:
            print("🔄 DRY RUN MODE - No changes will be made")
        
        if self.test_mode:
            print("🧪 TEST MODE - Will skip one transaction and quit")
        
        if not self.test_mode:
            input("\nPress Enter to start processing...")
        
        self._process_transactions(transactions)
        self._print_summary()
    
    def _initialize(self) -> bool:
        print("Initializing...")
        
        if not self.llm_client.test_connection():
            print("Error: Cannot connect to LM Studio. Please ensure it's running.")
            return False
        
        print("Loading categories from MoneyMoney...")
        self.categories = self.money_client.get_categories()
        
        if not self.categories:
            print("Error: No categories found in MoneyMoney.")
            return False
        
        self.category_selector = CategorySelector(self.categories, test_mode=self.test_mode)
        
        print(f"Loaded {len(self.categories)} categories")
        return True
    
    def _load_transactions(self) -> List[Dict]:
        print("Loading uncategorized transactions...")
        
        try:
            transactions = self.money_client.get_uncategorized_transactions(
                self.from_date, self.to_date
            )
            return transactions
        except Exception as e:
            self.logger.error(f"Failed to load transactions: {e}")
            print(f"Error loading transactions: {e}")
            return []
    
    def _process_transactions(self, transactions: List[Dict]):
        for i, transaction in enumerate(transactions, 1):
            print(f"\n{'═'*70}")
            print(f"🔢 Transaction {i}/{len(transactions)}")
            print('═'*70)
            
            print(self.money_client.format_transaction(transaction))
            
            self.stats['processed'] += 1
            
            try:
                if self._process_single_transaction(transaction):
                    self.stats['categorized'] += 1
                else:
                    self.stats['skipped'] += 1
            except Exception as e:
                self.logger.error(f"Error processing transaction {i}: {e}")
                self.stats['errors'] += 1
                print(f"Error processing transaction: {e}")
            
            # In test mode, process only one transaction then quit
            if self.test_mode:
                print("🧪 Test mode: Exiting after processing one transaction")
                break
    
    def _process_single_transaction(self, transaction: Dict) -> bool:
        print("🤖 Getting AI suggestions...")
        
        suggestions = self.llm_client.categorize_transaction(
            transaction, self.categories
        )
        
        # In test mode, fail if no suggestions are provided
        if self.test_mode and not suggestions:
            print("❌ TEST FAILED: No AI suggestions provided")
            print("🔧 Check LM Studio connection and model configuration")
            sys.exit(1)
        
        if suggestions:
            self.category_selector.display_suggestions(suggestions)
        else:
            print("🤖 No AI suggestions available.")
        
        while True:
            choice = self.category_selector.get_user_choice(suggestions)
            
            if not choice:
                print("Exiting...")
                sys.exit(0)
            
            action = choice.get('action')
            
            if action == 'skip':
                if self.test_mode:
                    print("✅ TEST PASSED: LLM suggestions provided successfully")
                print("Skipping transaction.")
                return False
            elif action == 'back':
                continue
            elif action == 'categorize':
                category = choice['category']
                return self._apply_categorization(transaction, category)
        
        return False
    
    def _apply_categorization(self, transaction: Dict, category: Dict) -> bool:
        category_path = category['full_name']
        transaction_id = transaction.get('id')
        
        if not transaction_id:
            print("Error: Transaction ID not found.")
            return False
        
        print(f"\n📂 Applying category: {category_path}")
        
        if self.dry_run:
            print("🔄 DRY RUN: Would categorize transaction")
            return True
        
        success = self.money_client.set_transaction_category(
            transaction_id, category_path
        )
        
        if success:
            print("✅ Category applied successfully")
        else:
            print("❌ Failed to apply category")
        
        return success
    
    def _print_summary(self):
        # Color codes
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        BOLD = '\033[1m'
        RESET = '\033[0m'
        
        print(f"\n{'═'*50}")
        print(f"📊 {BOLD}{CYAN}SUMMARY{RESET}")
        print('═'*50)
        print(f"📦 Transactions processed: {BOLD}{self.stats['processed']}{RESET}")
        print(f"✅ Successfully categorized: {GREEN}{BOLD}{self.stats['categorized']}{RESET}")
        print(f"⏭️  Skipped: {YELLOW}{BOLD}{self.stats['skipped']}{RESET}")
        print(f"❌ Errors: {RED}{BOLD}{self.stats['errors']}{RESET}")
        
        if self.stats['processed'] > 0:
            success_rate = (self.stats['categorized'] / self.stats['processed']) * 100
            if success_rate >= 80:
                rate_color = GREEN
                rate_icon = "🎉"
            elif success_rate >= 60:
                rate_color = YELLOW
                rate_icon = "👍"
            else:
                rate_color = RED
                rate_icon = "📈"
            print(f"{rate_icon} Success rate: {rate_color}{BOLD}{success_rate:.1f}%{RESET}")

if __name__ == '__main__':
    main()