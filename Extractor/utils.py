
# Fields that are ALWAYS removed regardless of user type
INTERNAL_KEYS = ['_include_screenshot']

SIGNED_ONLY_KEYS = ['keywords','image','screenshot','theme_color','robots_meta','robots_txt','social_links']

# At the end of manage_result, before returning, reorder like this:
META_KEYS = ['success', 'blocked', 'error', 'http_status', 'duration_ms', 'fetch_method', 'content_type', 'url']

# Reorders result to keep META_KEYS at the top.
def _reorder(result: dict) -> dict:
    ordered = {}
    for key in META_KEYS:
        if key in result:
            ordered[key] = result[key]
    # append remaining keys after meta keys
    for key, value in result.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def manage_result(result:dict, user_type:str="unsigned", fields:list=[]) -> dict:
    # Remove Internal Keys
    for key in INTERNAL_KEYS:
        result.pop(key, None)

    if user_type == "unsigned":
        # Remove Exclusive signup keys 
        for key in SIGNED_ONLY_KEYS:
            result.pop(key, None) 
        result['favicons'] = result['favicons'][:2] if result['favicons'] else [] # only send two favicons, if < 2 send all.
        
        return _reorder(result)
    
    elif user_type == "signed":
        # If user provides fields, extract only those + default.
        if fields:
            user_result = {key:value for key,value in result.items() if key in fields}
            # Keep default keys even if user dosent ask for
            for key in ['success','blocked','error','http_status']:
                user_result[key] = result[key]
            
            return _reorder(user_result)
    
    return _reorder(result)
             