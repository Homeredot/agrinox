/**
 * Java Integration Examples
 *
 * This file demonstrates how to use the Rwanda Locations library in Java
 *
 * To compile and run:
 * 1. Make sure you have the org.json library in your classpath
 * 2. Place RwandaLocations.java and locations.json in the same directory
 * 3. Compile: javac -cp .:json-20230227.jar JavaExample.java RwandaLocations.java
 * 4. Run: java -cp .:json-20230227.jar JavaExample
 */

import java.io.IOException;
import java.util.List;
import java.util.Map;

public class JavaExample {

    public static void main(String[] args) {
        try {
            // Create an instance
            RwandaLocations locations = new RwandaLocations("locations.json");

            System.out.println("=== Rwanda Locations - Java Examples ===\n");

            // Example 1: Get all provinces
            System.out.println("1. Getting all provinces:");
            List<Map<String, Object>> provinces = locations.getProvinces();
            System.out.println("   Total provinces: " + provinces.size());
            for (Map<String, Object> province : provinces) {
                System.out.println("   - " + province.get("name") + " (Code: " + province.get("code") + ")");
            }

            // Example 2: Get districts in a specific province (Kigali = 1)
            System.out.println("\n2. Getting districts in Kigali province:");
            List<Map<String, Object>> kigaliDistricts = locations.getDistricts(1);
            System.out.println("   Total districts in Kigali: " + kigaliDistricts.size());
            for (int i = 0; i < Math.min(3, kigaliDistricts.size()); i++) {
                Map<String, Object> district = kigaliDistricts.get(i);
                System.out.println("   - " + district.get("name") + " (Code: " + district.get("code") + ")");
            }

            // Example 3: Get sectors in a specific district
            System.out.println("\n3. Getting sectors in Nyarugenge district (Code: 101):");
            List<Map<String, Object>> sectors = locations.getSectors(101);
            System.out.println("   Total sectors: " + sectors.size());
            for (int i = 0; i < Math.min(3, sectors.size()); i++) {
                Map<String, Object> sector = sectors.get(i);
                System.out.println("   - " + sector.get("name") + " (Code: " + sector.get("code") + ")");
            }

            // Example 4: Search for locations
            System.out.println("\n4. Searching for locations containing \"kigali\":");
            List<Map<String, Object>> searchResults = locations.search("kigali", "all");
            System.out.println("   Found " + searchResults.size() + " results");
            if (!searchResults.isEmpty()) {
                Map<String, Object> firstResult = searchResults.get(0);
                @SuppressWarnings("unchecked")
                Map<String, Object> village = (Map<String, Object>) firstResult.get("village");
                @SuppressWarnings("unchecked")
                Map<String, Object> cell = (Map<String, Object>) firstResult.get("cell");
                @SuppressWarnings("unchecked")
                Map<String, Object> sector = (Map<String, Object>) firstResult.get("sector");

                System.out.println("   Example: " + village.get("name") + ", " +
                                 cell.get("name") + ", " + sector.get("name"));
            }

            // Example 5: Search only in districts
            System.out.println("\n5. Searching for districts containing \"nya\":");
            List<Map<String, Object>> districtSearch = locations.search("nya", "district");
            System.out.println("   Found " + districtSearch.size() + " results");
            for (int i = 0; i < Math.min(3, districtSearch.size()); i++) {
                Map<String, Object> result = districtSearch.get(i);
                @SuppressWarnings("unchecked")
                Map<String, Object> district = (Map<String, Object>) result.get("district");
                @SuppressWarnings("unchecked")
                Map<String, Object> province = (Map<String, Object>) result.get("province");

                System.out.println("   - " + district.get("name") + " in " + province.get("name"));
            }

            // Example 6: Get location by village code
            System.out.println("\n6. Getting location details by village code (101010102):");
            Map<String, Object> villageLocation = locations.getLocationByVillageCode(101010102);
            if (villageLocation != null) {
                @SuppressWarnings("unchecked")
                Map<String, Object> country = (Map<String, Object>) villageLocation.get("country");
                @SuppressWarnings("unchecked")
                Map<String, Object> province = (Map<String, Object>) villageLocation.get("province");
                @SuppressWarnings("unchecked")
                Map<String, Object> district = (Map<String, Object>) villageLocation.get("district");
                @SuppressWarnings("unchecked")
                Map<String, Object> sectorObj = (Map<String, Object>) villageLocation.get("sector");
                @SuppressWarnings("unchecked")
                Map<String, Object> cellObj = (Map<String, Object>) villageLocation.get("cell");
                @SuppressWarnings("unchecked")
                Map<String, Object> villageObj = (Map<String, Object>) villageLocation.get("village");

                System.out.println("   Country: " + country.get("name"));
                System.out.println("   Province: " + province.get("name"));
                System.out.println("   District: " + district.get("name"));
                System.out.println("   Sector: " + sectorObj.get("name"));
                System.out.println("   Cell: " + cellObj.get("name"));
                System.out.println("   Village: " + villageObj.get("name"));
            }

            // Example 7: Get statistics
            System.out.println("\n7. Getting statistics:");
            Map<String, Integer> stats = locations.getStats();
            System.out.println("   Total locations: " + stats.get("total_locations"));
            System.out.println("   Provinces: " + stats.get("provinces"));
            System.out.println("   Districts: " + stats.get("districts"));
            System.out.println("   Sectors: " + stats.get("sectors"));
            System.out.println("   Cells: " + stats.get("cells"));
            System.out.println("   Villages: " + stats.get("villages"));

            // Example 8: Building a cascading dropdown (common use case)
            System.out.println("\n8. Simulating cascading dropdown selection:");
            int selectedProvince = 1; // Kigali
            List<Map<String, Object>> districtsForDropdown = locations.getDistricts(selectedProvince);
            System.out.println("   Step 1: User selects province " + selectedProvince);
            System.out.println("   Step 2: Load districts: " + districtsForDropdown.size() + " options");

            int selectedDistrict = 101; // Nyarugenge
            List<Map<String, Object>> sectorsForDropdown = locations.getSectors(selectedDistrict);
            System.out.println("   Step 3: User selects district " + selectedDistrict);
            System.out.println("   Step 4: Load sectors: " + sectorsForDropdown.size() + " options");

            // Example 9: Get all villages in a specific sector
            System.out.println("\n9. Getting all villages in a specific sector (010101):");
            List<Map<String, Object>> cells = locations.getCells("010101");
            System.out.println("   Total cells in this sector: " + cells.size());
            if (!cells.isEmpty()) {
                Map<String, Object> firstCell = cells.get(0);
                Integer cellCode = (Integer) firstCell.get("code");
                List<Map<String, Object>> villages = locations.getVillages(cellCode);
                System.out.println("   Villages in " + firstCell.get("name") + " cell: " + villages.size());
                for (int i = 0; i < Math.min(3, villages.size()); i++) {
                    Map<String, Object> villageItem = villages.get(i);
                    System.out.println("   - " + villageItem.get("name") + " (Code: " + villageItem.get("code") + ")");
                }
            }

            // Example 10: Get all districts (no filter)
            System.out.println("\n10. Getting all districts (no filter):");
            List<Map<String, Object>> allDistricts = locations.getDistricts(null);
            System.out.println("   Total districts in Rwanda: " + allDistricts.size());
            System.out.println("   First 5 districts:");
            for (int i = 0; i < Math.min(5, allDistricts.size()); i++) {
                Map<String, Object> district = allDistricts.get(i);
                System.out.println("   - " + district.get("name") + " in " + district.get("province_name"));
            }

            System.out.println("\n=== Examples completed successfully! ===");

        } catch (IOException e) {
            System.err.println("Error loading data: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
