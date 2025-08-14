"""Parser for Adidas.com."""

import json
import re
import requests
from typing import List, Set
from .base import BaseParser, ParseResult


class AdidasParser(BaseParser):
    """Parser specifically for Adidas.com."""
    
    def can_parse(self, url: str) -> bool:
        """Check if URL is from Adidas."""
        domain = self.get_domain(url)
        adidas_domains = ['adidas.com', 'www.adidas.com', 'adidas.de', 'adidas.co.uk']
        return any(domain.endswith(d) for d in adidas_domains)
    
    def parse(self, url: str, target_sizes: List[str]) -> ParseResult:
        """Parse Adidas product page."""
        result = ParseResult(url=url)
        
        try:
            soup = self._fetch_page(url)
            if not soup:
                result.error = "Failed to fetch page"
                return result
            
            # Adidas-specific product name extraction
            result.product_name = self._extract_adidas_product_name(soup)
            result.price = self._extract_adidas_price(soup)
            
            # Check size availability
            available_sizes = self._check_adidas_sizes(soup, target_sizes)
            result.available_sizes = available_sizes
            result.in_stock = len(available_sizes) > 0
            
            result.metadata = {
                'parser': 'adidas',
                'domain': self.get_domain(url)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Adidas URL {url}: {e}")
            result.error = str(e)
        
        return result
    
    def _fetch_page(self, url: str, timeout: int = 30):
        """Fetch page using requests.get() directly for Adidas."""
        import time
        import random
        
        try:
            # Add a small random delay to be respectful
            time.sleep(random.uniform(1, 2))
            
            # Adidas-specific headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
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
    
    def _extract_adidas_product_name(self, soup) -> str:
        """Extract product name from Adidas page."""
        # Adidas-specific selectors
        selectors = [
            'h1[data-auto-id="product-title"]',
            '.product-title h1',
            '.pdp-product-name',
            'h1.name___JkMOq',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        # Fallback to generic method
        return self._extract_product_name(soup)
    
    def _extract_adidas_price(self, soup) -> str:
        """Extract price from Adidas page."""
        # Adidas-specific price selectors
        selectors = [
            '[data-auto-id="product-price"]',
            '.price .gl-price',
            '.product-price',
            '.price-wrapper .price',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                if any(symbol in price_text for symbol in ['$', '€', '£', '¥']):
                    return price_text
        
        # Fallback to generic method
        return self._extract_price(soup)
    
    def _check_adidas_sizes(self, soup, target_sizes: List[str]) -> Set[str]:
        """Check Adidas-specific size availability."""
        available_sizes = set()
        normalized_targets = {self._normalize_size(size): size for size in target_sizes}
        
        # Strategy 1: Size buttons/options
        size_elements = soup.find_all(attrs={'data-auto-id': 'size-selector-size-button'})
        for element in size_elements:
            if element.get('disabled') or 'disabled' in element.get('class', []):
                continue
            
            size_text = element.get_text(strip=True)
            if size_text:
                normalized = self._normalize_size(size_text)
                for norm_target, original_target in normalized_targets.items():
                    if norm_target in normalized or normalized in norm_target:
                        available_sizes.add(original_target)
        
        # Strategy 2: JSON data in scripts
        scripts = soup.find_all('script')
        for script in scripts:
            if not script.string:
                continue
            
            # Look for Adidas product data
            if 'window.DATA_STORE' in script.string or 'gtm.product' in script.string:
                try:
                    # Try to extract JSON data
                    json_matches = re.findall(r'({[^{}]*(?:{[^{}]*}[^{}]*)*})', script.string)
                    for json_str in json_matches:
                        try:
                            data = json.loads(json_str)
                            sizes = self._extract_sizes_from_adidas_json(data)
                            
                            for size in sizes:
                                normalized = self._normalize_size(size)
                                for norm_target, original_target in normalized_targets.items():
                                    if norm_target in normalized:
                                        available_sizes.add(original_target)
                        except json.JSONDecodeError:
                            continue
                            
                except Exception:
                    continue
        
        # Strategy 3: Size selector dropdowns
        size_selects = soup.find_all('select', attrs={'data-auto-id': re.compile(r'size', re.I)})
        for select in size_selects:
            options = select.find_all('option')
            for option in options:
                if option.get('disabled') or not option.get('value'):
                    continue
                
                size_text = option.get_text(strip=True)
                if size_text and size_text.lower() not in ['select size', 'size']:
                    normalized = self._normalize_size(size_text)
                    for norm_target, original_target in normalized_targets.items():
                        if norm_target in normalized:
                            available_sizes.add(original_target)
        
        return available_sizes
    
    def _extract_sizes_from_adidas_json(self, data) -> List[str]:
        """Extract available sizes from Adidas JSON data."""
        sizes = []
        
        def search_for_sizes(obj):
            if isinstance(obj, dict):
                # Look for size-related keys
                size_keys = ['size', 'sizes', 'availableSizes', 'variants', 'sizeOptions']
                for key in size_keys:
                    if key in obj:
                        value = obj[key]
                        if isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    # Look for size value in nested objects
                                    for size_key in ['size', 'value', 'displaySize', 'sizeValue']:
                                        if size_key in item:
                                            sizes.append(str(item[size_key]))
                                else:
                                    sizes.append(str(item))
                        elif isinstance(value, str):
                            sizes.append(value)
                
                # Look for availability info
                if 'availability' in obj and obj['availability']:
                    if 'sizes' in obj:
                        sizes.extend([str(s) for s in obj['sizes']])
                
                # Recursively search nested objects
                for value in obj.values():
                    if isinstance(value, (dict, list)):
                        search_for_sizes(value)
                        
            elif isinstance(obj, list):
                for item in obj:
                    search_for_sizes(item)
        
        search_for_sizes(data)
        return sizes
