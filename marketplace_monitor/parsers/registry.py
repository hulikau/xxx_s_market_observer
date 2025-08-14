"""Parser registry for managing different site parsers."""

import logging
from typing import Dict, List, Optional, Type
from .base import BaseParser


class ParserRegistry:
    """Registry for managing parsers for different sites."""
    
    def __init__(self):
        """Initialize parser registry."""
        self._parsers: Dict[str, Type[BaseParser]] = {}
        self._instances: Dict[str, BaseParser] = {}
        self.logger = logging.getLogger("parser.registry")
    
    def register(self, name: str, parser_class: Type[BaseParser]) -> None:
        """Register a parser class.
        
        Args:
            name: Parser name
            parser_class: Parser class to register
        """
        if not issubclass(parser_class, BaseParser):
            raise ValueError(f"Parser class must inherit from BaseParser: {parser_class}")
        
        self._parsers[name] = parser_class
        self.logger.info(f"Registered parser: {name}")
    
    def get_parser(self, name: str, config: Dict = None) -> Optional[BaseParser]:
        """Get a parser instance by name.
        
        Args:
            name: Parser name
            config: Parser configuration
            
        Returns:
            Parser instance or None if not found
        """
        if name not in self._parsers:
            self.logger.error(f"Parser not found: {name}")
            return None
        
        # Create instance key including config for caching
        if config:
            # Filter out None values and create a stable key
            filtered_config = {k: v for k, v in config.items() if v is not None}
            config_key = str(sorted(filtered_config.items()))
        else:
            config_key = ""
        instance_key = f"{name}:{config_key}"
        
        # Return cached instance if available
        if instance_key in self._instances:
            return self._instances[instance_key]
        
        # Create new instance
        try:
            parser_class = self._parsers[name]
            self.logger.debug(f"Creating parser instance for {name} with config: {config}")
            instance = parser_class(name, config)
            self._instances[instance_key] = instance
            self.logger.info(f"Successfully created parser instance: {name}")
            return instance
        except Exception as e:
            self.logger.error(f"Failed to create parser instance {name}: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    def get_parser_for_url(self, url: str, config: Dict = None) -> Optional[BaseParser]:
        """Get the appropriate parser for a URL.
        
        Args:
            url: URL to find parser for
            config: Parser configuration
            
        Returns:
            Parser instance that can handle the URL, or None
        """
        for name, parser_class in self._parsers.items():
            try:
                # Create temporary instance to test URL compatibility
                temp_instance = parser_class(name, config)
                if temp_instance.can_parse(url):
                    return self.get_parser(name, config)
            except Exception as e:
                self.logger.warning(f"Error checking parser {name} for URL {url}: {e}")
                continue
        
        self.logger.warning(f"No parser found for URL: {url}")
        return None
    
    def list_parsers(self) -> List[str]:
        """Get list of registered parser names.
        
        Returns:
            List of parser names
        """
        return list(self._parsers.keys())
    
    def clear(self) -> None:
        """Clear all registered parsers and instances."""
        self._parsers.clear()
        self._instances.clear()
        self.logger.info("Cleared all parsers")


# Global registry instance
registry = ParserRegistry()
