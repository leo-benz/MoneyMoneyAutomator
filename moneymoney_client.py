import subprocess
import plistlib
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import logging
from config import Config

logger = logging.getLogger(__name__)

class MoneyMoneyClient:
    
    def __init__(self):
        self.app_name = "MoneyMoney"
        self._accounts_cache = None
    
    def _run_applescript(self, script: str) -> str:
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"AppleScript error: {e.stderr}")
            raise Exception(f"AppleScript execution failed: {e.stderr}")
    
    def get_categories(self) -> List[Dict]:
        script = f'tell application "{self.app_name}" to export categories'
        plist_data = self._run_applescript(script)
        
        try:
            categories = plistlib.loads(plist_data.encode('utf-8'))
            
            # Debug: Log the raw category structure
            logger.debug(f"Raw categories structure: {len(categories)} categories found")
            
            # Count total categories before filtering
            total_count = len(categories)
            
            # Process indentation-based hierarchy from MoneyMoney
            flattened = self._process_indentation_hierarchy(categories)
            
            # Debug: Log some example flattened categories
            if flattened:
                logger.debug(f"Example flattened categories:")
                for i, cat in enumerate(flattened[:5]):  # First 5 examples
                    logger.debug(f"  {i+1}. name='{cat['name']}', full_name='{cat['full_name']}', parent_path='{cat.get('parent_path', '')}'")
            
            logger.info(f"Loaded {len(flattened)} assignable categories (leaf nodes) out of {total_count} total categories")
            
            return flattened
        except Exception as e:
            logger.error(f"Failed to parse categories: {e}")
            return []
    
    def _count_all_categories(self, categories: List[Dict]) -> int:
        """Count all categories including parent nodes."""
        count = 0
        for category in categories:
            count += 1
            if 'categories' in category and category['categories']:
                count += self._count_all_categories(category['categories'])
        return count
    
    def _flatten_categories(self, categories: List[Dict], parent_path: str = "") -> List[Dict]:
        flattened = []
        
        for category in categories:
            name = category.get('name', '')
            uuid = category.get('uuid', '')
            
            current_path = f"{parent_path} > {name}" if parent_path else name
            
            # Check if this category has subcategories
            has_subcategories = 'categories' in category and category['categories']
            
            # Check if this is a group/folder category (not assignable)
            is_group = category.get('group', False)
            
            # Only include categories that are:
            # 1. Leaf nodes (no subcategories) AND
            # 2. Not group categories (assignable)
            if not has_subcategories and not is_group:
                flattened.append({
                    'uuid': uuid,
                    'name': name,
                    'path': current_path,
                    'full_name': current_path
                })
            
            # Recursively process subcategories
            if has_subcategories:
                flattened.extend(
                    self._flatten_categories(category['categories'], current_path)
                )
        
        return flattened
    
    def _flatten_categories_with_context(self, categories: List[Dict], parent_path: str = "", parent_path_mm: str = "", hierarchy_level: int = 1) -> List[Dict]:
        """Enhanced category flattening that includes parent context and hierarchy information."""
        flattened = []
        
        for category in categories:
            name = category.get('name', '')
            uuid = category.get('uuid', '')
            
            # Build current path with ' > ' separator for display
            current_path = f"{parent_path} > {name}" if parent_path else name
            
            # Build MoneyMoney path with '\' separator for API compatibility
            current_path_mm = f"{parent_path_mm}\\{name}" if parent_path_mm else name
            
            # Check if this category has subcategories
            has_subcategories = 'categories' in category and category['categories']
            
            # Check if this is a group/folder category (not assignable)
            is_group = category.get('group', False)
            
            # Only include categories that are:
            # 1. Leaf nodes (no subcategories) AND
            # 2. Not group categories (assignable)
            if not has_subcategories and not is_group:
                flattened.append({
                    'uuid': uuid,
                    'name': name,
                    'path': current_path,
                    'full_name': current_path,  # Display format with ' > '
                    'moneymoney_path': current_path_mm,  # MoneyMoney API format with '\'
                    'parent_path': parent_path,
                    'hierarchy_level': hierarchy_level
                })
                logger.debug(f"Added leaf category: '{current_path}' (MM path: '{current_path_mm}', UUID: {uuid})")
            
            # Recursively process subcategories
            if has_subcategories:
                logger.debug(f"Processing subcategories for: '{current_path}' (has {len(category['categories'])} subcategories)")
                flattened.extend(
                    self._flatten_categories_with_context(
                        category['categories'], 
                        current_path,
                        current_path_mm,
                        hierarchy_level + 1
                    )
                )
        
        return flattened
    
    def _process_indentation_hierarchy(self, categories: List[Dict]) -> List[Dict]:
        """Process MoneyMoney's indentation-based category hierarchy."""
        flattened = []
        parent_stack = []  # Stack to track parent categories at each level
        
        for category in categories:
            name = category.get('name', '')
            uuid = category.get('uuid', '')
            indentation = category.get('indentation', 0)
            is_group = category.get('group', False)
            
            # Adjust parent stack based on current indentation level
            # Keep only parents at levels less than current indentation
            parent_stack = parent_stack[:indentation]
            
            # Build the current hierarchy path
            if parent_stack:
                # Create display path with ' > ' separator
                parent_names = [p['name'] for p in parent_stack]
                current_path = ' > '.join(parent_names + [name])
                parent_path = ' > '.join(parent_names)
                
                # Create MoneyMoney API path with '\' separator  
                current_path_mm = '\\'.join(parent_names + [name])
            else:
                # Top-level category
                current_path = name
                parent_path = ""
                current_path_mm = name
            
            # Only include leaf categories (not group categories) in the result
            if not is_group:
                flattened.append({
                    'uuid': uuid,
                    'name': name,
                    'path': current_path,
                    'full_name': current_path,  # Display format with ' > '
                    'moneymoney_path': current_path_mm,  # MoneyMoney API format with '\'
                    'parent_path': parent_path,
                    'hierarchy_level': indentation + 1  # 1-based level
                })
                logger.debug(f"Added leaf category: '{current_path}' (MM path: '{current_path_mm}', UUID: {uuid})")
            else:
                # Group category - add to parent stack for subsequent categories
                parent_stack.append({
                    'name': name,
                    'uuid': uuid,
                    'indentation': indentation
                })
                logger.debug(f"Processing group category: '{current_path}' (indentation: {indentation})")
        
        return flattened
    
    def get_accounts(self) -> Dict[str, str]:
        """Get account UUIDs mapped to account names."""
        if self._accounts_cache is not None:
            return self._accounts_cache
            
        script = f'tell application "{self.app_name}" to export accounts'
        try:
            plist_data = self._run_applescript(script)
            accounts_data = plistlib.loads(plist_data.encode('utf-8'))
            
            accounts_map = {}
            if isinstance(accounts_data, list):
                for account in accounts_data:
                    uuid = account.get('uuid', '')
                    name = account.get('name', 'Unknown')
                    if uuid:
                        accounts_map[uuid] = name
            
            self._accounts_cache = accounts_map
            return accounts_map
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            return {}
    
    def get_uncategorized_transactions(self, from_date: str, to_date: Optional[str] = None) -> List[Dict]:
        script_parts = [
            f'tell application "{self.app_name}"',
            f'export transactions from category "" from date "{from_date}"'
        ]
        
        if to_date:
            script_parts[1] += f' to date "{to_date}"'
        
        script_parts[1] += ' as "plist"'
        script_parts.append('end tell')
        
        script = '\n'.join(script_parts)
        plist_data = self._run_applescript(script)
        
        try:
            data = plistlib.loads(plist_data.encode('utf-8'))
            all_transactions = []
            
            if isinstance(data, dict) and 'transactions' in data:
                all_transactions = data['transactions'] or []
            elif isinstance(data, list):
                all_transactions = data or []
            else:
                logger.warning(f"Unexpected data format from MoneyMoney: {type(data)}")
                return []
            
            # Filter for truly uncategorized transactions (no category or empty category)
            uncategorized = []
            for transaction in all_transactions:
                category = transaction.get('category', '')
                # Consider empty string, None, or missing category as uncategorized
                if not category or category.strip() == '':
                    uncategorized.append(transaction)
            
            # Filter out pending transactions if configured to do so
            if Config.EXCLUDE_PENDING_TRANSACTIONS:
                booked_transactions = []
                pending_count = 0
                
                for transaction in uncategorized:
                    if self._is_transaction_booked(transaction):
                        booked_transactions.append(transaction)
                    else:
                        pending_count += 1
                
                logger.info(f"Found {len(all_transactions)} total transactions, {len(uncategorized)} uncategorized, {pending_count} pending transactions excluded")
                return booked_transactions
            else:
                logger.info(f"Found {len(all_transactions)} total transactions, {len(uncategorized)} uncategorized")
                return uncategorized
            
        except Exception as e:
            logger.error(f"Failed to parse transactions: {e}")
            return []
    
    def _is_transaction_booked(self, transaction: Dict) -> bool:
        """Determine if a transaction is fully booked (not pending)."""
        # Check explicit booked flag
        booked_flag = transaction.get('booked')
        if booked_flag is not None:
            # If explicitly set to False, it's pending
            if booked_flag is False:
                return False
            # If explicitly set to True, it's booked
            if booked_flag is True:
                return True
        
        # Check for booking date presence
        booking_date = transaction.get('bookingDate')
        if booking_date is not None:
            # Has a booking date, likely booked
            return True
        
        # If neither booked flag nor booking date is present/reliable,
        # treat as pending for safety (conservative approach)
        if booked_flag is None and booking_date is None:
            return False
        
        # Default to booked if we have some indication it's processed
        return True
    
    def set_transaction_category(self, transaction_id: int, category_path: str) -> bool:
        # Escape quotes and backslashes in the category path for AppleScript
        escaped_path = category_path.replace('\\', '\\\\').replace('"', '\\"')
        
        script = f'''tell application "{self.app_name}"
    set transaction id {transaction_id} category to "{escaped_path}"
end tell'''
        
        try:
            self._run_applescript(script)
            logger.info(f"Set transaction {transaction_id} to category '{category_path}'")
            return True
        except Exception as e:
            logger.error(f"Failed to set category for transaction {transaction_id}: {e}")
            return False
    
    def format_transaction(self, transaction: Dict) -> str:
        name = transaction.get('name', 'Unknown')
        amount = transaction.get('amount', 0)
        currency = transaction.get('currency', 'EUR')
        
        # Handle both date fields that MoneyMoney provides
        date = transaction.get('bookingDate') or transaction.get('valueDate') or 'Unknown'
        if hasattr(date, 'strftime'):
            date = date.strftime('%Y-%m-%d')
        
        purpose = transaction.get('purpose', '')
        comment = transaction.get('comment', '')
        booking_text = transaction.get('bookingText', '')
        
        # Get account name from UUID
        account_uuid = transaction.get('accountUuid', '')
        accounts = self.get_accounts()
        account = accounts.get(account_uuid, 'Unknown')
        
        # Color codes
        CYAN = '\033[96m'
        GREEN = '\033[92m'
        YELLOW = '\033[93m'
        RED = '\033[91m'
        BOLD = '\033[1m'
        RESET = '\033[0m'
        
        # Amount color based on positive/negative
        amount_color = GREEN if amount > 0 else RED
        amount_symbol = '💰' if amount > 0 else '💸'
        
        formatted = f"📅 {CYAN}{BOLD}Date:{RESET} {date}\n"
        formatted += f"🏦 {CYAN}{BOLD}Account:{RESET} {account}\n"
        formatted += f"🏪 {CYAN}{BOLD}Name:{RESET} {name}\n"
        formatted += f"{amount_symbol} {CYAN}{BOLD}Amount:{RESET} {amount_color}{amount:.2f} {currency}{RESET}\n"
        
        if purpose:
            formatted += f"📝 {CYAN}{BOLD}Purpose:{RESET} {purpose}\n"
        
        if comment:
            formatted += f"💬 {CYAN}{BOLD}Comment:{RESET} {comment}\n"
            
        if booking_text:
            formatted += f"🏛️ {CYAN}{BOLD}Booking Text:{RESET} {booking_text}\n"
        
        return formatted