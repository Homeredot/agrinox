/**
 * JavaScript Integration Examples
 *
 * This file demonstrates how to use the Rwanda Locations library in JavaScript/Node.js
 */

const RwandaLocations = require('../rwanda-locations');

// Create an instance
const locations = new RwandaLocations();

console.log('=== Rwanda Locations - JavaScript Examples ===\n');

// Example 1: Get all provinces
console.log('1. Getting all provinces:');
const provinces = locations.getProvinces();
console.log(`   Total provinces: ${provinces.length}`);
provinces.forEach(province => {
    console.log(`   - ${province.name} (Code: ${province.code})`);
});

// Example 2: Get districts in a specific province (Kigali = 1)
console.log('\n2. Getting districts in Kigali province:');
const kigaliDistricts = locations.getDistricts(1);
console.log(`   Total districts in Kigali: ${kigaliDistricts.length}`);
kigaliDistricts.slice(0, 3).forEach(district => {
    console.log(`   - ${district.name} (Code: ${district.code})`);
});

// Example 3: Get sectors in a specific district
console.log('\n3. Getting sectors in Nyarugenge district (Code: 101):');
const sectors = locations.getSectors(101);
console.log(`   Total sectors: ${sectors.length}`);
sectors.slice(0, 3).forEach(sector => {
    console.log(`   - ${sector.name} (Code: ${sector.code})`);
});

// Example 4: Search for locations
console.log('\n4. Searching for locations containing "kigali":');
const searchResults = locations.search('kigali');
console.log(`   Found ${searchResults.length} results`);
if (searchResults.length > 0) {
    const firstResult = searchResults[0];
    console.log(`   Example: ${firstResult.village.name}, ${firstResult.cell.name}, ${firstResult.sector.name}`);
}

// Example 5: Search only in districts
console.log('\n5. Searching for districts containing "nya":');
const districtSearch = locations.search('nya', 'district');
console.log(`   Found ${districtSearch.length} results`);
districtSearch.slice(0, 3).forEach(result => {
    console.log(`   - ${result.district.name} in ${result.province.name}`);
});

// Example 6: Get location by village code
console.log('\n6. Getting location details by village code (101010102):');
const villageLocation = locations.getLocationByVillageCode(101010102);
if (villageLocation) {
    console.log(`   Country: ${villageLocation.country.name}`);
    console.log(`   Province: ${villageLocation.province.name}`);
    console.log(`   District: ${villageLocation.district.name}`);
    console.log(`   Sector: ${villageLocation.sector.name}`);
    console.log(`   Cell: ${villageLocation.cell.name}`);
    console.log(`   Village: ${villageLocation.village.name}`);
}

// Example 7: Get statistics
console.log('\n7. Getting statistics:');
const stats = locations.getStats();
console.log(`   Total locations: ${stats.totalLocations}`);
console.log(`   Provinces: ${stats.provinces}`);
console.log(`   Districts: ${stats.districts}`);
console.log(`   Sectors: ${stats.sectors}`);
console.log(`   Cells: ${stats.cells}`);
console.log(`   Villages: ${stats.villages}`);

// Example 8: Get hierarchical tree (limited to one province for brevity)
console.log('\n8. Getting hierarchical tree for Kigali province:');
const hierarchy = locations.getHierarchy({ provinceCode: 1 });
if (hierarchy.length > 0) {
    const kigali = hierarchy[0];
    console.log(`   Province: ${kigali.name}`);
    console.log(`   Districts: ${kigali.districts.length}`);
    if (kigali.districts.length > 0) {
        const firstDistrict = kigali.districts[0];
        console.log(`   First district: ${firstDistrict.name}`);
        console.log(`   Sectors in ${firstDistrict.name}: ${firstDistrict.sectors.length}`);
    }
}

// Example 9: Building a cascading dropdown (common use case)
console.log('\n9. Simulating cascading dropdown selection:');
const selectedProvince = 1; // Kigali
const districtsForDropdown = locations.getDistricts(selectedProvince);
console.log(`   Step 1: User selects province ${selectedProvince}`);
console.log(`   Step 2: Load districts: ${districtsForDropdown.length} options`);

const selectedDistrict = 101; // Nyarugenge
const sectorsForDropdown = locations.getSectors(selectedDistrict);
console.log(`   Step 3: User selects district ${selectedDistrict}`);
console.log(`   Step 4: Load sectors: ${sectorsForDropdown.length} options`);

// Example 10: Get all villages in a specific sector
console.log('\n10. Getting all villages in a specific sector (010101):');
const cells = locations.getCells('010101');
console.log(`   Total cells in this sector: ${cells.length}`);
if (cells.length > 0) {
    const firstCell = cells[0];
    const villages = locations.getVillages(firstCell.code);
    console.log(`   Villages in ${firstCell.name} cell: ${villages.length}`);
    villages.slice(0, 3).forEach(village => {
        console.log(`   - ${village.name} (Code: ${village.code})`);
    });
}

console.log('\n=== Examples completed successfully! ===');
