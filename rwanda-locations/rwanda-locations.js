/**
 * Rwanda Locations - Easy Integration Library
 *
 * A simple, powerful utility to work with Rwanda's administrative locations.
 * Supports: Provinces, Districts, Sectors, Cells, and Villages
 *
 * For a more feature-rich package version, visit:
 * https://github.com/DevRW/rwanda-location
 */

const fs = require('fs');
const path = require('path');

class RwandaLocations {
  constructor() {
    this.data = null;
    this.cache = {
      provinces: null,
      districts: null,
      sectors: null,
      cells: null,
      villages: null
    };
  }

  /**
   * Load the locations data from JSON file
   */
  load() {
    if (!this.data) {
      const dataPath = path.join(__dirname, 'locations.json');
      this.data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
    }
    return this;
  }

  /**
   * Get all provinces
   * @returns {Array} List of unique provinces
   */
  getProvinces() {
    if (this.cache.provinces) return this.cache.provinces;

    this.load();
    const provinces = new Map();

    this.data.forEach(location => {
      if (!provinces.has(location.province_code)) {
        provinces.set(location.province_code, {
          code: location.province_code,
          name: location.province_name
        });
      }
    });

    this.cache.provinces = Array.from(provinces.values()).sort((a, b) => a.code - b.code);
    return this.cache.provinces;
  }

  /**
   * Get all districts, optionally filtered by province
   * @param {number|string} provinceCode - Optional province code to filter by
   * @returns {Array} List of districts
   */
  getDistricts(provinceCode = null) {
    this.load();
    const districts = new Map();

    this.data.forEach(location => {
      if (provinceCode && location.province_code != provinceCode) return;

      if (!districts.has(location.district_code)) {
        districts.set(location.district_code, {
          code: location.district_code,
          name: location.district_name,
          province_code: location.province_code,
          province_name: location.province_name
        });
      }
    });

    return Array.from(districts.values()).sort((a, b) => a.code - b.code);
  }

  /**
   * Get all sectors, optionally filtered by district
   * @param {number|string} districtCode - Optional district code to filter by
   * @returns {Array} List of sectors
   */
  getSectors(districtCode = null) {
    this.load();
    const sectors = new Map();

    this.data.forEach(location => {
      if (districtCode && location.district_code != districtCode) return;

      if (!sectors.has(location.sector_code)) {
        sectors.set(location.sector_code, {
          code: location.sector_code,
          name: location.sector_name,
          district_code: location.district_code,
          district_name: location.district_name,
          province_code: location.province_code,
          province_name: location.province_name
        });
      }
    });

    return Array.from(sectors.values()).sort((a, b) => a.code.localeCompare(b.code));
  }

  /**
   * Get all cells, optionally filtered by sector
   * @param {string} sectorCode - Optional sector code to filter by
   * @returns {Array} List of cells
   */
  getCells(sectorCode = null) {
    this.load();
    const cells = new Map();

    this.data.forEach(location => {
      if (sectorCode && location.sector_code != sectorCode) return;

      if (!cells.has(location.cell_code)) {
        cells.set(location.cell_code, {
          code: location.cell_code,
          name: location.cell_name,
          sector_code: location.sector_code,
          sector_name: location.sector_name,
          district_code: location.district_code,
          district_name: location.district_name,
          province_code: location.province_code,
          province_name: location.province_name
        });
      }
    });

    return Array.from(cells.values()).sort((a, b) => a.code - b.code);
  }

  /**
   * Get all villages, optionally filtered by cell
   * @param {number|string} cellCode - Optional cell code to filter by
   * @returns {Array} List of villages
   */
  getVillages(cellCode = null) {
    this.load();
    const villages = new Map();

    this.data.forEach(location => {
      if (cellCode && location.cell_code != cellCode) return;

      if (!villages.has(location.village_code)) {
        villages.set(location.village_code, {
          code: location.village_code,
          name: location.village_name,
          cell_code: location.cell_code,
          cell_name: location.cell_name,
          sector_code: location.sector_code,
          sector_name: location.sector_name,
          district_code: location.district_code,
          district_name: location.district_name,
          province_code: location.province_code,
          province_name: location.province_name
        });
      }
    });

    return Array.from(villages.values()).sort((a, b) => a.code - b.code);
  }

  /**
   * Search locations by name (case-insensitive)
   * @param {string} searchTerm - Search term
   * @param {string} level - Level to search: 'province', 'district', 'sector', 'cell', 'village', or 'all'
   * @returns {Array} Matching locations
   */
  search(searchTerm, level = 'all') {
    this.load();
    const term = searchTerm.toLowerCase();
    const results = [];
    const seen = new Set();

    this.data.forEach(location => {
      const matches =
        (level === 'all' || level === 'province') && location.province_name.toLowerCase().includes(term) ||
        (level === 'all' || level === 'district') && location.district_name.toLowerCase().includes(term) ||
        (level === 'all' || level === 'sector') && location.sector_name.toLowerCase().includes(term) ||
        (level === 'all' || level === 'cell') && location.cell_name.toLowerCase().includes(term) ||
        (level === 'all' || level === 'village') && location.village_name.toLowerCase().includes(term);

      if (matches) {
        const key = `${location.province_code}-${location.district_code}-${location.sector_code}-${location.cell_code}-${location.village_code}`;
        if (!seen.has(key)) {
          seen.add(key);
          results.push({
            province: { code: location.province_code, name: location.province_name },
            district: { code: location.district_code, name: location.district_name },
            sector: { code: location.sector_code, name: location.sector_name },
            cell: { code: location.cell_code, name: location.cell_name },
            village: { code: location.village_code, name: location.village_name }
          });
        }
      }
    });

    return results;
  }

  /**
   * Get location hierarchy for a specific village
   * @param {number|string} villageCode - Village code
   * @returns {Object|null} Complete location hierarchy
   */
  getLocationByVillageCode(villageCode) {
    this.load();
    const location = this.data.find(loc => loc.village_code == villageCode);

    if (!location) return null;

    return {
      country: { code: location.country_code, name: location.country_name },
      province: { code: location.province_code, name: location.province_name },
      district: { code: location.district_code, name: location.district_name },
      sector: { code: location.sector_code, name: location.sector_name },
      cell: { code: location.cell_code, name: location.cell_name },
      village: { code: location.village_code, name: location.village_name }
    };
  }

  /**
   * Get hierarchy tree structure
   * @param {Object} options - Options for filtering (provinceCode, districtCode, etc.)
   * @returns {Array} Hierarchical tree structure
   */
  getHierarchy(options = {}) {
    this.load();
    const { provinceCode, districtCode, sectorCode, cellCode } = options;

    const tree = {};

    this.data.forEach(location => {
      if (provinceCode && location.province_code != provinceCode) return;
      if (districtCode && location.district_code != districtCode) return;
      if (sectorCode && location.sector_code != sectorCode) return;
      if (cellCode && location.cell_code != cellCode) return;

      const pKey = location.province_code;
      const dKey = location.district_code;
      const sKey = location.sector_code;
      const cKey = location.cell_code;

      if (!tree[pKey]) {
        tree[pKey] = {
          code: location.province_code,
          name: location.province_name,
          districts: {}
        };
      }

      if (!tree[pKey].districts[dKey]) {
        tree[pKey].districts[dKey] = {
          code: location.district_code,
          name: location.district_name,
          sectors: {}
        };
      }

      if (!tree[pKey].districts[dKey].sectors[sKey]) {
        tree[pKey].districts[dKey].sectors[sKey] = {
          code: location.sector_code,
          name: location.sector_name,
          cells: {}
        };
      }

      if (!tree[pKey].districts[dKey].sectors[sKey].cells[cKey]) {
        tree[pKey].districts[dKey].sectors[sKey].cells[cKey] = {
          code: location.cell_code,
          name: location.cell_name,
          villages: []
        };
      }

      const villages = tree[pKey].districts[dKey].sectors[sKey].cells[cKey].villages;
      if (!villages.find(v => v.code === location.village_code)) {
        villages.push({
          code: location.village_code,
          name: location.village_name
        });
      }
    });

    // Convert nested objects to arrays
    return Object.values(tree).map(province => ({
      ...province,
      districts: Object.values(province.districts).map(district => ({
        ...district,
        sectors: Object.values(district.sectors).map(sector => ({
          ...sector,
          cells: Object.values(sector.cells)
        }))
      }))
    }));
  }

  /**
   * Get statistics about the data
   * @returns {Object} Statistics
   */
  getStats() {
    this.load();

    return {
      totalLocations: this.data.length,
      provinces: this.getProvinces().length,
      districts: this.getDistricts().length,
      sectors: this.getSectors().length,
      cells: this.getCells().length,
      villages: this.getVillages().length
    };
  }
}

// Export for Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = RwandaLocations;
}

// Export for browser (if needed)
if (typeof window !== 'undefined') {
  window.RwandaLocations = RwandaLocations;
}
