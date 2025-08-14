"""Command-line interface for marketplace monitor."""

import asyncio
import sys
import signal
from pathlib import Path
from typing import Optional

import click
import yaml
from colorlog import ColoredFormatter

from . import __version__
from .monitor import MarketplaceMonitor
from .config import Config


def setup_colored_logging():
    """Setup colored logging for CLI."""
    import logging
    
    # Create colored formatter
    formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    # Setup handler
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    
    # Get root logger
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


@click.group()
@click.version_option(version=__version__)
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """Marketplace Monitor - Monitor marketplace sites for product availability."""
    # Setup logging
    setup_colored_logging()
    
    if verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Store config path in context
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command()
@click.pass_context
def start(ctx):
    """Start monitoring all configured sites."""
    config_path = ctx.obj.get('config_path')
    
    try:
        monitor = MarketplaceMonitor(config_path)
        
        click.echo(f"🚀 Starting Marketplace Monitor v{__version__}")
        click.echo(f"📁 Config: {monitor.config_manager.config_path}")
        click.echo(f"🏪 Sites: {len(monitor.config.sites)}")
        click.echo(f"⏱️  Interval: {monitor.config.global_check_interval}s")
        click.echo()
        
        # Setup signal handlers for graceful shutdown
        def signal_handler(signum, frame):
            click.echo("\n🛑 Received shutdown signal, stopping monitor...")
            monitor.stop_monitoring()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Start monitoring
        asyncio.run(monitor.start_monitoring())
        
    except FileNotFoundError as e:
        click.echo(f"❌ Configuration file not found: {e}", err=True)
        click.echo("💡 Use 'marketplace-monitor init' to create a configuration file")
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Failed to start monitoring: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--site', '-s', help='Check specific site only')
@click.pass_context
def check(ctx, site: Optional[str]):
    """Run a single check of all sites (or specific site)."""
    config_path = ctx.obj.get('config_path')
    
    try:
        monitor = MarketplaceMonitor(config_path)
        
        async def run_check():
            if site:
                click.echo(f"🔍 Checking site: {site}")
                results = await monitor.check_single_site(site)
            else:
                click.echo("🔍 Running single check of all sites...")
                await monitor._run_monitoring_cycle()
                results = []  # Stats are tracked in monitor
            
            # Display results
            stats = monitor.get_stats()
            click.echo()
            click.echo("📊 Results:")
            click.echo(f"  ✅ Successful checks: {stats.successful_checks}")
            click.echo(f"  ❌ Failed checks: {stats.failed_checks}")
            click.echo(f"  📦 Sizes found: {stats.sizes_found}")
            click.echo(f"  📬 Notifications sent: {stats.notifications_sent}")
            
            if site and results:
                click.echo()
                click.echo(f"📋 Results for {site}:")
                for result in results:
                    status = "✅" if result.success else "❌"
                    click.echo(f"  {status} {result.url}")
                    if result.result and result.result.available_sizes:
                        sizes = ", ".join(result.result.available_sizes)
                        click.echo(f"    👟 Available sizes: {sizes}")
                    if result.error:
                        click.echo(f"    ⚠️  Error: {result.error}")
        
        asyncio.run(run_check())
        
    except Exception as e:
        click.echo(f"❌ Check failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output configuration file path')
@click.pass_context
def init(ctx, output: Optional[str]):
    """Initialize a new configuration file."""
    config_path = ctx.obj.get('config_path')
    
    if not output:
        output = config_path or "config.yaml"
    
    output_path = Path(output)
    
    # Check if file already exists
    if output_path.exists():
        if not click.confirm(f"Configuration file {output_path} already exists. Overwrite?"):
            click.echo("❌ Cancelled")
            return
    
    try:
        config_manager = Config(str(output_path))
        example_config = config_manager.create_example_config()
        config_manager.save(example_config)
        
        click.echo(f"✅ Created configuration file: {output_path}")
        click.echo()
        click.echo("📝 Next steps:")
        click.echo("1. Edit the configuration file to add your sites and notification settings")
        click.echo("2. Set environment variables for sensitive data (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)")
        click.echo("3. Run 'marketplace-monitor test-notifications' to verify setup")
        click.echo("4. Start monitoring with 'marketplace-monitor start'")
        
    except Exception as e:
        click.echo(f"❌ Failed to create configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def test_notifications(ctx):
    """Test notification systems."""
    config_path = ctx.obj.get('config_path')
    
    try:
        monitor = MarketplaceMonitor(config_path)
        
        click.echo("📬 Testing notification systems...")
        
        async def test_notifications():
            success = await monitor.test_notifications()
            if success:
                click.echo("✅ All notifications sent successfully!")
            else:
                click.echo("❌ Some notifications failed. Check logs for details.")
                return False
            return True
        
        success = asyncio.run(test_notifications())
        if not success:
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Test failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """Show configuration and system status."""
    config_path = ctx.obj.get('config_path')
    
    try:
        monitor = MarketplaceMonitor(config_path)
        config = monitor.get_config()
        
        click.echo(f"📊 Marketplace Monitor v{__version__} Status")
        click.echo("=" * 50)
        click.echo()
        
        # Configuration info
        click.echo("⚙️  Configuration:")
        click.echo(f"  📁 Config file: {monitor.config_manager.config_path}")
        click.echo(f"  ⏱️  Check interval: {config.global_check_interval}s")
        click.echo(f"  🔄 Max concurrent: {config.max_concurrent_checks}")
        click.echo(f"  📝 Log level: {config.log_level}")
        click.echo()
        
        # Sites info
        click.echo("🏪 Sites:")
        enabled_sites = [s for s in config.sites if s.enabled]
        disabled_sites = [s for s in config.sites if not s.enabled]
        
        click.echo(f"  ✅ Enabled: {len(enabled_sites)}")
        for site in enabled_sites:
            click.echo(f"    • {site.name} ({site.parser}) - {len(site.urls)} URLs")
            sizes_text = ", ".join(site.sizes[:3])
            if len(site.sizes) > 3:
                sizes_text += f" (+{len(site.sizes) - 3} more)"
            click.echo(f"      👟 Sizes: {sizes_text}")
        
        if disabled_sites:
            click.echo(f"  ❌ Disabled: {len(disabled_sites)}")
            for site in disabled_sites:
                click.echo(f"    • {site.name}")
        click.echo()
        
        # Parsers info
        from .parsers.registry import registry
        click.echo("🔧 Available parsers:")
        for parser_name in registry.list_parsers():
            click.echo(f"  • {parser_name}")
        click.echo()
        
        # Notifications info
        click.echo("📬 Notifications:")
        if monitor.notifiers:
            for notifier in monitor.notifiers:
                status = "✅" if notifier.is_enabled() else "❌"
                click.echo(f"  {status} {notifier.__class__.__name__}")
        else:
            click.echo("  ❌ No notifiers configured")
        
    except Exception as e:
        click.echo(f"❌ Failed to get status: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--format', 'output_format', type=click.Choice(['yaml', 'json']), default='yaml')
@click.pass_context
def config(ctx, output_format: str):
    """Display current configuration."""
    config_path = ctx.obj.get('config_path')
    
    try:
        config_manager = Config(config_path)
        config_data = config_manager.get()
        
        if output_format == 'yaml':
            click.echo(yaml.dump(config_data.dict(), default_flow_style=False, indent=2))
        else:
            import json
            click.echo(json.dumps(config_data.dict(), indent=2, default=str))
            
    except Exception as e:
        click.echo(f"❌ Failed to display configuration: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point for CLI."""
    cli()


if __name__ == '__main__':
    main()
