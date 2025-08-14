"""Generic parser that works with many e-commerce sites."""

import re
import requests
from typing import List, Set
from .base import BaseParser, ParseResult


class GenericParser(BaseParser):
    """Generic parser for common e-commerce sites."""
    
    def __init__(self, site_name: str, config: dict = None):
        """Initialize generic parser."""
        super().__init__(site_name, config)
        
        # Common size patterns
        self.size_patterns = [
            r'\b(US\s*)?(\d+(?:\.\d+)?)\b',  # US sizes like "US 9", "9.5"
            r'\b(EU\s*)?(\d{2}(?:\.\d+)?)\b',  # EU sizes like "EU 42", "42.5"
            r'\b(UK\s*)?(\d+(?:\.\d+)?)\b',  # UK sizes
            r'\b([XS|S|M|L|XL|XXL|XXXL]+)\b',  # Clothing sizes
        ]
    
    def can_parse(self, url: str) -> bool:
        """Generic parser can attempt to parse any URL."""
        # Generic parser is a fallback, so it accepts any URL
        # In practice, you might want to check for specific patterns
        return True
    
    def parse(self, url: str, target_sizes: List[str]) -> ParseResult:
        """Parse a product page using generic selectors."""
        result = ParseResult(url=url)
        
        try:
            soup = self._fetch_page(url)
            if not soup:
                result.error = "Failed to fetch page"
                return result
            
            # Extract product information
            result.product_name = self._extract_product_name(soup)
            result.price = self._extract_price(soup)
            
            # Check size availability using multiple strategies
            available_sizes = self._check_size_availability_comprehensive(soup, target_sizes)
            result.available_sizes = available_sizes
            result.in_stock = len(available_sizes) > 0
            
            # Add metadata
            result.metadata = {
                'parser': 'generic',
                'domain': self.get_domain(url),
                'total_sizes_found': len(self._find_all_sizes(soup))
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing {url}: {e}")
            result.error = str(e)
        
        return result
    
    def _fetch_page(self, url: str, timeout: int = 30):
        """Fetch page using requests.get() directly for generic sites."""
        import time
        import random
        
        try:
            # Add a small random delay to be respectful
            time.sleep(random.uniform(1, 2))
            
            # Generic headers that work with most sites
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # Make the request using requests.get() directly
            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            
            # Get raw HTML text
            html_text = response.text
            
            # Parse HTML text with BeautifulSoup
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, 'html.parser')
            return soup
            
        except Exception as e:
            self.logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def _check_size_availability_comprehensive(self, soup, target_sizes: List[str]) -> Set[str]:
        """Comprehensive size availability check using multiple strategies."""
        available_sizes = set()
        
        # Strategy 1: Standard size selectors
        available_sizes.update(self._check_size_availability(soup, target_sizes))
        
        # Strategy 2: JSON-LD structured data
        available_sizes.update(self._check_sizes_in_json_ld(soup, target_sizes))
        
        # Strategy 3: JavaScript variables
        available_sizes.update(self._check_sizes_in_scripts(soup, target_sizes))
        
        # Strategy 4: Form selects and options
        available_sizes.update(self._check_sizes_in_selects(soup, target_sizes))
        
        # Strategy 5: Button/link patterns
        available_sizes.update(self._check_sizes_in_buttons(soup, target_sizes))
        
        return available_sizes
    
    def _find_all_sizes(self, soup) -> Set[str]:
        """Find all possible sizes on the page."""
        sizes = set()
        
        # Look for size-related elements
        size_selectors = [
            '[data-size]',
            '.size-option',
            '.size-selector',
            '.size-button',
            'select[name*="size"] option',
            'button[data-value*="size"]',
        ]
        
        for selector in size_selectors:
            elements = soup.select(selector)
            for element in elements:
                # Extract size from various attributes
                size_attrs = ['data-size', 'data-value', 'value', 'title']
                for attr in size_attrs:
                    size_value = element.get(attr)
                    if size_value:
                        sizes.add(str(size_value).strip())
                
                # Also check text content
                text = element.get_text(strip=True)
                if text and len(text) < 10:  # Reasonable size text length
                    sizes.add(text)
        
        return sizes
    
    def _check_sizes_in_json_ld(self, soup, target_sizes: List[str]) -> Set[str]:
        """Check for sizes in JSON-LD structured data."""
        available_sizes = set()
        normalized_targets = {self._normalize_size(size): size for size in target_sizes}
        
        # Find JSON-LD scripts
        json_scripts = soup.find_all('script', type='application/ld+json')
        
        for script in json_scripts:
            try:
                import json
                data = json.loads(script.string)
                
                # Look for size information in various JSON-LD structures
                sizes = self._extract_sizes_from_json(data)
                
                for size in sizes:
                    normalized = self._normalize_size(size)
                    for norm_target, original_target in normalized_targets.items():
                        if norm_target in normalized or normalized in norm_target:
                            available_sizes.add(original_target)
                            
            except (json.JSONDecodeError, AttributeError):
                continue
        
        return available_sizes
    
    def _extract_sizes_from_json(self, data) -> List[str]:
        """Extract sizes from JSON data recursively."""
        sizes = []
        
        if isinstance(data, dict):
            # Look for common size keys
            size_keys = ['size', 'sizes', 'availableSizes', 'variants', 'options']
            for key in size_keys:
                if key in data:
                    value = data[key]
                    if isinstance(value, list):
                        sizes.extend([str(v) for v in value])
                    elif isinstance(value, str):
                        sizes.append(value)
            
            # Recurse into nested objects
            for value in data.values():
                if isinstance(value, (dict, list)):
                    sizes.extend(self._extract_sizes_from_json(value))
                    
        elif isinstance(data, list):
            for item in data:
                sizes.extend(self._extract_sizes_from_json(item))
        
        return sizes
    
    def _check_sizes_in_scripts(self, soup, target_sizes: List[str]) -> Set[str]:
        """Check for sizes in JavaScript variables."""
        available_sizes = set()
        normalized_targets = {self._normalize_size(size): size for size in target_sizes}
        
        scripts = soup.find_all('script')
        
        for script in scripts:
            if not script.string:
                continue
            
            # Look for common JavaScript patterns
            patterns = [
                r'sizes?\s*[:=]\s*\[(.*?)\]',
                r'availableSizes?\s*[:=]\s*\[(.*?)\]',
                r'variants?\s*[:=]\s*\[(.*?)\]',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, script.string, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    # Extract quoted strings from the match
                    size_matches = re.findall(r'["\']([^"\']+)["\']', match)
                    for size in size_matches:
                        normalized = self._normalize_size(size)
                        for norm_target, original_target in normalized_targets.items():
                            if norm_target in normalized or normalized in norm_target:
                                available_sizes.add(original_target)
        
        return available_sizes
    
    def _check_sizes_in_selects(self, soup, target_sizes: List[str]) -> Set[str]:
        """Check for sizes in select dropdowns."""
        available_sizes = set()
        normalized_targets = {self._normalize_size(size): size for size in target_sizes}
        
        # Find select elements that might contain sizes
        selects = soup.find_all('select')
        
        for select in selects:
            # Check if this select is size-related
            select_attrs = str(select.get('name', '')) + str(select.get('id', ''))
            if 'size' in select_attrs.lower():
                options = select.find_all('option')
                for option in options:
                    if option.get('disabled'):
                        continue
                    
                    option_text = option.get_text(strip=True)
                    option_value = option.get('value', '')
                    
                    for text in [option_text, option_value]:
                        if text:
                            normalized = self._normalize_size(text)
                            for norm_target, original_target in normalized_targets.items():
                                if norm_target in normalized or normalized in norm_target:
                                    available_sizes.add(original_target)
        
        return available_sizes
    
    def _check_sizes_in_buttons(self, soup, target_sizes: List[str]) -> Set[str]:
        """Check for sizes in buttons and clickable elements."""
        available_sizes = set()
        normalized_targets = {self._normalize_size(size): size for size in target_sizes}
        
        # Find buttons that might be size selectors
        buttons = soup.find_all(['button', 'a', 'span'], class_=re.compile(r'size', re.I))
        
        for button in buttons:
            if self._is_size_unavailable(button):
                continue
            
            button_text = button.get_text(strip=True)
            button_attrs = ' '.join([
                str(button.get('data-size', '')),
                str(button.get('data-value', '')),
                str(button.get('title', '')),
            ])
            
            for text in [button_text, button_attrs]:
                if text:
                    normalized = self._normalize_size(text)
                    for norm_target, original_target in normalized_targets.items():
                        if norm_target in normalized or normalized in norm_target:
                            available_sizes.add(original_target)
        
        return available_sizes
