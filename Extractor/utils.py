def reorder_result(result:dict, is_api_user:str, requested_fields:set) -> dict:
    
    if not is_api_user and not result.get('error'):  # unsigned
        result['favicons'] = result['favicons'][:2] if result.get('favicons') else []

    base_keys = {"success", "blocked", "error", "http_status", "duration_ms", "fetch_method", "content_type"}

    allowed_keys = base_keys.union(requested_fields)
    if "screenshot" in allowed_keys: allowed_keys.add("screenshot_note")
    # Rebuild dictionary omitting unauthorized/unrequested keys
    clean_result = {key: val for key, val in result.items() if key in allowed_keys}

    return clean_result