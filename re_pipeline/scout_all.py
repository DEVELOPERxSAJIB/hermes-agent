"""
Full Real Estate Lead Generation — Scout all target cities
Saves results incrementally so timeout doesn't lose data
"""
import json
import sys
import os
import time
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/nanosoft/re_pipeline')
os.chdir('/home/ubuntu/nanosoft')

from osm_sourcing import search_osm_city, is_franchise, US_COORDS, GCC_COORDS

OUTPUT = "/home/ubuntu/nanosoft/re_pipeline/raw_leads.json"

def load_existing():
    if os.path.exists(OUTPUT):
        with open(OUTPUT) as f:
            return json.load(f)
    return []

def save(leads):
    with open(OUTPUT, "w") as f:
        json.dump(leads, f, indent=2)

def main():
    existing = load_existing()
    existing_names = {l["Brokerage_Name"].lower().strip() for l in existing}
    print(f"Existing leads: {len(existing)}")

    all_cities = {**US_COORDS, **GCC_COORDS}
    cities_list = list(all_cities.keys())

    new_count = 0
    for i, city in enumerate(cities_list):
        print(f"[{i+1}/{len(cities_list)}] Scouting {city}...")
        try:
            results = search_osm_city(city, radius_meters=15000)
            for r in results:
                name_key = r["Brokerage_Name"].lower().strip()
                if name_key not in existing_names and not is_franchise(r["Brokerage_Name"]):
                    existing.append(r)
                    existing_names.add(name_key)
                    new_count += 1
            print(f"  Found {len(results)} (new: {new_count} total)")
            save(existing)  # Save incrementally
        except Exception as e:
            print(f"  Error: {e}")
        time.sleep(0.5)

    print(f"\n--- TOTAL RAW LEADS: {len(existing)} ---")

    from collections import Counter
    city_counts = Counter(l["City"] for l in existing)
    for city, count in city_counts.most_common():
        print(f"  {city}: {count}")

    us = sum(1 for l in existing if l["Market"] == "US")
    gcc = sum(1 for l in existing if l["Market"] == "GCC")
    print(f"\nUS: {us} | GCC: {gcc}")

if __name__ == "__main__":
    main()
