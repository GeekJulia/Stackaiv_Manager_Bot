def paginate_items(call_data, items, page_size=10):
    """
    Standardize calculating pagination offsets for list displays.
    
    Args:
        call_data: The callback data string (e.g. "admin:list_transactions:2")
        items: List of all items to paginate
        page_size: Number of items per page
        
    Returns:
        tuple: (page_items, current_page, total_pages)
    """
    parts = call_data.split(":")
    page = int(parts[2]) if len(parts) > 2 else 0
    total = len(items)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    # Bound the page
    page = max(0, min(page, total_pages - 1))
    
    start = page * page_size
    end = start + page_size
    page_items = items[start:end]
    
    return page_items, page, total_pages
