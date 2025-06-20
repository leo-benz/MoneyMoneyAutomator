# MoneyMoney AI Transaction Categorizer

An AI-powered transaction categorization tool for MoneyMoney on macOS that uses Large Language Models to intelligently suggest categories for uncategorized transactions.

## Features

- **🤖 AI-Powered Categorization**: Uses LM Studio local LLM to analyze transactions and suggest appropriate categories with confidence levels
- **🎨 Colorful Interactive Interface**: Beautiful CLI with emojis, colors, and single-key navigation (no Enter key needed)
- **🔍 Fuzzy Search**: Find categories quickly with partial matching and fuzzy string matching
- **📂 Smart Category Filtering**: Only shows assignable leaf categories, automatically excludes parent/folder categories
- **💬 Rich Transaction Context**: Displays user comments, bank booking text, and purpose information for better categorization
- **🔄 Dry Run Mode**: Preview categorization without making changes
- **🧪 Test Mode**: Non-interactive testing mode for CI/CD and debugging
- **📅 Flexible Date Range**: Process transactions from specific date ranges
- **🏦 Account Information**: Shows transaction account names and details
- **📊 Comprehensive Logging**: Detailed logging for debugging and monitoring

## Prerequisites

- **macOS**: Required for MoneyMoney AppleScript integration
- **MoneyMoney**: The financial management application must be installed and running
- **LM Studio**: Local LLM server for AI categorization
- **Python 3.9+**: Required for running the application

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd MoneyMoneyAutomator
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up LM Studio**:
   - Install [LM Studio](https://lmstudio.ai/)
   - Download and load a compatible language model
   - Start the local server (default: http://localhost:1234/v1)

4. **Configure MoneyMoney**:
   - Ensure MoneyMoney is installed and accessible
   - The application will use AppleScript to communicate with MoneyMoney

## Configuration

The application can be configured using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LM_STUDIO_URL` | `http://localhost:1234/v1` | LM Studio API base URL |
| `NUM_SUGGESTIONS` | `5` | Number of AI suggestions to show |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

You can set these in your shell:
```bash
export LM_STUDIO_URL="http://localhost:1234/v1"
export NUM_SUGGESTIONS="3"
export LOG_LEVEL="DEBUG"
```

## Usage

### Basic Usage

Process uncategorized transactions from the last 30 days:
```bash
python3 categorizer.py
```

### Command Line Options

```bash
python3 categorizer.py [OPTIONS]
```

**Options:**
- `--from-date YYYY-MM-DD`: Start date for transactions (default: 30 days ago)
- `--to-date YYYY-MM-DD`: End date for transactions (default: today)
- `--dry-run`: Preview mode - show what would be done without making changes
- `--test`: Non-interactive test mode - requires LLM suggestions and fails if none provided

### Examples

```bash
# Process transactions from the last week
python3 categorizer.py --from-date 2024-01-15

# Process specific date range
python3 categorizer.py --from-date 2024-01-01 --to-date 2024-01-31

# Dry run to see what would happen
python3 categorizer.py --dry-run

# Non-interactive test mode for CI/CD (validates LLM integration)
python3 categorizer.py --test

# Process last 7 days with debug logging
LOG_LEVEL=DEBUG python3 categorizer.py --from-date $(date -d '7 days ago' +%Y-%m-%d)
```

## How It Works

1. **Initialization**: 
   - Connects to LM Studio server
   - Loads categories from MoneyMoney
   - Validates configuration

2. **Transaction Loading**:
   - Retrieves uncategorized transactions from MoneyMoney
   - Filters by date range

3. **AI Processing**:
   - Sends transaction details to LM Studio
   - Receives AI-generated category suggestions
   - Validates suggestions against available categories

4. **User Interaction**:
   - Displays transaction details and AI suggestions
   - Provides options to accept suggestions or search manually
   - Applies selected categorization to MoneyMoney

## Interactive Options

When processing each transaction, you have several options (no Enter key needed):

- **🎯 [1-5]**: Accept an AI suggestion
- **🔍 [s]**: Search all categories manually  
- **⏭️ [n]**: Skip this transaction
- **🚪 [q]**: Quit the application

### Search Mode

- Enter search terms (minimum 2 characters)
- Uses fuzzy matching to find relevant categories
- Shows up to 10 best matches
- Navigate back to suggestions or continue searching

## File Structure

```
MoneyMoneyAutomator/
├── categorizer.py          # Main application entry point
├── config.py              # Configuration management
├── llm_client.py          # LM Studio API client
├── moneymoney_client.py   # MoneyMoney AppleScript interface
├── category_selector.py   # Interactive category selection
├── requirements.txt       # Python dependencies
├── tests/                # Test files
└── README.md             # This file
```

## Core Components

### TransactionCategorizer
Main application class that orchestrates the categorization process.

### LMStudioClient
Handles communication with the LM Studio local LLM server for AI-powered categorization suggestions.

### MoneyMoneyClient
Manages AppleScript-based communication with MoneyMoney for reading transactions and applying categories.

### CategorySelector
Provides interactive user interface for category selection with fuzzy search capabilities.

## Error Handling

The application includes comprehensive error handling:

- **Connection Errors**: Validates LM Studio connectivity
- **AppleScript Errors**: Handles MoneyMoney communication issues
- **JSON Parsing**: Gracefully handles malformed LLM responses
- **User Input**: Validates and sanitizes user input

## Logging

Detailed logging is available at multiple levels:
- Transaction processing status
- API communication details
- Error messages and stack traces
- Performance metrics

Set `LOG_LEVEL=DEBUG` for verbose output during troubleshooting.

## Testing

### Unit Tests
Run the test suite:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest tests/ --cov=. --cov-report=html
```

### Integration Testing
Test the full application including LLM integration:
```bash
python3 categorizer.py --test
```

This will:
- ✅ Validate LM Studio connection
- ✅ Ensure AI suggestions are generated  
- ✅ Test transaction processing pipeline
- ❌ **Fail with exit code 1** if LLM doesn't provide suggestions

Perfect for CI/CD pipelines to ensure the AI integration is working correctly.

## Troubleshooting

### Common Issues

**"Cannot connect to LM Studio"**
- Ensure LM Studio is running and accessible
- Check the URL configuration
- Verify firewall settings

**"No categories found in MoneyMoney"**
- Ensure MoneyMoney is running
- Check that categories exist in your MoneyMoney setup
- Verify AppleScript permissions

**"EOF when reading a line"**
- This occurs when running in non-interactive environments
- Use `--test` mode for automated testing and CI/CD
- Use `--dry-run` for preview without changes
- Run in a proper terminal for interactive use

### Debug Mode

Enable debug logging for detailed troubleshooting:
```bash
LOG_LEVEL=DEBUG python3 categorizer.py --dry-run
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **MoneyMoney**: Excellent financial management software for macOS
- **LM Studio**: Local LLM server for privacy-focused AI processing
- **FuzzyWuzzy**: Fuzzy string matching for category search