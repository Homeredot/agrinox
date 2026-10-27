# Rwanda Locations - Easy Integration

A comprehensive, easy-to-use dataset containing Rwanda's complete administrative locations hierarchy with helper libraries for JavaScript, Python, and Java.

This repository provides a simple, downloadable solution for integrating Rwanda location data into your projects. Each location includes unique codes and follows the administrative hierarchy: **Country → Province → District → Sector → Cell → Village**.

## Features

- Complete Rwanda administrative data (222,000+ location records)
- Helper libraries for JavaScript/Node.js, Python, and Java
- Simple API with powerful querying capabilities
- Search functionality across all administrative levels
- Cascading location selection support
- Hierarchical tree structure generation
- Zero dependencies (except JSON parsing)
- Works offline - no API calls needed

## Need a Full Package?

For a more feature-rich, production-ready package with additional tools and TypeScript support, check out:
**[https://github.com/DevRW/rwanda-location](https://github.com/DevRW/rwanda-location)**

This repository is designed for simple integration and quick setup.

---

## Quick Start

### 1. Download the Data

Download both the data file and the helper library for your language:

```bash
# Download the locations data
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/locations.json

# For JavaScript
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/rwanda-locations.js

# For Python
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/rwanda_locations.py

# For Java
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/RwandaLocations.java
```

### 2. Use in Your Project

#### JavaScript/Node.js

```javascript
const RwandaLocations = require('./rwanda-locations');

const locations = new RwandaLocations();

// Get all provinces
const provinces = locations.getProvinces();
console.log(provinces);
// Output: [{ code: 1, name: 'KIGALI' }, { code: 2, name: 'SOUTHERN' }, ...]

// Get districts in Kigali province
const districts = locations.getDistricts(1);

// Search for locations
const results = locations.search('nyarugenge');

// Get complete hierarchy for a village
const location = locations.getLocationByVillageCode(101010102);
console.log(location);
// Output: {
//   country: { code: 'RWA', name: 'RWANDA' },
//   province: { code: 1, name: 'KIGALI' },
//   district: { code: 101, name: 'Nyarugenge' },
//   sector: { code: '010101', name: 'Gitega' },
//   cell: { code: 1010101, name: 'Akabahizi' },
//   village: { code: 101010102, name: 'Gihanga' }
// }
```

#### Python

```python
from rwanda_locations import RwandaLocations

locations = RwandaLocations()

# Get all provinces
provinces = locations.get_provinces()
print(provinces)
# Output: [{'code': 1, 'name': 'KIGALI'}, {'code': 2, 'name': 'SOUTHERN'}, ...]

# Get districts in Kigali province
districts = locations.get_districts(province_code=1)

# Search for locations
results = locations.search('nyarugenge')

# Get complete hierarchy for a village
location = locations.get_location_by_village_code(101010102)
```

#### Java

```java
import java.io.IOException;

public class Main {
    public static void main(String[] args) throws IOException {
        RwandaLocations locations = new RwandaLocations();

        // Get all provinces
        var provinces = locations.getProvinces();
        System.out.println(provinces);

        // Get districts in Kigali province
        var districts = locations.getDistricts(1);

        // Search for locations
        var results = locations.search("nyarugenge", "all");

        // Get complete hierarchy for a village
        var location = locations.getLocationByVillageCode(101010102);
    }
}
```

**Note for Java**: Add `org.json` dependency to your project:
```xml
<!-- Maven -->
<dependency>
    <groupId>org.json</groupId>
    <artifactId>json</artifactId>
    <version>20230227</version>
</dependency>
```

```gradle
// Gradle
implementation 'org.json:json:20230227'
```

---

## Data Structure

Each location record in `locations.json` contains:

```json
{
  "id": "fdf89758-99f0-4b6d-a793-e72f274c0fa1",
  "country_code": "RWA",
  "country_name": "RWANDA",
  "province_code": 1,
  "province_name": "KIGALI",
  "district_code": 101,
  "district_name": "Nyarugenge",
  "sector_code": "010101",
  "sector_name": "Gitega",
  "cell_code": 1010101,
  "cell_name": "Akabahizi",
  "village_code": 101010102,
  "village_name": "Gihanga"
}
```

---

## API Reference

### JavaScript API

#### `getProvinces()`
Get all unique provinces.
```javascript
const provinces = locations.getProvinces();
// Returns: [{ code: 1, name: 'KIGALI' }, ...]
```

#### `getDistricts(provinceCode?)`
Get all districts, optionally filtered by province.
```javascript
const allDistricts = locations.getDistricts();
const kigaliDistricts = locations.getDistricts(1);
```

#### `getSectors(districtCode?)`
Get all sectors, optionally filtered by district.
```javascript
const allSectors = locations.getSectors();
const nyarugenSectors = locations.getSectors(101);
```

#### `getCells(sectorCode?)`
Get all cells, optionally filtered by sector.
```javascript
const allCells = locations.getCells();
const sectorCells = locations.getCells('010101');
```

#### `getVillages(cellCode?)`
Get all villages, optionally filtered by cell.
```javascript
const allVillages = locations.getVillages();
const cellVillages = locations.getVillages(1010101);
```

#### `search(searchTerm, level?)`
Search locations by name (case-insensitive).
```javascript
// Search all levels
const results = locations.search('kigali');

// Search only districts
const districtResults = locations.search('nya', 'district');

// Levels: 'province', 'district', 'sector', 'cell', 'village', 'all' (default)
```

#### `getLocationByVillageCode(villageCode)`
Get complete location hierarchy for a specific village.
```javascript
const location = locations.getLocationByVillageCode(101010102);
// Returns full hierarchy from country to village
```

#### `getHierarchy(options?)`
Get hierarchical tree structure.
```javascript
// Get full hierarchy
const fullTree = locations.getHierarchy();

// Get hierarchy for specific province
const kigaliTree = locations.getHierarchy({ provinceCode: 1 });

// Filter by district
const districtTree = locations.getHierarchy({
  provinceCode: 1,
  districtCode: 101
});
```

#### `getStats()`
Get statistics about the dataset.
```javascript
const stats = locations.getStats();
// Returns: {
//   totalLocations: 222630,
//   provinces: 5,
//   districts: 30,
//   sectors: 416,
//   cells: 2148,
//   villages: 14837
// }
```

### Python API

All methods are similar to JavaScript but use Python naming conventions:

- `get_provinces()`
- `get_districts(province_code=None)`
- `get_sectors(district_code=None)`
- `get_cells(sector_code=None)`
- `get_villages(cell_code=None)`
- `search(search_term, level='all')`
- `get_location_by_village_code(village_code)`
- `get_hierarchy(province_code=None, district_code=None, ...)`
- `get_stats()`

### Java API

All methods are similar to JavaScript but use Java naming conventions and types:

- `List<Map<String, Object>> getProvinces()`
- `List<Map<String, Object>> getDistricts(Integer provinceCode)`
- `List<Map<String, Object>> getSectors(Integer districtCode)`
- `List<Map<String, Object>> getCells(String sectorCode)`
- `List<Map<String, Object>> getVillages(Integer cellCode)`
- `List<Map<String, Object>> search(String searchTerm, String level)`
- `Map<String, Object> getLocationByVillageCode(int villageCode)`
- `Map<String, Integer> getStats()`

---

## Common Use Cases

### 1. Cascading Dropdown Menus

```javascript
// JavaScript example
const locations = new RwandaLocations();

// Step 1: Load provinces for first dropdown
const provinces = locations.getProvinces();

// Step 2: User selects province, load districts
const selectedProvinceCode = 1; // Kigali
const districts = locations.getDistricts(selectedProvinceCode);

// Step 3: User selects district, load sectors
const selectedDistrictCode = 101; // Nyarugenge
const sectors = locations.getSectors(selectedDistrictCode);

// Continue for cells and villages...
```

### 2. Location Search

```javascript
// Search across all levels
const searchResults = locations.search('kigali');

// Search only in specific level
const provinces = locations.search('kigali', 'province');
const districts = locations.search('nyarugenge', 'district');
const villages = locations.search('gihanga', 'village');
```

### 3. Autocomplete/Typeahead

```python
def autocomplete(user_input, level='all'):
    locations = RwandaLocations()
    return locations.search(user_input, level)

# Use in your autocomplete endpoint
suggestions = autocomplete('kig')  # Returns matching locations
```

### 4. Address Validation

```javascript
function validateAddress(villageCode) {
    const locations = new RwandaLocations();
    const location = locations.getLocationByVillageCode(villageCode);
    return location !== null;
}
```

### 5. Generate Location Hierarchy

```python
# Get full tree structure for data visualization
locations = RwandaLocations()
hierarchy = locations.get_hierarchy()

# Or get specific province tree
kigali_tree = locations.get_hierarchy(province_code=1)
```

---

## Examples

Complete working examples are available in the `examples/` directory:

- **JavaScript**: `examples/javascript-example.js`
- **Python**: `examples/python-example.py`
- **Java**: `examples/JavaExample.java`

Run them to see all features in action:

```bash
# JavaScript
node examples/javascript-example.js

# Python
python examples/python-example.py

# Java (with org.json in classpath)
javac -cp .:json-20230227.jar examples/JavaExample.java RwandaLocations.java
java -cp .:json-20230227.jar examples.JavaExample
```

---

## Data Coverage

The dataset includes:
- **1** Country (Rwanda)
- **5** Provinces
- **30** Districts
- **416** Sectors
- **2,148** Cells
- **14,837** Villages
- **222,630+** Total location records

---

## Performance Tips

### Caching
The libraries automatically cache frequently accessed data (like provinces) to improve performance. The data is loaded only once when first accessed.

### Large Datasets
If you're working with the full dataset in memory-constrained environments, consider:
- Loading only the levels you need
- Using the search function with specific level filters
- Implementing server-side pagination for large result sets

### File Size
The `locations.json` file is approximately 50MB. For web applications, consider:
- Loading it server-side instead of client-side
- Creating a REST API wrapper around the library
- Using the full package at [DevRW/rwanda-location](https://github.com/DevRW/rwanda-location) which includes optimized builds

---

## Browser Usage

For JavaScript in browsers, you can use the library without Node.js:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Rwanda Locations</title>
</head>
<body>
    <script src="rwanda-locations.js"></script>
    <script>
        // Note: You'll need to modify the library to load JSON via fetch
        // or include the data directly in the HTML

        fetch('locations.json')
            .then(res => res.json())
            .then(data => {
                // Modify RwandaLocations to accept data directly
                const locations = new RwandaLocations();
                locations.data = data;

                const provinces = locations.getProvinces();
                console.log(provinces);
            });
    </script>
</body>
</html>
```

---

## Contributing

Contributions are welcome! If you find any issues or want to improve the libraries:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Make your changes
4. Test thoroughly
5. Submit a Pull Request

---

## Data Source

This data is sourced from [DevRW/rwanda-location](https://github.com/DevRW/rwanda-location/blob/develop/src/db/locations.json) and is kept up-to-date with official Rwanda administrative divisions.

---

## License

MIT License - Feel free to use this in your projects!

---

## Support

If you encounter any issues:

1. Check the [examples/](examples/) directory for working code
2. Review the API reference above
3. Open an issue on GitHub with details about your problem

---

## Related Projects

- **[DevRW/rwanda-location](https://github.com/DevRW/rwanda-location)** - Full-featured package with TypeScript support, CLI tools, and more

---

## Changelog

### v2.0.0 (2025)
- Complete rebuild with new data structure
- Added helper libraries for JavaScript, Python, and Java
- Added comprehensive search functionality
- Added hierarchical tree generation
- Added 222,000+ location records with unique codes
- Added complete API documentation and examples

### v1.0.0
- Initial release with basic JSON structure

---

Made with ❤️ for developers working with Rwanda location data
