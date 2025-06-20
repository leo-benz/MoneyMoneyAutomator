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
from cache_manager import CacheManager

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
    parser.add_argument(
        '--pre-run-only',
        action='store_true',
        help='Only generate and cache AI suggestions, no user interaction'
    )
    parser.add_argument(
        '--apply-only',
        action='store_true',
        help='Only run interactive mode using cached suggestions'
    )
    
    args = parser.parse_args()
    
    try:
        categorizer = TransactionCategorizer(
            from_date=args.from_date,
            to_date=args.to_date,
            dry_run=args.dry_run,
            test_mode=args.test,
            pre_run_only=args.pre_run_only,
            apply_only=args.apply_only
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
    
    def __init__(self, from_date: str, to_date: Optional[str] = None, dry_run: bool = False, test_mode: bool = False, 
                 pre_run_only: bool = False, apply_only: bool = False, combined_mode: bool = None):
        self.from_date = from_date
        self.to_date = to_date
        self.dry_run = dry_run
        self.test_mode = test_mode
        self.pre_run_only = pre_run_only
        self.apply_only = apply_only
        
        # Determine mode: combined is default unless specific mode is selected
        if combined_mode is None:
            self.combined_mode = not (pre_run_only or apply_only)
        else:
            self.combined_mode = combined_mode
        
        self.logger = logging.getLogger(__name__)
        
        self.money_client = MoneyMoneyClient()
        self.llm_client = LMStudioClient()
        self.cache_manager = CacheManager()
        
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
        elif self.pre_run_only:
            print("🤖 PRE-RUN MODE - Generating AI suggestions for all transactions")
        elif self.apply_only:
            print("⚡ APPLY MODE - Using cached AI suggestions")
        else:
            print("🔄 COMBINED MODE - Pre-processing all transactions, then interactive confirmation")
        
        # Route to appropriate mode
        if self.pre_run_only:
            self._run_pre_run_only()
        elif self.apply_only:
            self._run_apply_only()
        elif self.combined_mode:
            self._run_combined_mode()
        else:
            # Legacy mode for test_mode
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
    
    def _run_combined_mode(self):
        """Run combined mode: pre-process all transactions, then interactive confirmation."""
        transactions = self._load_transactions()
        
        if not transactions:
            print("No uncategorized transactions found.")
            return
        
        print(f"\n{'='*60}")
        print("🤖 PHASE 1: Pre-processing transactions with AI...")
        print('='*60)
        
        # Pre-process all transactions
        cached_count = 0
        for i, transaction in enumerate(transactions, 1):
            transaction_id = transaction.get('id')
            if not transaction_id:
                continue
                
            # Skip if already cached
            if self.cache_manager.has_suggestions(transaction_id):
                cached_count += 1
                continue
            
            print(f"Processing transaction {i}/{len(transactions)}: {transaction.get('name', 'Unknown')[:30]}...")
            
            try:
                suggestions = self.llm_client.categorize_transaction(transaction, self.categories)
                if suggestions:
                    self.cache_manager.store_suggestions(transaction_id, suggestions)
                    cached_count += 1
            except Exception as e:
                self.logger.error(f"Error pre-processing transaction {transaction_id}: {e}")
        
        print(f"\n✅ Pre-processing complete! {cached_count}/{len(transactions)} transactions have AI suggestions")
        
        print(f"\n{'='*60}")
        print("⚡ PHASE 2: Interactive confirmation...")
        print('='*60)
        
        if not self.test_mode:
            input("Press Enter to start interactive confirmation...")
        
        # Now run interactive confirmation using cached suggestions
        for i, transaction in enumerate(transactions, 1):
            print(f"\n{'═'*70}")
            print(f"🔢 Transaction {i}/{len(transactions)}")
            print('═'*70)
            
            print(self.money_client.format_transaction(transaction))
            
            self.stats['processed'] += 1
            
            try:
                if self._process_single_transaction_cached(transaction):
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
    
    def _run_pre_run_only(self):
        """Run pre-run only mode: generate and cache AI suggestions."""
        transactions = self._load_transactions()
        
        if not transactions:
            print("No uncategorized transactions found.")
            return
        
        print(f"\nPre-processing {len(transactions)} transactions...")
        
        cached_count = 0
        for i, transaction in enumerate(transactions, 1):
            transaction_id = transaction.get('id')
            if not transaction_id:
                continue
            
            # Skip if already cached
            if self.cache_manager.has_suggestions(transaction_id):
                print(f"Transaction {i}/{len(transactions)}: Already cached")
                cached_count += 1
                continue
            
            print(f"Processing transaction {i}/{len(transactions)}: {transaction.get('name', 'Unknown')[:30]}...")
            
            try:
                suggestions = self.llm_client.categorize_transaction(transaction, self.categories)
                if suggestions:
                    self.cache_manager.store_suggestions(transaction_id, suggestions)
                    cached_count += 1
                    print(f"  ✅ Cached {len(suggestions)} suggestions")
                else:
                    print("  ⚠️ No suggestions generated")
            except Exception as e:
                self.logger.error(f"Error processing transaction {transaction_id}: {e}")
                print(f"  ❌ Error: {e}")
        
        print(f"\n✅ Pre-processing complete! {cached_count}/{len(transactions)} transactions have cached AI suggestions")
        print("Run with --apply-only to interactively confirm the suggestions")
    
    def _run_apply_only(self):
        """Run apply-only mode: use cached suggestions for interactive confirmation."""
        cached_ids = self.cache_manager.get_cached_transaction_ids()
        
        if not cached_ids:
            print("No cached suggestions found. Run without --apply-only or with --pre-run-only first.")
            return
        
        transactions = self._load_transactions()
        
        if not transactions:
            print("No uncategorized transactions found.")
            return
        
        # Filter transactions to only those with cached suggestions
        cached_transactions = [t for t in transactions if str(t.get('id', '')) in cached_ids]
        
        if not cached_transactions:
            print("No cached suggestions match current uncategorized transactions.")
            return
        
        print(f"\nFound {len(cached_transactions)} transactions with cached AI suggestions")
        
        if not self.test_mode:
            input("Press Enter to start interactive confirmation...")
        
        for i, transaction in enumerate(cached_transactions, 1):
            print(f"\n{'═'*70}")
            print(f"🔢 Transaction {i}/{len(cached_transactions)}")
            print('═'*70)
            
            print(self.money_client.format_transaction(transaction))
            
            self.stats['processed'] += 1
            
            try:
                if self._process_single_transaction_cached(transaction):
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
    
    def _process_single_transaction_cached(self, transaction: Dict) -> bool:
        """Process a single transaction using cached suggestions."""
        transaction_id = transaction.get('id')
        if not transaction_id:
            print("Error: Transaction ID not found.")
            return False
        
        # Get cached suggestions
        suggestions = self.cache_manager.get_suggestions(transaction_id)
        
        if not suggestions:
            print("🤖 No cached AI suggestions available.")
        
        # In test mode, fail if no suggestions are provided
        if self.test_mode and not suggestions:
            print("❌ TEST FAILED: No cached AI suggestions provided")
            sys.exit(1)
        
        if suggestions:
            self.category_selector.display_suggestions(suggestions)
        
        while True:
            choice = self.category_selector.get_user_choice(suggestions)
            
            if not choice:
                print("Exiting...")
                sys.exit(0)
            
            action = choice.get('action')
            
            if action == 'skip':
                if self.test_mode:
                    print("✅ TEST PASSED: Cached suggestions provided successfully")
                print("Skipping transaction.")
                # Clean up cache entry for skipped transaction
                self.cache_manager.remove_suggestions(transaction_id)
                return False
            elif action == 'back':
                continue
            elif action == 'categorize':
                category = choice['category']
                success = self._apply_categorization(transaction, category)
                if success:
                    # Offer rule generation after successful categorization
                    if not self.test_mode:
                        self._propose_rule_generation(transaction, category)
                    # Clean up cache entry for successfully categorized transaction
                    self.cache_manager.remove_suggestions(transaction_id)
                return success
        
        return False
    
    def _propose_rule_generation(self, transaction: Dict, category: Dict) -> None:
        """Propose generating a categorization rule for the transaction."""
        try:
            # Ask user if they want to generate a rule
            if not self.category_selector.offer_rule_generation():
                return
            
            print("🤖 Generating categorization rule...")
            
            # Generate rule using AI
            rule = self.llm_client.generate_categorization_rule(transaction, category)
            
            if not rule:
                print("❌ Failed to generate rule. Please try again later.")
                return
            
            # Display rule proposal and handle user choice
            choice = self.category_selector.display_rule_proposal(rule)
            
            if choice == 'copy':
                print("📋 Rule has been copied to clipboard!")
                print("💡 You can now paste it into MoneyMoney's categorization rules.")
            
        except Exception as e:
            self.logger.error(f"Error in rule generation: {e}")
            print("❌ An error occurred while generating the rule.")
    
    def _copy_to_clipboard(self, text: str) -> bool:
        """Copy text to clipboard using pbcopy."""
        try:
            import subprocess
            process = subprocess.run(
                ['pbcopy'],
                input=text.encode(),
                check=True
            )
            return process.returncode == 0
        except Exception as e:
            self.logger.error(f"Failed to copy to clipboard: {e}")
            return False

if __name__ == '__main__':
    main()