"""
Python Integration Examples

This file demonstrates how to use the Rwanda Locations library in Python
"""

import sys
import os

# Add parent directory to path to import the module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rwanda_locations import RwandaLocations

# Create an instance
locations = RwandaLocations()

print('=== Rwanda Locations - Python Examples ===\n')

# Example 1: Get all provinces
print('1. Getting all provinces:')
provinces = locations.get_provinces()
print(f'   Total provinces: {len(provinces)}')
for province in provinces:
    print(f'   - {province["name"]} (Code: {province["code"]})')

# Example 2: Get districts in a specific province (Kigali = 1)
print('\n2. Getting districts in Kigali province:')
kigali_districts = locations.get_districts(province_code=1)
print(f'   Total districts in Kigali: {len(kigali_districts)}')
for district in kigali_districts[:3]:
    print(f'   - {district["name"]} (Code: {district["code"]})')

# Example 3: Get sectors in a specific district
print('\n3. Getting sectors in Nyarugenge district (Code: 101):')
sectors = locations.get_sectors(district_code=101)
print(f'   Total sectors: {len(sectors)}')
for sector in sectors[:3]:
    print(f'   - {sector["name"]} (Code: {sector["code"]})')

# Example 4: Search for locations
print('\n4. Searching for locations containing "kigali":')
search_results = locations.search('kigali')
print(f'   Found {len(search_results)} results')
if search_results:
    first_result = search_results[0]
    print(f'   Example: {first_result["village"]["name"]}, {first_result["cell"]["name"]}, {first_result["sector"]["name"]}')

# Example 5: Search only in districts
print('\n5. Searching for districts containing "nya":')
district_search = locations.search('nya', level='district')
print(f'   Found {len(district_search)} results')
for result in district_search[:3]:
    print(f'   - {result["district"]["name"]} in {result["province"]["name"]}')

# Example 6: Get location by village code
print('\n6. Getting location details by village code (101010102):')
village_location = locations.get_location_by_village_code(101010102)
if village_location:
    print(f'   Country: {village_location["country"]["name"]}')
    print(f'   Province: {village_location["province"]["name"]}')
    print(f'   District: {village_location["district"]["name"]}')
    print(f'   Sector: {village_location["sector"]["name"]}')
    print(f'   Cell: {village_location["cell"]["name"]}')
    print(f'   Village: {village_location["village"]["name"]}')

# Example 7: Get statistics
print('\n7. Getting statistics:')
stats = locations.get_stats()
print(f'   Total locations: {stats["total_locations"]}')
print(f'   Provinces: {stats["provinces"]}')
print(f'   Districts: {stats["districts"]}')
print(f'   Sectors: {stats["sectors"]}')
print(f'   Cells: {stats["cells"]}')
print(f'   Villages: {stats["villages"]}')

# Example 8: Get hierarchical tree (limited to one province for brevity)
print('\n8. Getting hierarchical tree for Kigali province:')
hierarchy = locations.get_hierarchy(province_code=1)
if hierarchy:
    kigali = hierarchy[0]
    print(f'   Province: {kigali["name"]}')
    print(f'   Districts: {len(kigali["districts"])}')
    if kigali['districts']:
        first_district = kigali['districts'][0]
        print(f'   First district: {first_district["name"]}')
        print(f'   Sectors in {first_district["name"]}: {len(first_district["sectors"])}')

# Example 9: Building a cascading dropdown (common use case)
print('\n9. Simulating cascading dropdown selection:')
selected_province = 1  # Kigali
districts_for_dropdown = locations.get_districts(province_code=selected_province)
print(f'   Step 1: User selects province {selected_province}')
print(f'   Step 2: Load districts: {len(districts_for_dropdown)} options')

selected_district = 101  # Nyarugenge
sectors_for_dropdown = locations.get_sectors(district_code=selected_district)
print(f'   Step 3: User selects district {selected_district}')
print(f'   Step 4: Load sectors: {len(sectors_for_dropdown)} options')

# Example 10: Get all villages in a specific sector
print('\n10. Getting all villages in a specific sector (010101):')
cells = locations.get_cells(sector_code='010101')
print(f'   Total cells in this sector: {len(cells)}')
if cells:
    first_cell = cells[0]
    villages = locations.get_villages(cell_code=first_cell['code'])
    print(f'   Villages in {first_cell["name"]} cell: {len(villages)}')
    for village in villages[:3]:
        print(f'   - {village["name"]} (Code: {village["code"]})')

# Example 11: Using with pandas (if available)
try:
    import pandas as pd

    print('\n11. Creating a pandas DataFrame:')
    all_districts = locations.get_districts()
    df = pd.DataFrame(all_districts)
    print(f'   DataFrame shape: {df.shape}')
    print('   First 3 rows:')
    print(df.head(3).to_string(index=False))
except ImportError:
    print('\n11. Pandas integration (pandas not installed)')
    print('   Install pandas with: pip install pandas')

# Example 12: Export to JSON
print('\n12. Exporting province data to JSON:')
import json
provinces_json = json.dumps(provinces, indent=2, ensure_ascii=False)
print(f'   Exported {len(provinces)} provinces to JSON format')
print('   Sample:')
print(provinces_json[:200] + '...')

print('\n=== Examples completed successfully! ===')
