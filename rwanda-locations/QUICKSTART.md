# Quick Start Guide

Get started with Rwanda Locations in 3 simple steps!

## Step 1: Download

Choose your language and download the files:

### JavaScript/Node.js
```bash
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/locations.json
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/rwanda-locations.js
```

### Python
```bash
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/locations.json
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/rwanda_locations.py
```

### Java
```bash
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/locations.json
curl -O https://raw.githubusercontent.com/jnkindi/rwanda-locations-json/master/RwandaLocations.java
```

For Java, also add this dependency to your `pom.xml`:
```xml
<dependency>
    <groupId>org.json</groupId>
    <artifactId>json</artifactId>
    <version>20230227</version>
</dependency>
```

## Step 2: Create Your File

### JavaScript (app.js)
```javascript
const RwandaLocations = require('./rwanda-locations');

const locations = new RwandaLocations();

// Get all provinces
const provinces = locations.getProvinces();
console.log('Provinces:', provinces);

// Get districts in Kigali
const districts = locations.getDistricts(1);
console.log('Kigali Districts:', districts);

// Search for a location
const results = locations.search('nyarugenge');
console.log('Search results:', results.length);
```

### Python (app.py)
```python
from rwanda_locations import RwandaLocations

locations = RwandaLocations()

# Get all provinces
provinces = locations.get_provinces()
print('Provinces:', provinces)

# Get districts in Kigali
districts = locations.get_districts(province_code=1)
print('Kigali Districts:', districts)

# Search for a location
results = locations.search('nyarugenge')
print('Search results:', len(results))
```

### Java (App.java)
```java
import java.io.IOException;

public class App {
    public static void main(String[] args) throws IOException {
        RwandaLocations locations = new RwandaLocations();

        // Get all provinces
        var provinces = locations.getProvinces();
        System.out.println("Provinces: " + provinces);

        // Get districts in Kigali
        var districts = locations.getDistricts(1);
        System.out.println("Kigali Districts: " + districts);

        // Search for a location
        var results = locations.search("nyarugenge", "all");
        System.out.println("Search results: " + results.size());
    }
}
```

## Step 3: Run It!

### JavaScript
```bash
node app.js
```

### Python
```bash
python app.py
```

### Java
```bash
javac -cp .:json-20230227.jar App.java RwandaLocations.java
java -cp .:json-20230227.jar App
```

## Common Tasks

### Build a Cascading Dropdown

```javascript
// JavaScript example
const locations = new RwandaLocations();

// Step 1: Show provinces
const provinces = locations.getProvinces();
// Display in dropdown

// Step 2: User selects province (e.g., Kigali = 1)
const districts = locations.getDistricts(1);
// Display districts in second dropdown

// Step 3: User selects district (e.g., Nyarugenge = 101)
const sectors = locations.getSectors(101);
// Display sectors in third dropdown
```

### Search for a Location

```python
# Python example
locations = RwandaLocations()

# Search all levels
all_results = locations.search('kigali')

# Search only districts
district_results = locations.search('kigali', 'district')

# Search only villages
village_results = locations.search('gihanga', 'village')
```

### Get Full Location Details

```java
// Java example
RwandaLocations locations = new RwandaLocations();

// Get complete hierarchy for a village
var location = locations.getLocationByVillageCode(101010102);
System.out.println("Province: " + location.get("province"));
System.out.println("District: " + location.get("district"));
System.out.println("Sector: " + location.get("sector"));
System.out.println("Cell: " + location.get("cell"));
System.out.println("Village: " + location.get("village"));
```

## Need More?

- See full documentation in [README.md](README.md)
- Check working examples in the [examples/](examples/) directory
- For a full-featured package: [DevRW/rwanda-location](https://github.com/DevRW/rwanda-location)

## API Quick Reference

| Method | Description | Example |
|--------|-------------|---------|
| `getProvinces()` | Get all provinces | `locations.getProvinces()` |
| `getDistricts(code)` | Get districts by province | `locations.getDistricts(1)` |
| `getSectors(code)` | Get sectors by district | `locations.getSectors(101)` |
| `getCells(code)` | Get cells by sector | `locations.getCells('010101')` |
| `getVillages(code)` | Get villages by cell | `locations.getVillages(1010101)` |
| `search(term, level)` | Search locations | `locations.search('kigali', 'all')` |
| `getLocationByVillageCode(code)` | Get full hierarchy | `locations.getLocationByVillageCode(101010102)` |
| `getStats()` | Get data statistics | `locations.getStats()` |

That's it! You're ready to use Rwanda Locations in your project!
