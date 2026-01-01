
from src.intelligence.discovery import discover_trends

try:
    print("Testing trend discovery...")
    trends = discover_trends()
    print(f"Result: Found {len(trends)} verified trends.")
    if trends:
        print(f"Top trend: {trends[0].topic}")
except Exception as e:
    print(f"Error during discovery: {e}")
