"""Parser for Mango.com."""

import json
import re
from typing import List, Set
from .base import BaseParser, ParseResult


class MangoParser(BaseParser):
    """Parser specifically for Mango.com."""
    
    def __init__(self, site_name: str, config: dict = None):
        """Initialize Mango parser with mobile user agent to avoid bot detection."""
        super().__init__(site_name, config)
        
        # Use mobile user agent - this bypasses Mango's bot detection
        # Desktop browser headers trigger 403, but mobile works
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-de',
            'Accept-Encoding': 'gzip, deflate, br',
        })
    
    def can_parse(self, url: str) -> bool:
        """Check if URL is from Mango."""
        domain = self.get_domain(url)
        mango_domains = ['mango.com', 'shop.mango.com', 'www.mango.com']
        return any(domain.endswith(d) for d in mango_domains)
    
    def parse(self, url: str, target_sizes: List[str]) -> ParseResult:
        """Parse Mango product page."""
        result = ParseResult(url=url)
        
        try:
            soup = self._fetch_page(url)
            if not soup:
                result.error = "Failed to fetch page"
                return result
            
            # Mango-specific product name extraction
            result.product_name = self._extract_mango_product_name(soup)
            result.price = self._extract_mango_price(soup)
            
            # Check size availability
            available_sizes = self._check_mango_sizes(soup, target_sizes)
            result.available_sizes = available_sizes
            result.in_stock = len(available_sizes) > 0
            
            result.metadata = {
                'parser': 'mango',
                'domain': self.get_domain(url)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Mango URL {url}: {e}")
            result.error = str(e)
        
        return result
    
    def _fetch_page(self, url: str, timeout: int = 30):
        """Fetch page with mobile user agent (bypasses Mango's bot detection)."""
        import time
        import random
        
        try:
            # Add a small random delay to be respectful
            time.sleep(random.uniform(1, 2))
            
            # Make the request - mobile user agent should work
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            
            # Try to detect encoding
            if response.encoding is None:
                response.encoding = 'utf-8'
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'lxml')
            return soup
            
        except Exception as e:
            self.logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def _extract_mango_product_name(self, soup) -> str:
        """Extract product name from Mango page."""
        # Mango-specific selectors
        selectors = [
            'h1.product-name',
            '.product-title h1',
            '.pdp-product-name',
            'h1[data-testid="product-name"]',
            '.product-display-name h1',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        # Try to extract from JSON data
        product_data = self._extract_mango_json_data(soup)
        if product_data:
            for item in product_data:
                if isinstance(item, dict) and 'productInfo' in item:
                    product_info = item['productInfo']
                    if 'name' in product_info:
                        return product_info['name']
                    elif 'nameEn' in product_info:
                        return product_info['nameEn']
        
        # Fallback to generic method
        return self._extract_product_name(soup)
    
    def _extract_mango_price(self, soup) -> str:
        """Extract price from Mango page."""
        # Mango-specific price selectors
        selectors = [
            '.product-price .price',
            '.price-current',
            '.price-now',
            '[data-testid="price"]',
            '.product-price-current',
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                if any(symbol in price_text for symbol in ['$', '€', '£', '¥']):
                    return price_text
        
        # Try to extract from JSON data
        product_data = self._extract_mango_json_data(soup)
        if product_data:
            for item in product_data:
                if isinstance(item, dict) and 'priceInfo' in item:
                    price_info = item['priceInfo']
                    if 'price' in price_info:
                        price = price_info['price']
                        # Add currency symbol if not present
                        if isinstance(price, (int, float)):
                            return f"€{price}"
                        return str(price)
        
        # Fallback to generic method
        return self._extract_price(soup)
    
    def _check_mango_sizes(self, soup, target_sizes: List[str]) -> Set[str]:
        """Check Mango-specific size availability."""
        available_sizes = set()
        normalized_targets = {self._normalize_size(size): size for size in target_sizes}
        
        # Strategy 1: Extract from JSON data (most reliable for Mango)
        product_data = self._extract_mango_json_data(soup)
        if product_data:
            json_sizes = self._extract_sizes_from_mango_json(product_data, normalized_targets)
            available_sizes.update(json_sizes)
        
        # Strategy 2: Check HTML size buttons/elements
        html_sizes = self._check_mango_html_sizes(soup, normalized_targets)
        available_sizes.update(html_sizes)
        
        return available_sizes
    
    def _extract_mango_json_data(self, soup) -> List[dict]:
        """Extract Mango's product JSON data from script tags."""
        product_data = []
        
        scripts = soup.find_all('script')
        for script in scripts:
            if not script.string:
                continue
            
            # Look for Mango's product data patterns
            script_content = script.string.strip()
            
            # Pattern 1: self.__next_f.push with product data
            if 'self.__next_f.push' in script_content and 'productInfo' in script_content:
                try:
                    # Extract JSON from the push call
                    json_match = re.search(r'self\.__next_f\.push\(\[.*?,\s*"([^"]*(?:\\.[^"]*)*)"\s*\]\)', script_content)
                    if json_match:
                        json_str = json_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                        # Try to parse as JSON
                        try:
                            data = json.loads(json_str)
                            if isinstance(data, list):
                                product_data.extend(data)
                            elif isinstance(data, dict):
                                product_data.append(data)
                        except json.JSONDecodeError:
                            # If direct parsing fails, try to extract individual JSON objects
                            json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_str)
                            for json_obj in json_objects:
                                try:
                                    data = json.loads(json_obj)
                                    product_data.append(data)
                                except json.JSONDecodeError:
                                    continue
                except Exception as e:
                    # Use logging instead of self.logger in case logger isn't initialized yet
                    import logging
                    logging.getLogger("parser.mango").debug(f"Failed to parse Mango JSON data: {e}")
                    continue
            
            # Pattern 2: Direct JSON objects with productInfo
            elif 'productInfo' in script_content and '{' in script_content:
                try:
                    json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', script_content)
                    for json_obj in json_objects:
                        if 'productInfo' in json_obj:
                            try:
                                data = json.loads(json_obj)
                                product_data.append(data)
                            except json.JSONDecodeError:
                                continue
                except Exception:
                    continue
        
        return product_data
    
    def _extract_sizes_from_mango_json(self, product_data: List[dict], normalized_targets: dict) -> Set[str]:
        """Extract available sizes from Mango's JSON data."""
        available_sizes = set()
        
        for item in product_data:
            if not isinstance(item, dict):
                continue
            
            # Look for productInfo with colors and sizes
            if 'productInfo' in item:
                product_info = item['productInfo']
                if 'colors' in product_info:
                    colors = product_info['colors']
                    if isinstance(colors, list):
                        for color in colors:
                            if isinstance(color, dict) and 'sizes' in color:
                                sizes = color['sizes']
                                if isinstance(sizes, list):
                                    for size_info in sizes:
                                        if isinstance(size_info, dict):
                                            # Get size label or shortDescription
                                            size_label = size_info.get('label', size_info.get('shortDescription', ''))
                                            if size_label:
                                                normalized = self._normalize_size(size_label)
                                                for norm_target, original_target in normalized_targets.items():
                                                    if norm_target == normalized or norm_target in normalized:
                                                        available_sizes.add(original_target)
            
            # Also check direct sizes array if present
            if 'sizes' in item:
                sizes = item['sizes']
                if isinstance(sizes, list):
                    for size_info in sizes:
                        if isinstance(size_info, dict):
                            size_label = size_info.get('label', size_info.get('shortDescription', ''))
                            if size_label:
                                normalized = self._normalize_size(size_label)
                                for norm_target, original_target in normalized_targets.items():
                                    if norm_target == normalized or norm_target in normalized:
                                        available_sizes.add(original_target)
        
        return available_sizes
    
    def _check_mango_html_sizes(self, soup, normalized_targets: dict) -> Set[str]:
        """Check Mango size availability from HTML elements."""
        available_sizes = set()
        
        # Strategy 1: Size buttons with specific classes
        size_buttons = soup.find_all('button', class_=re.compile(r'size', re.I))
        for button in size_buttons:
            if self._is_mango_size_unavailable(button):
                continue
            
            size_text = button.get_text(strip=True)
            if size_text:
                normalized = self._normalize_size(size_text)
                for norm_target, original_target in normalized_targets.items():
                    if norm_target == normalized or norm_target in normalized:
                        available_sizes.add(original_target)
        
        # Strategy 2: Size list items
        size_items = soup.find_all('li', class_=re.compile(r'size', re.I))
        for item in size_items:
            if self._is_mango_size_unavailable(item):
                continue
            
            # Look for size text in spans or direct text
            size_spans = item.find_all('span')
            for span in size_spans:
                size_text = span.get_text(strip=True)
                if size_text and len(size_text) <= 5:  # Size labels are typically short
                    normalized = self._normalize_size(size_text)
                    for norm_target, original_target in normalized_targets.items():
                        if norm_target == normalized or norm_target in normalized:
                            available_sizes.add(original_target)
        
        # Strategy 3: Generic size selectors
        size_elements = soup.find_all(['button', 'span', 'div'], 
                                    string=lambda text: text and any(
                                        target in str(text).upper() 
                                        for target in normalized_targets.keys()
                                    ))
        
        for element in size_elements:
            if self._is_mango_size_unavailable(element):
                continue
            
            size_text = element.get_text(strip=True)
            normalized = self._normalize_size(size_text)
            for norm_target, original_target in normalized_targets.items():
                if norm_target == normalized or norm_target in normalized:
                    available_sizes.add(original_target)
        
        return available_sizes
    
    def _is_mango_size_unavailable(self, element) -> bool:
        """Check if a Mango size element indicates the size is unavailable."""
        # Check standard unavailability indicators
        if self._is_size_unavailable(element):
            return True
        
        # Mango-specific unavailability indicators
        text = element.get_text(strip=True).lower()
        
        # German indicators
        unavailable_texts = [
            'ich will es',  # "I want it!" - indicates not available
            'nicht verfügbar',  # "not available"
            'ausverkauft',  # "sold out"
            'nur wenige',  # "only few" - might be considered unavailable depending on requirements
        ]
        
        # English indicators
        unavailable_texts.extend([
            'i want it',
            'not available',
            'sold out',
            'out of stock',
            'notify me',
        ])
        
        # Check if any unavailable text is present
        for unavailable_text in unavailable_texts:
            if unavailable_text in text:
                # For "nur wenige" / "only few", we might want to consider it available
                # but with low stock. For now, let's treat it as available.
                if 'nur wenige' in text or 'only few' in text:
                    continue
                return True
        
        # Check for specific Mango classes that indicate unavailability
        classes = element.get('class', [])
        unavailable_classes = [
            'notavailable',
            'not-available', 
            'sold-out',
            'soldout',
            'unavailable',
            'disabled',
        ]
        
        class_string = ' '.join(classes).lower()
        for unavailable_class in unavailable_classes:
            if unavailable_class in class_string:
                return True
        
        # Check parent elements for unavailability indicators
        parent = element.parent
        if parent:
            parent_text = parent.get_text(strip=True).lower()
            for unavailable_text in unavailable_texts:
                if unavailable_text in parent_text:
                    if 'nur wenige' in parent_text or 'only few' in parent_text:
                        continue
                    return True
        
        return False
    
    def _normalize_size(self, size: str) -> str:
        """Normalize size string for Mango-specific comparison."""
        normalized = BaseParser._normalize_size(self, size)
        
        # Mango-specific normalizations
        mango_mappings = {
            'EINHEITSGRÖSSE': 'U',  # German with umlaut
            'ONE SIZE': 'U',
            'UNICA': 'U',
        }
        
        for old, new in mango_mappings.items():
            normalized = normalized.replace(old, new)
        
        return normalized
