from app.cache.redis_client import get_redis
from pathlib import Path

redis_client = get_redis()

script_path = Path(__file__).parent / "token_bucket.lua"

with open(script_path) as f:
    lua_script = f.read()

token_bucket = redis_client.register_script(lua_script)