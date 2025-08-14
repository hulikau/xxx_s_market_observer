"""Parser for Nike.com."""

import json
import re
from typing import List, Set
from .base import BaseParser, ParseResult


class NikeParser(BaseParser):
    """Parser specifically for Nike.com."""
    
    def can_parse(self, url: str) -> bool:
        """Check if URL is from Nike."""
        domain = self.get_domain(url)
        nike_domains = ['nike.com', 'www.nike.com']
        return any(domain.endswith(d) for d in nike_domains)
    
    def parse(self, url: str, target_sizes: List[str]) -> ParseResult:
        """Parse Nike product page."""
        result = ParseResult(url=url)
        
        try:
            soup = self._fetch_page(url)
            if not soup:
                result.error = "Failed to fetch page"
                return result
            
            # Nike-specific product name extraction
            result.product_name = self._extract_nike_product_name(soup)
            result.price = self._extract_nike_price(soup)
            
            # Check size availability
            available_sizes = self._check_nike_sizes(soup, target_sizes)
            result.available_sizes = available_sizes
            result.in_stock = len(available_sizes) > 0
            
            result.metadata = {
                'parser': 'nike',
                'domain': self.get_domain(url)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Nike URL {url}: {e}")
            result.error = str(e)
        
        return result
    
    def _extract_nike_product_name(self, soup) -> str:
        """Extract product name from Nike page."""
        # Nike-specific selectors
        selectors = [
            'h1[data-testid="product-title"]',
            '#pdp_product_title',
            '.pdp-product-name-title',
            '.product-title h1',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        # Fallback to generic method
        return self._extract_product_name(soup)
    
    def _extract_nike_price(self, soup) -> str:
        """Extract price from Nike page."""
        # Nike-specific price selectors
        selectors = [
            '[data-testid="product-price"]',
            '.product-price .sr-only',
            '.product-price',
            '.price-wrapper .price',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                if '$' in price_text or '€' in price_text or '£' in price_text:
                    return price_text
        
        # Fallback to generic method
        return self._extract_price(soup)
    
    def _check_nike_sizes(self, soup, target_sizes: List[str]) -> Set[str]:
        """Check Nike-specific size availability."""
        available_sizes = set()
        normalized_targets = {self._normalize_size(size): size for size in target_sizes}
        
        # Strategy 1: Nike size buttons
        size_buttons = soup.find_all('input', {'name': 'skuAndSize'})
        for button in size_buttons:
            if button.get('disabled'):
                continue
            
            # Get size from label
            label_id = button.get('id', '')
            if label_id:
                label = soup.find('label', {'for': label_id})
                if label:
                    size_text = label.get_text(strip=True)
                    normalized = self._normalize_size(size_text)
                    
                    for norm_target, original_target in normalized_targets.items():
                        if norm_target in normalized:
                            available_sizes.add(original_target)
        
        # Strategy 2: JSON data in scripts
        scripts = soup.find_all('script')
        for script in scripts:
            if not script.string:
                continue
            
            # Look for Nike's product data
            if 'INITIAL_REDUX_STATE' in script.string or 'window.NIKE_REDUX_STATE' in script.string:
                try:
                    # Extract JSON data
                    json_match = re.search(r'({.*})', script.string, re.DOTALL)
                    if json_match:
                        data = json.loads(json_match.group(1))
                        sizes = self._extract_sizes_from_nike_json(data)
                        
                        for size in sizes:
                            normalized = self._normalize_size(size)
                            for norm_target, original_target in normalized_targets.items():
                                if norm_target in normalized:
                                    available_sizes.add(original_target)
                                    
                except (json.JSONDecodeError, AttributeError):
                    continue
        
        # Strategy 3: Size selector elements
        size_elements = soup.find_all(attrs={'data-qa': re.compile(r'size', re.I)})
        for element in size_elements:
            if 'disabled' in element.get('class', []) or element.get('disabled'):
                continue
            
            size_text = element.get_text(strip=True)
            if size_text:
                normalized = self._normalize_size(size_text)
                for norm_target, original_target in normalized_targets.items():
                    if norm_target in normalized:
                        available_sizes.add(original_target)
        
        return available_sizes
    
    def _extract_sizes_from_nike_json(self, data) -> List[str]:
        """Extract available sizes from Nike's JSON data."""
        sizes = []
        
        def search_for_sizes(obj):
            if isinstance(obj, dict):
                # Look for size-related keys
                if 'availableSkus' in obj:
                    skus = obj['availableSkus']
                    if isinstance(skus, list):
                        for sku in skus:
                            if isinstance(sku, dict) and 'localizedSize' in sku:
                                sizes.append(sku['localizedSize'])
                
                if 'skus' in obj:
                    skus = obj['skus']
                    if isinstance(skus, list):
                        for sku in skus:
                            if isinstance(sku, dict):
                                if 'localizedSize' in sku and sku.get('available', False):
                                    sizes.append(sku['localizedSize'])
                                elif 'nikeSize' in sku and sku.get('available', False):
                                    sizes.append(sku['nikeSize'])
                
                # Recursively search nested objects
                for value in obj.values():
                    if isinstance(value, (dict, list)):
                        search_for_sizes(value)
                        
            elif isinstance(obj, list):
                for item in obj:
                    search_for_sizes(item)
        
        search_for_sizes(data)
        return sizes
