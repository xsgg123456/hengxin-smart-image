"""Server-owned entry keys and platform/brand defaults."""
from typing import Literal

PlatformToolKey = Literal['outon', 'outonlife', 'beleev', 'wayfair', 'walmart', 'home-depot', 'mercado-libre']
PLATFORM_TOOLS = {
    'outon': ('Amazon', 'OUTON'),
    'outonlife': ('Amazon', 'OUTONLIFE'),
    'beleev': ('Amazon', 'BELEEV'),
    'wayfair': ('Wayfair', ''),
    'walmart': ('Walmart', ''),
    'home-depot': ('The Home Depot', ''),
    'mercado-libre': ('Mercado Libre', ''),
}
TOOL_KEYS = (*PLATFORM_TOOLS, 'custom-size')
