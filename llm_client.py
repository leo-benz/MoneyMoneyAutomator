import requests
import json
import logging
from typing import List, Dict, Optional
from config import Config

logger = logging.getLogger(__name__)

class LMStudioClient:
    
    def __init__(self):
        self.base_url = Config.LM_STUDIO_BASE_URL
        self.model = Config.LM_STUDIO_MODEL
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json'
        })
    
    def categorize_transaction(self, transaction: Dict, categories: List[Dict]) -> List[Dict]:
        category_list = self._format_categories_for_prompt(categories)
        
        prompt = self._build_categorization_prompt(transaction, category_list)
        
        try:
            response = self._call_llm(prompt)
            suggestions = self._parse_suggestions(response, categories)
            return suggestions[:Config.NUM_SUGGESTIONS]
        except Exception as e:
            logger.error(f"LLM categorization failed: {e}")
            return []
    
    def _format_categories_for_prompt(self, categories: List[Dict]) -> str:       
        formatted = []
        for cat in categories:
            # Use MoneyMoney path format for consistency with existing training data
            path_for_llm = cat.get('moneymoney_path', cat['full_name'])
            category_line = f"- {path_for_llm} (UUID: {cat['uuid']})"
            
            # Add hierarchy context if available
            if 'parent_path' in cat and cat['parent_path']:
                category_line += f" [Parent: {cat['parent_path']}]"
            if 'hierarchy_level' in cat:
                category_line += f" [Level: {cat['hierarchy_level']}]"
                
            formatted.append(category_line)
        return '\n'.join(formatted)
    
    def _build_categorization_prompt(self, transaction: Dict, category_list: str) -> str:
        name = transaction.get('name', 'Unknown')
        amount = transaction.get('amount', 0)
        purpose = transaction.get('purpose', '')
        comment = transaction.get('comment', '')
        booking_text = transaction.get('bookingText', '')
        
        # Clean purpose to remove saveback/cashback information that confuses categorization
        cleaned_purpose = purpose
        if purpose:
            # Remove saveback/cashback mentions as they don't indicate the transaction category
            import re
            cleaned_purpose = re.sub(r'saveback:?\s*[\d,.\s€$]+', '', purpose, flags=re.IGNORECASE)
            cleaned_purpose = re.sub(r'cashback:?\s*[\d,.\s€$]+', '', cleaned_purpose, flags=re.IGNORECASE)
            cleaned_purpose = cleaned_purpose.strip()
        
        # Build transaction description with all available information
        transaction_desc = f"Merchant/Name: {name}\nAmount: {amount}"
        
        if cleaned_purpose:
            transaction_desc += f"\nDescription: {cleaned_purpose}"
            
        if comment:
            transaction_desc += f"\nUser Comment: {comment}"
            
        if booking_text:
            transaction_desc += f"\nBank Booking Text: {booking_text}"
        
        prompt = f"""You are a financial transaction categorization assistant. Analyze the following transaction and suggest the most appropriate categories from the provided list.

IMPORTANT: Only suggest categories that are in the provided list. Each suggestion must include the exact category path and UUID from the list.

The categories are organized hierarchically - use this context to make better suggestions:
- Higher hierarchy levels (like Level 3) are more specific than lower levels (Level 1)
- Parent categories provide context for understanding the category's purpose
- Choose the most specific category that matches the transaction when possible

Transaction Details:
{transaction_desc}

Available Categories (with hierarchy context):
{category_list}

Please provide your top {Config.NUM_SUGGESTIONS} category suggestions in the following JSON format:
{{
    "suggestions": [
        {{
            "category_path": "Exact category name from list",
            "uuid": "exact-uuid-from-list",
            "confidence": 0.85,
            "reasoning": "Brief explanation for this categorization"
        }}
    ]
}}

Categorization Guidelines:
1. Focus primarily on the merchant/company name
2. Consider the transaction amount for context
3. Use user comments for additional context and intent
4. Consider bank booking text for transaction type information
5. Match to logical expense categories
6. Ignore saveback/cashback information - categorize based on the actual purchase
7. Only use categories from the provided list with exact names and UUIDs
8. IMPORTANT: Each category UUID must appear only once in your suggestions - do not duplicate categories

Respond only with valid JSON."""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.3,
            "max_tokens": 8000,
            "stream": False
        }
        
        # Add model specification if configured or auto-detect
        model_to_use = self._get_model_to_use()
        if model_to_use:
            payload["model"] = model_to_use
        
        try:
            response = self.session.post(url, json=payload, timeout=240)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            raise
    
    def _parse_suggestions(self, llm_response: str, categories: List[Dict]) -> List[Dict]:
        try:
            # Clean the response - remove thinking tags first (DeepSeek model outputs these)
            cleaned_response = llm_response.strip()
            
            # Remove thinking tags that DeepSeek models output
            import re
            cleaned_response = re.sub(r'<think>.*?</think>', '', cleaned_response, flags=re.DOTALL)
            cleaned_response = re.sub(r'<thinking>.*?</thinking>', '', cleaned_response, flags=re.DOTALL)
            cleaned_response = cleaned_response.strip()
            
            # Handle markdown-wrapped JSON
            if '```json' in cleaned_response:
                # Extract JSON from markdown code blocks
                start = cleaned_response.find('```json') + 7
                end = cleaned_response.find('```', start)
                if end != -1:
                    cleaned_response = cleaned_response[start:end].strip()
            elif '```' in cleaned_response:
                # Handle generic code blocks
                start = cleaned_response.find('```') + 3
                end = cleaned_response.find('```', start)
                if end != -1:
                    cleaned_response = cleaned_response[start:end].strip()
            
            logger.debug(f"Cleaned LLM response: {cleaned_response}")
            data = json.loads(cleaned_response)
            suggestions = data.get('suggestions', [])
            
            validated_suggestions = []
            seen_uuids = set()
            
            for suggestion in suggestions:
                category_path = suggestion.get('category_path', '')
                uuid = suggestion.get('uuid', '')
                confidence = suggestion.get('confidence', 0.0)
                reasoning = suggestion.get('reasoning', '')
                
                matching_category = self._find_category_by_path_or_uuid(
                    categories, category_path, uuid
                )
                
                if matching_category and matching_category['uuid'] not in seen_uuids:
                    seen_uuids.add(matching_category['uuid'])
                    validated_suggestions.append({
                        'category': matching_category,
                        'confidence': confidence,
                        'reasoning': reasoning
                    })
            
            return validated_suggestions
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw LLM response: {repr(llm_response)}")
            return []
    
    def _find_category_by_path_or_uuid(self, categories: List[Dict], path: str, uuid: str) -> Optional[Dict]:
        # First try exact matches
        for category in categories:
            if (category['uuid'] == uuid or 
                category['full_name'] == path or 
                category.get('moneymoney_path', '') == path):
                return category
        
        # Then try partial matches on both path formats
        for category in categories:
            if (path.lower() in category['full_name'].lower() or
                path.lower() in category.get('moneymoney_path', '').lower()):
                return category
        
        return None
    
    def _get_model_to_use(self) -> Optional[str]:
        """Get the model to use for API calls. Returns configured model or auto-detects."""
        if self.model:
            logger.debug(f"Using configured model: {self.model}")
            return self.model
        
        # Auto-detect available models
        try:
            available_models = self._get_available_models()
            if not available_models:
                logger.warning("No models available in LM Studio")
                return None
            
            if len(available_models) == 1:
                model = available_models[0]
                logger.info(f"Auto-detected single model: {model}")
                return model
            
            # Multiple models available - prefer chat models, then pick the first one
            chat_models = [m for m in available_models if any(keyword in m.lower() 
                          for keyword in ['chat', 'instruct', 'conversation'])]
            
            if chat_models:
                model = chat_models[0]
                logger.info(f"Auto-selected chat model: {model} from {len(available_models)} available models")
                return model
            else:
                model = available_models[0]
                logger.info(f"Auto-selected first model: {model} from {len(available_models)} available models")
                return model
                
        except Exception as e:
            logger.error(f"Failed to auto-detect model: {e}")
            return None
    
    def _get_available_models(self) -> List[str]:
        """Get list of available models from LM Studio."""
        try:
            url = f"{self.base_url}/models"
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            
            result = response.json()
            models = [model.get('id', '') for model in result.get('data', [])]
            return [m for m in models if m]  # Filter out empty strings
            
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []
    
    def generate_categorization_rule(self, transaction: Dict, category: Dict) -> Optional[Dict]:
        """Generate a MoneyMoney categorization rule for the given transaction and category."""
        name = transaction.get('name', 'Unknown')
        amount = transaction.get('amount', 0)
        purpose = transaction.get('purpose', '')
        comment = transaction.get('comment', '')
        booking_text = transaction.get('bookingText', '')
        
        # Build transaction description for rule generation
        transaction_desc = f"Merchant/Name: {name}\nAmount: {amount}"
        
        if purpose:
            transaction_desc += f"\nDescription: {purpose}"
            
        if comment:
            transaction_desc += f"\nUser Comment: {comment}"
            
        if booking_text:
            transaction_desc += f"\nBank Booking Text: {booking_text}"
        
        category_path = category.get('full_name', 'Unknown')
        
        prompt = f"""You are an expert at creating MoneyMoney categorization rules. Generate a precise rule that would automatically categorize similar transactions to the category "{category_path}".

Transaction to analyze:
{transaction_desc}

Target Category: {category_path}

MoneyMoney Rule Syntax:
- Search for words using text in quotes: "STARBUCKS"
- Use field prefixes: name:"text", purpose:"text", amount>value, amount<value
- Combine conditions: AND, OR, NOT
- Use parentheses for grouping: (condition1 OR condition2) AND condition3
- Available fields: name, purpose, local_account, remote_account, currency, reference, mandate, creditor_id, comment, booking_text

Create a rule that:
1. Is specific enough to avoid false positives
2. Is general enough to catch similar transactions
3. Uses the most reliable transaction fields (name is usually most reliable)
4. Considers amount ranges if relevant for this type of transaction

Respond with JSON in this exact format:
{{
    "rule": "exact MoneyMoney rule syntax here",
    "explanation": "brief explanation of what this rule matches",
    "confidence": 0.85
}}

Examples of good rules:
- name:"STARBUCKS" (matches all Starbucks transactions)
- name:"SHELL" AND purpose:"FUEL" (gas station fuel purchases)
- name:"AMAZON" AND amount<50.00 (small Amazon purchases)
- purpose:"SALARY" OR purpose:"WAGE" (salary payments)

Respond only with valid JSON."""

        try:
            response = self._call_llm(prompt)
            return self._parse_rule_response(response)
        except Exception as e:
            logger.error(f"Rule generation failed: {e}")
            return None
    
    def _parse_rule_response(self, llm_response: str) -> Optional[Dict]:
        """Parse the LLM response for rule generation."""
        try:
            # Clean the response - remove thinking tags first
            cleaned_response = llm_response.strip()
            
            # Remove thinking tags that some models output
            import re
            cleaned_response = re.sub(r'<think>.*?</think>', '', cleaned_response, flags=re.DOTALL)
            cleaned_response = re.sub(r'<thinking>.*?</thinking>', '', cleaned_response, flags=re.DOTALL)
            cleaned_response = cleaned_response.strip()
            
            # Handle markdown-wrapped JSON
            if '```json' in cleaned_response:
                start = cleaned_response.find('```json') + 7
                end = cleaned_response.find('```', start)
                if end != -1:
                    cleaned_response = cleaned_response[start:end].strip()
            elif '```' in cleaned_response:
                start = cleaned_response.find('```') + 3
                end = cleaned_response.find('```', start)
                if end != -1:
                    cleaned_response = cleaned_response[start:end].strip()
            
            logger.debug(f"Cleaned rule response: {cleaned_response}")
            data = json.loads(cleaned_response)
            
            # Validate required fields
            if 'rule' in data and 'explanation' in data and 'confidence' in data:
                return {
                    'rule': data['rule'],
                    'explanation': data['explanation'],
                    'confidence': float(data['confidence'])
                }
            else:
                logger.error("Rule response missing required fields")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse rule response as JSON: {e}")
            logger.error(f"Raw response: {repr(llm_response)}")
            return None
        except Exception as e:
            logger.error(f"Error parsing rule response: {e}")
            return None

    def test_connection(self) -> bool:
        try:
            available_models = self._get_available_models()
            if not available_models:
                logger.error("LM Studio connection failed: No models available")
                return False
            
            logger.info(f"LM Studio connection successful - {len(available_models)} model(s) available")
            if len(available_models) > 1:
                selected_model = self._get_model_to_use()
                logger.info(f"Will use model: {selected_model}")
            
            return True
        except Exception as e:
            logger.error(f"LM Studio connection failed: {e}")
            return False