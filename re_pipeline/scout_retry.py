"""Scout remaining cities with rate limit handling"""
import json, sys, os, time
sys.path.insert(0, '/home/ubuntu/nanosoft/re_pipeline')
os.chdir('/home/ubuntu/nanosoft')
from osm_sourcing import search_osm_city, is_franchise

OUTPUT = "/home/ubuntu/nanosoft/re_pipeline/raw_leads.json"

def load_existing():
    if os.path.exists(OUTPUT):
        with open(OUTPUT) as f:
            return json.load(f)
    return []

def save(leads):
    with open(OUTPUT, "w") as f:
        json.dump(leads, f, indent=2)

cities_to_scout = sys.argv[1:]
existing = load_existing()
existing_names = {l["Brokerage_Name"].lower().strip() for l in existing}

for city in cities_to_scout:
    print(f"Scouting {city}...")
    for attempt in range(3):
        try:
            results = search_osm_city(city, radius_meters=15000)
            for r in results:
                name_key = r["Brokerage_Name"].lower().strip()
                if name_key not in existing_names and not is_franchise(r["Brokerage_Name"]):
                    existing.append(r)
                    existing_names.add(name_key)
            print(f"  Found {len(results)}, total now: {len(existing)}")
            save(existing)
            break
        except Exception as e:
            if "429" in str(e):
                print(f"  Rate limited, waiting 10s...")
                time.sleep(10)
            else:
                print(f"  Error: {e}")
                break
    time.sleep(2)

print(f"Done. Total: {len(existing)}")
