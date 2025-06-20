# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Testing
```bash
# Run all tests with verbose output
python3 -m pytest tests/ -v

# Run tests with coverage report
python3 -m pytest tests/ --cov=. --cov-report=term-missing

# Run a specific test file
python3 -m pytest tests/test_llm_client.py -v

# Run a specific test method
python3 -m pytest tests/test_categorizer.py::TestTransactionCategorizer::test_init_default_values -v
```

### Running the Application
```bash
# Normal operation (interactive)
python3 categorizer.py

# Dry run mode (safe preview)
python3 categorizer.py --dry-run

# Non-interactive test mode (skip one transaction and quit)
python3 categorizer.py --test

# Specific date range
python3 categorizer.py --from-date 2024-01-01 --to-date 2024-01-31

# With debug logging
LOG_LEVEL=DEBUG python3 categorizer.py --dry-run
```

### Dependencies
```bash
# Install all dependencies
pip3 install -r requirements.txt

# Install for development (includes test dependencies)
pip3 install -r requirements.txt
```

## Architecture Overview

This is an AI-powered transaction categorization tool for MoneyMoney on macOS. The architecture follows a multi-layer design with clear separation of concerns:

### Core Data Flow
```
MoneyMoney (AppleScript) → Transaction Data → LLM Processing → User Interaction → Category Assignment
```

### Key Components

**`categorizer.py`** - Main orchestrator that coordinates the entire workflow. Uses a command pattern with initialization, processing loop, and cleanup phases. Handles CLI arguments, statistics tracking, and dry-run mode.

**`moneymoney_client.py`** - AppleScript integration layer using subprocess calls. Handles plist-based data exchange with MoneyMoney, flattens hierarchical categories into searchable paths (e.g., "Food & Dining\Coffee"), and formats transaction data for display.

**`llm_client.py`** - LM Studio HTTP API client for AI categorization. Implements structured prompt engineering with JSON response parsing, validates suggestions against actual MoneyMoney categories using fallback matching (exact UUID → exact path → fuzzy matching).

**`category_selector.py`** - Interactive CLI interface with state machine navigation. Provides fuzzy search using fuzzywuzzy, multi-level navigation flows (suggestions → search → results), and category tree visualization.

**`config.py`** - Environment-driven configuration with sensible defaults. All settings can be overridden via environment variables.

### Integration Patterns

The application uses **adapter patterns** to normalize different external interfaces:
- AppleScript subprocess calls → Python methods
- HTTP REST API → Python methods
- Different data formats: Plist (MoneyMoney) → Python Dict → JSON (LLM) → User Interface

**Strategy pattern** for category matching with multiple fallback approaches:
1. Exact UUID match
2. Exact path match  
3. Fuzzy partial matching

### Error Handling Architecture

**Graceful degradation** - If LLM fails, continue with manual category selection
**Early exit pattern** - Fail fast if prerequisites (LM Studio connection, categories) aren't met
**Comprehensive validation** - JSON schema validation, category existence checks, transaction ID validation

## Testing Patterns

### Mock-Heavy Strategy
External dependencies (MoneyMoney, LM Studio) are extensively mocked using `unittest.mock` with `@patch` decorators. This ensures tests run without external services and are deterministic.

### Fixture-Based Testing
`conftest.py` provides reusable fixtures (`sample_transaction`, `sample_categories`, etc.) for consistent test data across test files.

### Test Organization
- Test classes mirror source code structure
- Comprehensive coverage: happy path, error scenarios, edge cases
- Setup methods ensure consistent test data initialization
- Descriptive method names indicate test intentions

### Running Specific Tests
When debugging, use specific test targeting:
```bash
# Test a specific component
python3 -m pytest tests/test_llm_client.py::TestLMStudioClient::test_parse_suggestions_valid_json -v
```

## Development Environment Setup

### Prerequisites
- macOS (required for MoneyMoney AppleScript integration)
- MoneyMoney application installed and running
- LM Studio with a loaded language model
- Python 3.9+

### Environment Variables
```bash
export LM_STUDIO_URL="http://localhost:1234/v1"  # LM Studio API endpoint
export NUM_SUGGESTIONS="5"                       # Number of AI suggestions to show
export LOG_LEVEL="DEBUG"                         # Logging verbosity
```

### Interactive vs Non-Interactive Mode
The application requires user input for category selection. In non-interactive environments (like automated testing), use `--test` mode which automatically skips one transaction and exits, or `--dry-run` mode for preview without changes.

## Code Conventions

### Error Handling
Always use graceful degradation patterns - if a component fails, allow the user to continue with reduced functionality rather than crashing.

### Logging
Each major component has its own logger. Use structured logging with consistent formatting across all components.

### Data Validation
Validate all external data (JSON from LLM, plist from MoneyMoney) before processing. Include fallback handling for malformed data.

### Testing External Dependencies
When adding new external integrations, create comprehensive mocks that cover both success and failure scenarios. Use fixtures for consistent test data.

## Development Workflow

### After Every Code Change
IMPORTANT: After completing any todo or making code changes, ALWAYS follow this sequence:

1. **Run Tests**: Execute the full test suite to ensure no regressions
   ```bash
   python3 -m pytest tests/ -v
   ```

2. **Test Application**: Run the app in test mode to verify functionality
   ```bash
   python3 categorizer.py --test
   ```

3. **Update Documentation**: Update README.md and other docs to reflect changes

This ensures code quality, functionality verification, and documentation stays current with all changes.