"""Core monitoring system for marketplace sites."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from .config import Config, SiteConfig
from .parsers.registry import registry
from .parsers.base import ParseResult
from .notifications.telegram import TelegramNotifier
from .notifications.base import NotificationMessage


@dataclass
class MonitorResult:
    """Result of monitoring a single site."""
    
    site_name: str
    url: str
    success: bool
    result: Optional[ParseResult] = None
    error: Optional[str] = None
    check_time: datetime = field(default_factory=datetime.now)
    duration: float = 0.0  # seconds


@dataclass
class MonitorStats:
    """Statistics for monitoring session."""
    
    total_checks: int = 0
    successful_checks: int = 0
    failed_checks: int = 0
    sizes_found: int = 0
    notifications_sent: int = 0
    start_time: datetime = field(default_factory=datetime.now)
    last_check_time: Optional[datetime] = None


class MarketplaceMonitor:
    """Main marketplace monitoring system."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize marketplace monitor.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_manager = Config(config_path)
        self.config = self.config_manager.get()
        self.stats = MonitorStats()
        self.running = False
        self._stop_event = asyncio.Event()
        
        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger("monitor")
        
        # Initialize parsers
        self._register_parsers()
        
        # Initialize notifiers
        self.notifiers = []
        self._setup_notifiers()
        
        # Track last successful finds to avoid duplicate notifications
        self._last_finds: Dict[str, Set[str]] = {}
        
        self.logger.info("Marketplace Monitor initialized")
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def _register_parsers(self):
        """Register all available parsers."""
        # Import and register parsers
        from .parsers.generic import GenericParser
        from .parsers.nike import NikeParser
        from .parsers.adidas import AdidasParser
        from .parsers.mango import MangoParser
        
        registry.register('generic', GenericParser)
        registry.register('nike', NikeParser)
        registry.register('adidas', AdidasParser)
        registry.register('mango', MangoParser)
        
        self.logger.info(f"Registered parsers: {registry.list_parsers()}")
    
    def _setup_notifiers(self):
        """Setup notification systems."""
        notifications_config = self.config.notifications
        
        # Setup Telegram notifier
        if notifications_config.telegram and notifications_config.telegram.get('enabled'):
            try:
                telegram_notifier = TelegramNotifier(notifications_config.telegram)
                if telegram_notifier.is_enabled():
                    self.notifiers.append(telegram_notifier)
                    self.logger.info("Telegram notifier initialized")
                else:
                    self.logger.warning("Telegram notifier failed to initialize")
            except Exception as e:
                self.logger.error(f"Failed to setup Telegram notifier: {e}")
        
        self.logger.info(f"Initialized {len(self.notifiers)} notifiers")
    
    async def start_monitoring(self):
        """Start continuous monitoring of all sites."""
        if self.running:
            self.logger.warning("Monitor is already running")
            return
        
        self.running = True
        self._stop_event.clear()
        self.stats = MonitorStats()
        
        self.logger.info("Starting marketplace monitoring...")
        self.logger.info(f"Monitoring {len(self.config.sites)} sites")
        
        try:
            while self.running and not self._stop_event.is_set():
                # Run monitoring cycle
                await self._run_monitoring_cycle()
                
                # Wait for next cycle
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.config.global_check_interval
                    )
                except asyncio.TimeoutError:
                    pass  # Normal timeout, continue monitoring
                
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
        finally:
            self.running = False
            self.logger.info("Monitoring stopped")
    
    async def _run_monitoring_cycle(self):
        """Run a single monitoring cycle for all enabled sites."""
        self.logger.info("Starting monitoring cycle...")
        cycle_start = time.time()
        
        # Get enabled sites
        enabled_sites = [site for site in self.config.sites if site.enabled]
        if not enabled_sites:
            self.logger.warning("No enabled sites to monitor")
            return
        
        # Create monitoring tasks
        tasks = []
        for site in enabled_sites:
            for url in site.urls:
                task = asyncio.create_task(
                    self._monitor_single_url(site, url)
                )
                tasks.append(task)
        
        # Wait for all tasks with concurrency limit
        semaphore = asyncio.Semaphore(self.config.max_concurrent_checks)
        
        async def limited_monitor(task):
            async with semaphore:
                return await task
        
        # Execute all tasks
        results = await asyncio.gather(
            *[limited_monitor(task) for task in tasks],
            return_exceptions=True
        )
        
        # Process results
        successful_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Task error: {result}")
                self.stats.failed_checks += 1
            elif isinstance(result, MonitorResult):
                if result.success:
                    self.stats.successful_checks += 1
                    successful_results.append(result)
                else:
                    self.stats.failed_checks += 1
        
        # Send notifications for new finds
        await self._process_results_and_notify(successful_results)
        
        cycle_duration = time.time() - cycle_start
        self.stats.last_check_time = datetime.now()
        
        self.logger.info(
            f"Monitoring cycle completed in {cycle_duration:.1f}s. "
            f"Success: {len(successful_results)}, "
            f"Failed: {self.stats.failed_checks}"
        )
    
    async def _monitor_single_url(self, site: SiteConfig, url: str) -> MonitorResult:
        """Monitor a single URL for size availability.
        
        Args:
            site: Site configuration
            url: URL to monitor
            
        Returns:
            MonitorResult with check results
        """
        start_time = time.time()
        self.stats.total_checks += 1
        
        try:
            # Get appropriate parser
            parser = registry.get_parser(site.parser, {
                'user_agent': self.config.user_agent,
                'headers': site.headers,
                'cookies': site.cookies
            })
            
            if not parser:
                return MonitorResult(
                    site_name=site.name,
                    url=url,
                    success=False,
                    error=f"Parser not found: {site.parser}",
                    duration=time.time() - start_time
                )
            
            # Parse the page
            result = parser.parse(url, site.sizes)
            
            return MonitorResult(
                site_name=site.name,
                url=url,
                success=result.error is None,
                result=result,
                error=result.error,
                duration=time.time() - start_time
            )
            
        except Exception as e:
            self.logger.error(f"Error monitoring {url}: {e}")
            return MonitorResult(
                site_name=site.name,
                url=url,
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    async def _process_results_and_notify(self, results: List[MonitorResult]):
        """Process monitoring results and send notifications for new finds.
        
        Args:
            results: List of successful monitoring results
        """
        for result in results:
            if not result.result or not result.result.available_sizes:
                continue
            
            # Check if this is a new find
            url_key = result.url
            current_sizes = result.result.available_sizes
            previous_sizes = self._last_finds.get(url_key, set())
            
            # Find new sizes that weren't available before
            new_sizes = current_sizes - previous_sizes
            
            if new_sizes:
                self.logger.info(
                    f"New sizes found for {result.site_name}: "
                    f"{', '.join(new_sizes)} at {result.url}"
                )
                
                # Update stats
                self.stats.sizes_found += len(new_sizes)
                
                # Create notification message
                notification_result = result.result
                notification_result.available_sizes = new_sizes  # Only notify about new sizes
                
                # Send notifications
                await self._send_notifications(notification_result, result.site_name)
                
                # Update last finds
                self._last_finds[url_key] = current_sizes
            else:
                # Update last finds even if no new sizes (sizes might have been removed)
                self._last_finds[url_key] = current_sizes
    
    async def _send_notifications(self, result: ParseResult, site_name: str):
        """Send notifications for size availability.
        
        Args:
            result: Parse result with available sizes
            site_name: Name of the site
        """
        if not self.notifiers:
            self.logger.warning("No notifiers configured")
            return
        
        notification_tasks = []
        for notifier in self.notifiers:
            if notifier.is_enabled():
                message = notifier.create_message_from_result(result, site_name)
                task = asyncio.create_task(notifier.send_notification(message))
                notification_tasks.append(task)
        
        if notification_tasks:
            # Send all notifications concurrently
            results = await asyncio.gather(*notification_tasks, return_exceptions=True)
            
            successful_notifications = sum(1 for r in results if r is True)
            self.stats.notifications_sent += successful_notifications
            
            self.logger.info(f"Sent {successful_notifications}/{len(notification_tasks)} notifications")
    
    def stop_monitoring(self):
        """Stop the monitoring process."""
        if not self.running:
            self.logger.warning("Monitor is not running")
            return
        
        self.logger.info("Stopping monitoring...")
        self.running = False
        self._stop_event.set()
    
    async def check_single_site(self, site_name: str) -> List[MonitorResult]:
        """Check a single site manually.
        
        Args:
            site_name: Name of site to check
            
        Returns:
            List of monitoring results
        """
        site = None
        for s in self.config.sites:
            if s.name == site_name:
                site = s
                break
        
        if not site:
            raise ValueError(f"Site not found: {site_name}")
        
        results = []
        for url in site.urls:
            result = await self._monitor_single_url(site, url)
            results.append(result)
        
        return results
    
    def get_stats(self) -> MonitorStats:
        """Get monitoring statistics.
        
        Returns:
            Current monitoring statistics
        """
        return self.stats
    
    def get_config(self):
        """Get current configuration."""
        return self.config
    
    def reload_config(self):
        """Reload configuration from file."""
        self.config = self.config_manager.load()
        self._setup_notifiers()  # Reinitialize notifiers
        self.logger.info("Configuration reloaded")
    
    async def test_notifications(self):
        """Test all notification systems."""
        if not self.notifiers:
            self.logger.warning("No notifiers configured")
            return False
        
        # Create test message
        from .parsers.base import ParseResult
        test_result = ParseResult(
            url="https://example.com/test-product",
            product_name="Test Product",
            available_sizes={"US 9", "US 10"},
            price="$99.99",
            in_stock=True
        )
        
        success = True
        for notifier in self.notifiers:
            if notifier.is_enabled():
                message = notifier.create_message_from_result(test_result, "Test Site")
                result = await notifier.send_notification(message)
                if not result:
                    success = False
                self.logger.info(f"Test notification for {notifier.__class__.__name__}: {'✓' if result else '✗'}")
        
        return success
