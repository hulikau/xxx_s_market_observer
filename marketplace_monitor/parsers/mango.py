"""Parser for Mango.com."""

import json
import re
import requests
from typing import List, Set, Optional, Dict
from .base import BaseParser, ParseResult


class MangoParser(BaseParser):
    """Parser specifically for Mango.com."""
    
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
            
            # Log extracted product information
            if result.product_name:
                self.logger.info(f"📦 Product: {result.product_name}")
            if result.price:
                self.logger.info(f"💰 Price: {result.price}")
            
            # Check size availability
            available_sizes = self._check_mango_sizes(soup, target_sizes)
            result.available_sizes = available_sizes
            result.in_stock = len(available_sizes) > 0
            
            # Log size detection results
            if available_sizes:
                self.logger.info(f"✅ Found {len(available_sizes)} available sizes: {', '.join(sorted(available_sizes))}")
            else:
                self.logger.info(f"❌ No target sizes found. Target sizes were: {', '.join(target_sizes)}")
            
            result.metadata = {
                'parser': 'mango',
                'domain': self.get_domain(url)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Mango URL {url}: {e}")
            result.error = str(e)
        
        return result
    
    def _fetch_page(self, url: str, timeout: int = 30):
        """Fetch page using requests.get() directly."""
        import time
        import random
        
        try:
            # Add a small random delay to be respectful
            time.sleep(random.uniform(1, 2))
            
            # Use mobile user agent headers to bypass bot detection
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'de-de',
                'Accept-Encoding': 'gzip, deflate, br',
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
        
        self.logger.debug(f"🔍 Looking for sizes: {target_sizes}")
        self.logger.debug(f"🔍 Normalized targets: {normalized_targets}")
        
        # Strategy 1: Extract from JSON data (most reliable for Mango)
        product_data = self._extract_mango_json_data(soup)
        if product_data:
            self.logger.debug(f"📊 Found {len(product_data)} JSON product data objects")
            json_sizes = self._extract_sizes_from_mango_json(product_data, normalized_targets)
            if json_sizes:
                self.logger.info(f"📊 JSON data found sizes: {', '.join(sorted(json_sizes))}")
            else:
                self.logger.debug("📊 No sizes found in JSON data")
            available_sizes.update(json_sizes)
        else:
            self.logger.debug("📊 No JSON product data found")
        
        # Strategy 2: Check HTML size buttons/elements
        html_sizes = self._check_mango_html_sizes(soup, normalized_targets)
        if html_sizes:
            self.logger.info(f"🌐 HTML elements found sizes: {', '.join(sorted(html_sizes))}")
        else:
            self.logger.debug("🌐 No sizes found in HTML elements")
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
            if 'self.__next_f.push' in script_content and ('productInfo' in script_content or 'product' in script_content or 'reference' in script_content):
                try:
                    # Extract JSON from the push call
                    json_match = re.search(r'self\.__next_f\.push\(\[.*?,\s*"([^"]*(?:\\.[^"]*)*)"\s*\]\)', script_content)
                    if json_match:
                        json_str = json_match.group(1).replace('\\"', '"').replace('\\\\', '\\')
                        
                        # Try Next.js specific parsing first
                        nextjs_data = self._parse_nextjs_product_data(json_str)
                        if nextjs_data:
                            product_data.append(nextjs_data)
                        
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
    
    def _parse_nextjs_product_data(self, data_string: str) -> Optional[Dict]:
        """Parse product data from Next.js streaming content."""
        try:
            # Look for product reference pattern
            if '"reference":"87007197"' in data_string or '"name":"Kombiniertes' in data_string:
                self.logger.debug("Found product reference in Next.js data")
                
                # Extract size-related data patterns
                size_patterns = {
                    'sizes': re.findall(r'"sizes?":\s*\[([^\]]*)\]', data_string, re.IGNORECASE),
                    'variants': re.findall(r'"variants?":\s*\[([^\]]*)\]', data_string, re.IGNORECASE),
                    'stock': re.findall(r'"stock":\s*(\w+)', data_string, re.IGNORECASE),
                    'available': re.findall(r'"available":\s*(true|false)', data_string, re.IGNORECASE),
                }
                
                # Look for individual size entries
                size_entries = re.findall(r'"([XSMLXL]+)":\s*{[^}]*"available":\s*(true|false)', data_string)
                
                if any(size_patterns.values()) or size_entries:
                    result = {
                        'source': 'nextjs_stream',
                        'patterns': size_patterns,
                        'size_entries': size_entries,
                        'raw_excerpt': data_string[:500] if len(data_string) > 500 else data_string
                    }
                    self.logger.debug(f"Extracted Next.js product data: {len(size_entries)} size entries")
                    return result
                    
        except Exception as e:
            self.logger.debug(f"Error parsing Next.js product data: {e}")
        
        return None
    
    def _extract_sizes_from_mango_json(self, product_data: List[dict], normalized_targets: dict) -> Set[str]:
        """Extract available sizes from Mango's JSON data."""
        available_sizes = set()
        
        for item in product_data:
            if not isinstance(item, dict):
                continue
            
            # Handle Next.js streaming data
            if item.get('source') == 'nextjs_stream':
                self.logger.debug("Processing Next.js streaming data for sizes")
                
                # Check size entries (individual size availability)
                size_entries = item.get('size_entries', [])
                for size_name, is_available in size_entries:
                    if is_available.lower() == 'true':
                        normalized = self._normalize_size(size_name)
                        for norm_target, original_target in normalized_targets.items():
                            if norm_target == normalized or norm_target in normalized:
                                available_sizes.add(original_target)
                                self.logger.debug(f"Found available size from Next.js: {original_target}")
                
                # Check pattern matches
                patterns = item.get('patterns', {})
                for pattern_name, matches in patterns.items():
                    if matches:
                        self.logger.debug(f"Found {pattern_name} pattern matches: {matches}")
                        for match in matches:
                            # Extract individual sizes from the match
                            size_tokens = re.findall(r'"([XSMLXL]+)"', match)
                            for size_token in size_tokens:
                                normalized = self._normalize_size(size_token)
                                for norm_target, original_target in normalized_targets.items():
                                    if norm_target == normalized or norm_target in normalized:
                                        available_sizes.add(original_target)
                                        self.logger.debug(f"Found available size from pattern: {original_target}")
                
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
        
        # Strategy 1: Look for Mango's specific size list structure
        # Find size list items with the specific Mango classes (they have suffixes like __o9_m)
        size_items = soup.find_all('li', class_=lambda x: x and any('SizesList_listItem' in cls for cls in x))
        
        # If the class-based search doesn't work, fallback to finding all li elements in size context
        if not size_items:
            # Look for li elements within size-related containers
            size_containers = soup.find_all(['div', 'ol'], class_=lambda x: x and any('SizesList' in cls for cls in x))
            for container in size_containers:
                size_items.extend(container.find_all('li'))
            self.logger.debug(f"🔄 Using fallback: found {len(size_items)} li elements in size containers")
        
        self.logger.debug(f"🔍 Found {len(size_items)} size list items with SizesList_listItem class")
        
        for item in size_items:
            # Look for the size button within the list item
            size_button = item.find('button', class_=lambda x: x and any('SizeItem_sizeItem' in cls for cls in x))
            
            # Fallback: if specific class search fails, use any button in the item
            if not size_button:
                size_button = item.find('button')
                if size_button:
                    self.logger.debug("🔄 Using fallback button search")
            
            if not size_button:
                self.logger.debug("❌ No button found in size item")
                continue
            
            # Check if this size is unavailable
            if self._is_mango_size_unavailable(size_button):
                self.logger.debug(f"❌ Size button marked as unavailable")
                continue
            
            # Extract size from font tags (Mango uses <font> tags for size text)
            size_fonts = size_button.find_all('font')
            for font in size_fonts:
                size_text = font.get_text(strip=True)
                if size_text and len(size_text) <= 5:  # Size labels are typically short
                    self.logger.debug(f"🔍 Found size text in font: '{size_text}'")
                    normalized = self._normalize_size(size_text)
                    for norm_target, original_target in normalized_targets.items():
                        if norm_target == normalized or norm_target in normalized:
                            self.logger.debug(f"✅ Size match: '{size_text}' -> '{original_target}'")
                            available_sizes.add(original_target)
        
        # Strategy 2: Fallback to generic size buttons (if the above doesn't work)
        if not available_sizes:
            self.logger.debug("🔄 Using fallback strategy for size detection")
            size_buttons = soup.find_all('button', class_=re.compile(r'size', re.I))
            self.logger.debug(f"🔍 Found {len(size_buttons)} generic size buttons")
            
            for button in size_buttons:
                if self._is_mango_size_unavailable(button):
                    continue
                
                size_text = button.get_text(strip=True)
                if size_text and len(size_text) <= 5:
                    self.logger.debug(f"🔍 Found size text in button: '{size_text}'")
                    normalized = self._normalize_size(size_text)
                    for norm_target, original_target in normalized_targets.items():
                        if norm_target == normalized or norm_target in normalized:
                            self.logger.debug(f"✅ Size match: '{size_text}' -> '{original_target}'")
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
                self.logger.debug(f"❌ Found unavailable text: '{unavailable_text}'")
                return True
        
        # Check for Mango-specific SizeItemContent_notAvailable class
        classes = element.get('class', [])
        class_string = ' '.join(classes)
        
        # Also check child elements for the notAvailable class
        unavailable_spans = element.find_all('span', class_=lambda x: x and any('SizeItemContent_notAvailable' in cls for cls in x))
        if unavailable_spans:
            self.logger.debug("❌ Found SizeItemContent_notAvailable class in child elements")
            return True
        
        if 'SizeItemContent_notAvailable' in class_string:
            self.logger.debug("❌ Found SizeItemContent_notAvailable class")
            return True
        
        # Check for other unavailability classes
        unavailable_classes = [
            'notavailable',
            'not-available', 
            'sold-out',
            'soldout',
            'unavailable',
            'disabled',
        ]
        
        class_string_lower = class_string.lower()
        for unavailable_class in unavailable_classes:
            if unavailable_class in class_string_lower:
                self.logger.debug(f"❌ Found unavailable class: '{unavailable_class}'")
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
        normalized = super()._normalize_size(size)
        
        # Mango-specific normalizations
        mango_mappings = {
            'EINHEITSGRÖSSE': 'U',  # German with umlaut
            'ONE SIZE': 'U',
            'UNICA': 'U',
        }
        
        for old, new in mango_mappings.items():
            normalized = normalized.replace(old, new)
        
        return normalized
