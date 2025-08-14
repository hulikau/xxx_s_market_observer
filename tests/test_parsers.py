"""Tests for parser system."""

import pytest
from unittest.mock import Mock, patch

from marketplace_monitor.parsers.base import BaseParser, ParseResult
from marketplace_monitor.parsers.registry import ParserRegistry
from marketplace_monitor.parsers.generic import GenericParser
from marketplace_monitor.parsers.nike import NikeParser


class TestParser(BaseParser):
    """Test parser for testing."""
    
    def can_parse(self, url: str) -> bool:
        return "test.com" in url
    
    def parse(self, url: str, target_sizes):
        return ParseResult(
            url=url,
            product_name="Test Product",
            available_sizes={"US 9", "US 10"},
            in_stock=True
        )


def test_parser_registry():
    """Test parser registry functionality."""
    registry = ParserRegistry()
    
    # Register parser
    registry.register('test', TestParser)
    assert 'test' in registry.list_parsers()
    
    # Get parser
    parser = registry.get_parser('test')
    assert parser is not None
    assert isinstance(parser, TestParser)
    
    # Test URL matching
    parser = registry.get_parser_for_url('https://test.com/product')
    assert parser is not None
    
    # Test non-existent parser
    parser = registry.get_parser('nonexistent')
    assert parser is None


def test_generic_parser():
    """Test generic parser."""
    parser = GenericParser('test')
    
    # Should accept any URL
    assert parser.can_parse('https://example.com')
    assert parser.can_parse('https://anysite.com')


def test_nike_parser():
    """Test Nike parser."""
    parser = NikeParser('nike')
    
    # Should only accept Nike URLs
    assert parser.can_parse('https://nike.com/product')
    assert parser.can_parse('https://www.nike.com/product')
    assert not parser.can_parse('https://adidas.com/product')


def test_parse_result():
    """Test ParseResult dataclass."""
    result = ParseResult(url="https://example.com")
    
    assert result.url == "https://example.com"
    assert result.available_sizes == set()
    assert result.in_stock is False
    assert result.metadata == {}
    
    # Test with data
    result = ParseResult(
        url="https://example.com",
        product_name="Test Product",
        available_sizes={"US 9", "US 10"},
        price="$100",
        in_stock=True
    )
    
    assert result.product_name == "Test Product"
    assert len(result.available_sizes) == 2
    assert result.in_stock is True
