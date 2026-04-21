import os
import glob
import re

routes_dir = "backend/app/api/routes"

for filepath in glob.glob(f"{routes_dir}/*.py"):
    with open(filepath, "r") as f:
        src = f.read()

    # 1. Update imports
    if "from app.core.db import get_supabase" in src and "execute_async" not in src:
        src = src.replace("from app.core.db import get_supabase", "from app.core.db import get_supabase, execute_async")
        
    # 2. Make helper functions async only if they are 'def' and not 'async def'
    for c in ["_assert_workspace_owner", "_assert_slack_team_owner", "assert_team_owner"]:
        src = re.sub(r'(?<!async )def ' + c, 'async def ' + c, src)
        # Update calls to await only if not already await
        src = re.sub(r'(?<!await )' + c + r'\(', 'await ' + c + '(', src)
        src = src.replace(f"async def await {c}(", f"async def {c}(")

    while True:
        ex_idx = src.find(".execute()")
        if ex_idx == -1:
            break
            
        matches = list(re.finditer(r'(?:sb|supabase)\.(?:table|rpc|delete|auth)', src[:ex_idx]))
        if not matches:
            break
            
        last_match = matches[-1]
        start_idx = last_match.start()
        
        prefix = src[:start_idx]
        query = src[start_idx:ex_idx]
        suffix = src[ex_idx + len(".execute()"):]
        
        src = prefix + "await execute_async(" + query + ")" + suffix

    with open(filepath, "w") as f:
        f.write(src)

print("Done")
