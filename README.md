# Marketplace Monitor

A powerful Python tool to monitor marketplace sites for product availability and get notified when your desired sizes are in stock.

## Features

- 🏪 **Multi-site support**: Monitor multiple marketplace sites simultaneously
- 🔧 **Configurable parsers**: Extensible parser system for different sites
- 👟 **Size tracking**: Monitor specific sizes across different sizing systems (US, EU, UK)
- 📱 **Telegram notifications**: Get instant notifications when sizes become available
- ⚙️ **Flexible configuration**: YAML-based configuration with environment variable support
- 🚀 **Easy installation**: Install as a Python package with CLI interface
- 📊 **Monitoring stats**: Track success rates and notification history
- 🔄 **Concurrent monitoring**: Efficient multi-threaded checking
- 🛡️ **Error handling**: Robust error handling and retry mechanisms

## Installation

### From Source

```bash
git clone <repository-url>
cd marketplace-monitor
pip install -e .
```

### Requirements

- Python 3.8+
- pip

## Quick Start

### 1. Initialize Configuration

```bash
marketplace-monitor init
```

This creates a `config.yaml` file with example configuration.

### 2. Configure Your Sites

Edit `config.yaml` to add the sites and products you want to monitor:

```yaml
sites:
  - name: "Nike Store"
    parser: "nike"
    urls:
      - "https://www.nike.com/t/air-jordan-1-retro-high-og-shoe-DZ5485-612"
    sizes:
      - "US 9"
      - "US 10"
      - "US 11"
    check_interval: 300
    enabled: true

  - name: "Generic Store"
    parser: "generic"
    urls:
      - "https://example-store.com/product/sneakers"
    sizes:
      - "42"
      - "43"
      - "44"
    check_interval: 600
    enabled: true
```

### 3. Set Up Notifications

#### Telegram Setup

1. Create a Telegram bot:
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Use `/newbot` command and follow instructions
   - Save the bot token

2. Get your chat ID:
   - Start a conversation with your bot
   - Send any message
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response

3. Set environment variables:
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
export TELEGRAM_CHAT_ID="your_chat_id_here"
```

Or create a `.env` file:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 4. Test Your Setup

```bash
# Test notifications
marketplace-monitor test-notifications

# Check configuration
marketplace-monitor status

# Run a single check
marketplace-monitor check
```

### 5. Start Monitoring

```bash
marketplace-monitor start
```

## CLI Commands

### `marketplace-monitor start`
Start continuous monitoring of all configured sites.

### `marketplace-monitor check [--site SITE_NAME]`
Run a single check of all sites or a specific site.

### `marketplace-monitor init [--output CONFIG_FILE]`
Initialize a new configuration file.

### `marketplace-monitor test-notifications`
Test all configured notification systems.

### `marketplace-monitor status`
Show configuration and system status.

### `marketplace-monitor config [--format yaml|json]`
Display current configuration.

## Configuration

### Site Configuration

```yaml
sites:
  - name: "Site Name"           # Display name for the site
    parser: "parser_name"       # Parser to use (generic, nike, etc.)
    urls:                       # List of URLs to monitor
      - "https://example.com/product1"
      - "https://example.com/product2"
    sizes:                      # Sizes to monitor for
      - "US 9"
      - "US 10"
      - "42"
    check_interval: 300         # Check interval in seconds (min: 60)
    enabled: true               # Whether to monitor this site
    headers:                    # Optional custom headers
      "User-Agent": "Custom User Agent"
    cookies:                    # Optional custom cookies
      "session": "value"
```

### Global Settings

```yaml
global_check_interval: 300      # Default check interval (seconds)
max_concurrent_checks: 5        # Maximum concurrent site checks
user_agent: "Mozilla/5.0 ..."   # Default user agent
timeout: 30                     # Request timeout (seconds)
retry_attempts: 3               # Number of retry attempts
log_level: "INFO"              # Logging level
```

### Notification Settings

```yaml
notifications:
  telegram:
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
    enabled: true
```

## Available Parsers

### Generic Parser (`generic`)
Works with most e-commerce sites using common patterns and selectors. This is the fallback parser that attempts to find size information using multiple strategies.

### Nike Parser (`nike`)
Specialized parser for Nike.com with Nike-specific selectors and JSON data extraction.

### Creating Custom Parsers

You can create custom parsers by extending the `BaseParser` class:

```python
from marketplace_monitor.parsers.base import BaseParser, ParseResult

class MyStoreParser(BaseParser):
    def can_parse(self, url: str) -> bool:
        return "mystore.com" in url
    
    def parse(self, url: str, target_sizes: List[str]) -> ParseResult:
        # Your parsing logic here
        pass

# Register the parser
from marketplace_monitor.parsers.registry import registry
registry.register('mystore', MyStoreParser)
```

## Environment Variables

- `TELEGRAM_BOT_TOKEN`: Telegram bot token for notifications
- `TELEGRAM_CHAT_ID`: Telegram chat ID for notifications

## Logging

The tool uses structured logging with different levels:

- `DEBUG`: Detailed debugging information
- `INFO`: General information about monitoring activities
- `WARNING`: Warning messages for non-critical issues
- `ERROR`: Error messages for failures

Use `--verbose` flag to enable debug logging:

```bash
marketplace-monitor --verbose start
```

## Troubleshooting

### Common Issues

1. **"Configuration file not found"**
   - Run `marketplace-monitor init` to create a configuration file
   - Use `--config` flag to specify a custom config file path

2. **"Parser not found"**
   - Check that the parser name in your config matches available parsers
   - Use `marketplace-monitor status` to see available parsers

3. **"Telegram notifications not working"**
   - Verify your bot token and chat ID are correct
   - Test with `marketplace-monitor test-notifications`
   - Check that environment variables are set

4. **"Sites not being checked"**
   - Ensure sites are enabled in configuration
   - Check that URLs are accessible
   - Review logs for error messages

### Debug Mode

Enable verbose logging to see detailed information:

```bash
marketplace-monitor --verbose start
```

## Development

### Setting Up Development Environment

```bash
git clone <repository-url>
cd marketplace-monitor
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black marketplace_monitor/
flake8 marketplace_monitor/
mypy marketplace_monitor/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

- Create an issue on GitHub for bug reports or feature requests
- Check the logs for debugging information
- Use `marketplace-monitor status` to verify your configuration
