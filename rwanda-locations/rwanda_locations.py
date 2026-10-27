"""
Rwanda Locations - Easy Integration Library

A simple, powerful utility to work with Rwanda's administrative locations.
Supports: Provinces, Districts, Sectors, Cells, and Villages

For a more feature-rich package version, visit:
https://github.com/DevRW/rwanda-location
"""

import json
import os
from typing import List, Dict, Optional, Any


class RwandaLocations:
    def __init__(self, data_file: str = None):
        """
        Initialize the Rwanda Locations library

        Args:
            data_file: Path to the locations.json file (default: locations.json in the same directory)
        """
        self.data_file = data_file or os.path.join(os.path.dirname(__file__), 'locations.json')
        self.data: List[Dict] = None
        self.cache = {
            'provinces': None,
            'districts': None,
            'sectors': None,
            'cells': None,
            'villages': None
        }

    def load(self) -> 'RwandaLocations':
        """Load the locations data from JSON file"""
        if self.data is None:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        return self

    def get_provinces(self) -> List[Dict[str, Any]]:
        """
        Get all provinces

        Returns:
            List of unique provinces with code and name
        """
        if self.cache['provinces']:
            return self.cache['provinces']

        self.load()
        provinces = {}

        for location in self.data:
            code = location['province_code']
            if code not in provinces:
                provinces[code] = {
                    'code': location['province_code'],
                    'name': location['province_name']
                }

        self.cache['provinces'] = sorted(provinces.values(), key=lambda x: x['code'])
        return self.cache['provinces']

    def get_districts(self, province_code: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all districts, optionally filtered by province

        Args:
            province_code: Optional province code to filter by

        Returns:
            List of districts
        """
        self.load()
        districts = {}

        for location in self.data:
            if province_code is not None and location['province_code'] != province_code:
                continue

            code = location['district_code']
            if code not in districts:
                districts[code] = {
                    'code': location['district_code'],
                    'name': location['district_name'],
                    'province_code': location['province_code'],
                    'province_name': location['province_name']
                }

        return sorted(districts.values(), key=lambda x: x['code'])

    def get_sectors(self, district_code: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all sectors, optionally filtered by district

        Args:
            district_code: Optional district code to filter by

        Returns:
            List of sectors
        """
        self.load()
        sectors = {}

        for location in self.data:
            if district_code is not None and location['district_code'] != district_code:
                continue

            code = location['sector_code']
            if code not in sectors:
                sectors[code] = {
                    'code': location['sector_code'],
                    'name': location['sector_name'],
                    'district_code': location['district_code'],
                    'district_name': location['district_name'],
                    'province_code': location['province_code'],
                    'province_name': location['province_name']
                }

        return sorted(sectors.values(), key=lambda x: x['code'])

    def get_cells(self, sector_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all cells, optionally filtered by sector

        Args:
            sector_code: Optional sector code to filter by

        Returns:
            List of cells
        """
        self.load()
        cells = {}

        for location in self.data:
            if sector_code is not None and location['sector_code'] != sector_code:
                continue

            code = location['cell_code']
            if code not in cells:
                cells[code] = {
                    'code': location['cell_code'],
                    'name': location['cell_name'],
                    'sector_code': location['sector_code'],
                    'sector_name': location['sector_name'],
                    'district_code': location['district_code'],
                    'district_name': location['district_name'],
                    'province_code': location['province_code'],
                    'province_name': location['province_name']
                }

        return sorted(cells.values(), key=lambda x: x['code'])

    def get_villages(self, cell_code: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all villages, optionally filtered by cell

        Args:
            cell_code: Optional cell code to filter by

        Returns:
            List of villages
        """
        self.load()
        villages = {}

        for location in self.data:
            if cell_code is not None and location['cell_code'] != cell_code:
                continue

            code = location['village_code']
            if code not in villages:
                villages[code] = {
                    'code': location['village_code'],
                    'name': location['village_name'],
                    'cell_code': location['cell_code'],
                    'cell_name': location['cell_name'],
                    'sector_code': location['sector_code'],
                    'sector_name': location['sector_name'],
                    'district_code': location['district_code'],
                    'district_name': location['district_name'],
                    'province_code': location['province_code'],
                    'province_name': location['province_name']
                }

        return sorted(villages.values(), key=lambda x: x['code'])

    def search(self, search_term: str, level: str = 'all') -> List[Dict[str, Any]]:
        """
        Search locations by name (case-insensitive)

        Args:
            search_term: Search term
            level: Level to search: 'province', 'district', 'sector', 'cell', 'village', or 'all'

        Returns:
            List of matching locations
        """
        self.load()
        term = search_term.lower()
        results = []
        seen = set()

        for location in self.data:
            matches = (
                (level == 'all' or level == 'province') and term in location['province_name'].lower() or
                (level == 'all' or level == 'district') and term in location['district_name'].lower() or
                (level == 'all' or level == 'sector') and term in location['sector_name'].lower() or
                (level == 'all' or level == 'cell') and term in location['cell_name'].lower() or
                (level == 'all' or level == 'village') and term in location['village_name'].lower()
            )

            if matches:
                key = f"{location['province_code']}-{location['district_code']}-{location['sector_code']}-{location['cell_code']}-{location['village_code']}"
                if key not in seen:
                    seen.add(key)
                    results.append({
                        'province': {'code': location['province_code'], 'name': location['province_name']},
                        'district': {'code': location['district_code'], 'name': location['district_name']},
                        'sector': {'code': location['sector_code'], 'name': location['sector_name']},
                        'cell': {'code': location['cell_code'], 'name': location['cell_name']},
                        'village': {'code': location['village_code'], 'name': location['village_name']}
                    })

        return results

    def get_location_by_village_code(self, village_code: int) -> Optional[Dict[str, Any]]:
        """
        Get location hierarchy for a specific village

        Args:
            village_code: Village code

        Returns:
            Complete location hierarchy or None if not found
        """
        self.load()

        for location in self.data:
            if location['village_code'] == village_code:
                return {
                    'country': {'code': location['country_code'], 'name': location['country_name']},
                    'province': {'code': location['province_code'], 'name': location['province_name']},
                    'district': {'code': location['district_code'], 'name': location['district_name']},
                    'sector': {'code': location['sector_code'], 'name': location['sector_name']},
                    'cell': {'code': location['cell_code'], 'name': location['cell_name']},
                    'village': {'code': location['village_code'], 'name': location['village_name']}
                }

        return None

    def get_hierarchy(self, province_code: Optional[int] = None,
                     district_code: Optional[int] = None,
                     sector_code: Optional[str] = None,
                     cell_code: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get hierarchy tree structure

        Args:
            province_code: Optional province code to filter by
            district_code: Optional district code to filter by
            sector_code: Optional sector code to filter by
            cell_code: Optional cell code to filter by

        Returns:
            Hierarchical tree structure
        """
        self.load()
        tree = {}

        for location in self.data:
            if province_code is not None and location['province_code'] != province_code:
                continue
            if district_code is not None and location['district_code'] != district_code:
                continue
            if sector_code is not None and location['sector_code'] != sector_code:
                continue
            if cell_code is not None and location['cell_code'] != cell_code:
                continue

            p_key = location['province_code']
            d_key = location['district_code']
            s_key = location['sector_code']
            c_key = location['cell_code']

            if p_key not in tree:
                tree[p_key] = {
                    'code': location['province_code'],
                    'name': location['province_name'],
                    'districts': {}
                }

            if d_key not in tree[p_key]['districts']:
                tree[p_key]['districts'][d_key] = {
                    'code': location['district_code'],
                    'name': location['district_name'],
                    'sectors': {}
                }

            if s_key not in tree[p_key]['districts'][d_key]['sectors']:
                tree[p_key]['districts'][d_key]['sectors'][s_key] = {
                    'code': location['sector_code'],
                    'name': location['sector_name'],
                    'cells': {}
                }

            if c_key not in tree[p_key]['districts'][d_key]['sectors'][s_key]['cells']:
                tree[p_key]['districts'][d_key]['sectors'][s_key]['cells'][c_key] = {
                    'code': location['cell_code'],
                    'name': location['cell_name'],
                    'villages': []
                }

            villages = tree[p_key]['districts'][d_key]['sectors'][s_key]['cells'][c_key]['villages']
            if not any(v['code'] == location['village_code'] for v in villages):
                villages.append({
                    'code': location['village_code'],
                    'name': location['village_name']
                })

        # Convert nested dicts to lists
        result = []
        for province in tree.values():
            province['districts'] = [
                {
                    **district,
                    'sectors': [
                        {
                            **sector,
                            'cells': list(sector['cells'].values())
                        }
                        for sector in district['sectors'].values()
                    ]
                }
                for district in province['districts'].values()
            ]
            result.append(province)

        return result

    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the data

        Returns:
            Dictionary with counts of each administrative level
        """
        self.load()

        return {
            'total_locations': len(self.data),
            'provinces': len(self.get_provinces()),
            'districts': len(self.get_districts()),
            'sectors': len(self.get_sectors()),
            'cells': len(self.get_cells()),
            'villages': len(self.get_villages())
        }


# Example usage
if __name__ == '__main__':
    # Create instance
    locations = RwandaLocations()

    # Get all provinces
    provinces = locations.get_provinces()
    print(f"Total Provinces: {len(provinces)}")
    print(f"First Province: {provinces[0]}")

    # Get statistics
    stats = locations.get_stats()
    print(f"\nStatistics: {stats}")

    # Search example
    results = locations.search('kigali')
    print(f"\nSearch results for 'kigali': {len(results)} results")
