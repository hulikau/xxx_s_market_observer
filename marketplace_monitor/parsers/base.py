"""Base parser class for marketplace sites."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup


@dataclass
class ParseResult:
    """Result of parsing a product page."""
    
    url: str
    product_name: Optional[str] = None
    available_sizes: Set[str] = field(default_factory=set)
    price: Optional[str] = None
    in_stock: bool = False
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """Base class for all site parsers."""
    
    def __init__(self, site_name: str, config: Dict[str, Any] = None):
        """Initialize parser.
        
        Args:
            site_name: Name of the site this parser handles
            config: Parser-specific configuration
        """
        self.site_name = site_name
        self.config = config or {}
        self.logger = logging.getLogger(f"parser.{site_name}")
        
        # Default request settings
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.config.get(
                'user_agent',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
        })
        
        # Add custom headers if provided
        if 'headers' in self.config and self.config['headers'] is not None:
            self.session.headers.update(self.config['headers'])
        
        # Add cookies if provided
        if 'cookies' in self.config and self.config['cookies'] is not None:
            self.session.cookies.update(self.config['cookies'])
    
    @abstractmethod
    def can_parse(self, url: str) -> bool:
        """Check if this parser can handle the given URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if this parser can handle the URL
        """
        pass
    
    @abstractmethod
    def parse(self, url: str, target_sizes: List[str]) -> ParseResult:
        """Parse a product page and check for size availability.
        
        Args:
            url: Product page URL
            target_sizes: List of sizes to check for
            
        Returns:
            ParseResult with availability information
        """
        pass
    
    def _fetch_page(self, url: str, timeout: int = 30) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page.
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            
        Returns:
            BeautifulSoup object or None if failed
        """
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            # Try to detect encoding
            if response.encoding is None:
                response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'lxml')
            return soup
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to parse {url}: {e}")
            return None
    
    def _normalize_size(self, size: str) -> str:
        """Normalize size string for comparison.
        
        Args:
            size: Raw size string
            
        Returns:
            Normalized size string
        """
        if not size:
            return ""
        
        # Convert to string and strip whitespace
        normalized = str(size).strip().upper()
        
        # Common normalizations
        size_mappings = {
            # US sizes
            'US': '',
            'US ': '',
            # EU sizes
            'EU': '',
            'EU ': '',
            # UK sizes
            'UK': '',
            'UK ': '',
            # Remove extra spaces
            '  ': ' ',
        }
        
        for old, new in size_mappings.items():
            normalized = normalized.replace(old, new)
        
        return normalized.strip()
    
    def _extract_product_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract product name from page.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Product name or None
        """
        # Common selectors for product names
        selectors = [
            'h1[data-testid="product-title"]',
            'h1.product-title',
            'h1.pdp-product-name',
            '.product-name h1',
            '.product-title',
            'h1',
            '[data-testid="product-name"]',
            '.product-display-name',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text(strip=True)
                if name and len(name) > 3:  # Reasonable product name length
                    return name
        
        # Fallback to title tag
        title = soup.find('title')
        if title:
            return title.get_text(strip=True)
        
        return None
    
    def _extract_price(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract price from page.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Price string or None
        """
        # Common selectors for prices
        selectors = [
            '.price',
            '.product-price',
            '[data-testid="price"]',
            '.current-price',
            '.sale-price',
            '.price-current',
            '.price-now',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                price = element.get_text(strip=True)
                if price and ('$' in price or '€' in price or '£' in price or '¥' in price):
                    return price
        
        return None
    
    def _check_size_availability(self, soup: BeautifulSoup, target_sizes: List[str]) -> Set[str]:
        """Check which target sizes are available.
        
        Args:
            soup: BeautifulSoup object
            target_sizes: List of sizes to check for
            
        Returns:
            Set of available sizes from the target list
        """
        available_sizes = set()
        normalized_targets = {self._normalize_size(size): size for size in target_sizes}
        
        # This is a generic implementation - specific parsers should override
        size_elements = soup.find_all(['option', 'button', 'span', 'div'], 
                                    string=lambda text: text and any(
                                        target in str(text).upper() 
                                        for target in normalized_targets.keys()
                                    ))
        
        for element in size_elements:
            text = element.get_text(strip=True)
            normalized = self._normalize_size(text)
            
            for norm_target, original_target in normalized_targets.items():
                if norm_target in normalized or normalized in norm_target:
                    # Check if size is actually available (not disabled/sold out)
                    if not self._is_size_unavailable(element):
                        available_sizes.add(original_target)
        
        return available_sizes
    
    def _is_size_unavailable(self, element) -> bool:
        """Check if a size element indicates the size is unavailable.
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            True if size appears to be unavailable
        """
        # Check for disabled attribute
        if element.get('disabled'):
            return True
        
        # Check for common unavailable classes
        classes = element.get('class', [])
        unavailable_classes = ['disabled', 'sold-out', 'unavailable', 'out-of-stock']
        if any(cls in ' '.join(classes).lower() for cls in unavailable_classes):
            return True
        
        # Check parent elements for unavailable indicators
        parent = element.parent
        if parent:
            parent_classes = parent.get('class', [])
            if any(cls in ' '.join(parent_classes).lower() for cls in unavailable_classes):
                return True
        
        return False
    
    def get_domain(self, url: str) -> str:
        """Extract domain from URL.
        
        Args:
            url: URL to parse
            
        Returns:
            Domain name
        """
        return urlparse(url).netloc.lower()
