/**
 * Rwanda Locations - Easy Integration Library
 *
 * A simple, powerful utility to work with Rwanda's administrative locations.
 * Supports: Provinces, Districts, Sectors, Cells, and Villages
 *
 * For a more feature-rich package version, visit:
 * https://github.com/DevRW/rwanda-location
 *
 * Dependencies: org.json (JSON-java)
 * Add to your pom.xml or build.gradle:
 * Maven: <dependency>
 *          <groupId>org.json</groupId>
 *          <artifactId>json</artifactId>
 *          <version>20230227</version>
 *        </dependency>
 * Gradle: implementation 'org.json:json:20230227'
 */

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.*;
import java.util.stream.Collectors;

public class RwandaLocations {
    private JSONArray data;
    private Map<String, List<Map<String, Object>>> cache;
    private String dataFilePath;

    /**
     * Constructor with default data file path
     */
    public RwandaLocations() {
        this("locations.json");
    }

    /**
     * Constructor with custom data file path
     *
     * @param dataFilePath Path to the locations.json file
     */
    public RwandaLocations(String dataFilePath) {
        this.dataFilePath = dataFilePath;
        this.data = null;
        this.cache = new HashMap<>();
    }

    /**
     * Load the locations data from JSON file
     *
     * @return this instance for method chaining
     * @throws IOException if file cannot be read
     */
    public RwandaLocations load() throws IOException {
        if (data == null) {
            String content = new String(Files.readAllBytes(Paths.get(dataFilePath)));
            data = new JSONArray(content);
        }
        return this;
    }

    /**
     * Get all provinces
     *
     * @return List of unique provinces
     * @throws IOException if data cannot be loaded
     */
    public List<Map<String, Object>> getProvinces() throws IOException {
        if (cache.containsKey("provinces")) {
            return cache.get("provinces");
        }

        load();
        Map<Integer, Map<String, Object>> provinces = new HashMap<>();

        for (int i = 0; i < data.length(); i++) {
            JSONObject location = data.getJSONObject(i);
            int code = location.getInt("province_code");

            if (!provinces.containsKey(code)) {
                Map<String, Object> province = new HashMap<>();
                province.put("code", code);
                province.put("name", location.getString("province_name"));
                provinces.put(code, province);
            }
        }

        List<Map<String, Object>> result = new ArrayList<>(provinces.values());
        result.sort(Comparator.comparingInt(p -> (Integer) p.get("code")));
        cache.put("provinces", result);

        return result;
    }

    /**
     * Get all districts, optionally filtered by province
     *
     * @param provinceCode Optional province code to filter by (null for all)
     * @return List of districts
     * @throws IOException if data cannot be loaded
     */
    public List<Map<String, Object>> getDistricts(Integer provinceCode) throws IOException {
        load();
        Map<Integer, Map<String, Object>> districts = new HashMap<>();

        for (int i = 0; i < data.length(); i++) {
            JSONObject location = data.getJSONObject(i);

            if (provinceCode != null && location.getInt("province_code") != provinceCode) {
                continue;
            }

            int code = location.getInt("district_code");

            if (!districts.containsKey(code)) {
                Map<String, Object> district = new HashMap<>();
                district.put("code", code);
                district.put("name", location.getString("district_name"));
                district.put("province_code", location.getInt("province_code"));
                district.put("province_name", location.getString("province_name"));
                districts.put(code, district);
            }
        }

        List<Map<String, Object>> result = new ArrayList<>(districts.values());
        result.sort(Comparator.comparingInt(d -> (Integer) d.get("code")));

        return result;
    }

    /**
     * Get all sectors, optionally filtered by district
     *
     * @param districtCode Optional district code to filter by (null for all)
     * @return List of sectors
     * @throws IOException if data cannot be loaded
     */
    public List<Map<String, Object>> getSectors(Integer districtCode) throws IOException {
        load();
        Map<String, Map<String, Object>> sectors = new HashMap<>();

        for (int i = 0; i < data.length(); i++) {
            JSONObject location = data.getJSONObject(i);

            if (districtCode != null && location.getInt("district_code") != districtCode) {
                continue;
            }

            String code = location.getString("sector_code");

            if (!sectors.containsKey(code)) {
                Map<String, Object> sector = new HashMap<>();
                sector.put("code", code);
                sector.put("name", location.getString("sector_name"));
                sector.put("district_code", location.getInt("district_code"));
                sector.put("district_name", location.getString("district_name"));
                sector.put("province_code", location.getInt("province_code"));
                sector.put("province_name", location.getString("province_name"));
                sectors.put(code, sector);
            }
        }

        List<Map<String, Object>> result = new ArrayList<>(sectors.values());
        result.sort(Comparator.comparing(s -> (String) s.get("code")));

        return result;
    }

    /**
     * Get all cells, optionally filtered by sector
     *
     * @param sectorCode Optional sector code to filter by (null for all)
     * @return List of cells
     * @throws IOException if data cannot be loaded
     */
    public List<Map<String, Object>> getCells(String sectorCode) throws IOException {
        load();
        Map<Integer, Map<String, Object>> cells = new HashMap<>();

        for (int i = 0; i < data.length(); i++) {
            JSONObject location = data.getJSONObject(i);

            if (sectorCode != null && !location.getString("sector_code").equals(sectorCode)) {
                continue;
            }

            int code = location.getInt("cell_code");

            if (!cells.containsKey(code)) {
                Map<String, Object> cell = new HashMap<>();
                cell.put("code", code);
                cell.put("name", location.getString("cell_name"));
                cell.put("sector_code", location.getString("sector_code"));
                cell.put("sector_name", location.getString("sector_name"));
                cell.put("district_code", location.getInt("district_code"));
                cell.put("district_name", location.getString("district_name"));
                cell.put("province_code", location.getInt("province_code"));
                cell.put("province_name", location.getString("province_name"));
                cells.put(code, cell);
            }
        }

        List<Map<String, Object>> result = new ArrayList<>(cells.values());
        result.sort(Comparator.comparingInt(c -> (Integer) c.get("code")));

        return result;
    }

    /**
     * Get all villages, optionally filtered by cell
     *
     * @param cellCode Optional cell code to filter by (null for all)
     * @return List of villages
     * @throws IOException if data cannot be loaded
     */
    public List<Map<String, Object>> getVillages(Integer cellCode) throws IOException {
        load();
        Map<Integer, Map<String, Object>> villages = new HashMap<>();

        for (int i = 0; i < data.length(); i++) {
            JSONObject location = data.getJSONObject(i);

            if (cellCode != null && location.getInt("cell_code") != cellCode) {
                continue;
            }

            int code = location.getInt("village_code");

            if (!villages.containsKey(code)) {
                Map<String, Object> village = new HashMap<>();
                village.put("code", code);
                village.put("name", location.getString("village_name"));
                village.put("cell_code", location.getInt("cell_code"));
                village.put("cell_name", location.getString("cell_name"));
                village.put("sector_code", location.getString("sector_code"));
                village.put("sector_name", location.getString("sector_name"));
                village.put("district_code", location.getInt("district_code"));
                village.put("district_name", location.getString("district_name"));
                village.put("province_code", location.getInt("province_code"));
                village.put("province_name", location.getString("province_name"));
                villages.put(code, village);
            }
        }

        List<Map<String, Object>> result = new ArrayList<>(villages.values());
        result.sort(Comparator.comparingInt(v -> (Integer) v.get("code")));

        return result;
    }

    /**
     * Search locations by name (case-insensitive)
     *
     * @param searchTerm Search term
     * @param level      Level to search: "province", "district", "sector", "cell", "village", or "all"
     * @return List of matching locations
     * @throws IOException if data cannot be loaded
     */
    public List<Map<String, Object>> search(String searchTerm, String level) throws IOException {
        load();
        String term = searchTerm.toLowerCase();
        List<Map<String, Object>> results = new ArrayList<>();
        Set<String> seen = new HashSet<>();

        for (int i = 0; i < data.length(); i++) {
            JSONObject location = data.getJSONObject(i);

            boolean matches =
                    (level.equals("all") || level.equals("province")) && location.getString("province_name").toLowerCase().contains(term) ||
                            (level.equals("all") || level.equals("district")) && location.getString("district_name").toLowerCase().contains(term) ||
                            (level.equals("all") || level.equals("sector")) && location.getString("sector_name").toLowerCase().contains(term) ||
                            (level.equals("all") || level.equals("cell")) && location.getString("cell_name").toLowerCase().contains(term) ||
                            (level.equals("all") || level.equals("village")) && location.getString("village_name").toLowerCase().contains(term);

            if (matches) {
                String key = String.format("%d-%d-%s-%d-%d",
                        location.getInt("province_code"),
                        location.getInt("district_code"),
                        location.getString("sector_code"),
                        location.getInt("cell_code"),
                        location.getInt("village_code"));

                if (!seen.contains(key)) {
                    seen.add(key);

                    Map<String, Object> result = new HashMap<>();
                    result.put("province", createSimpleMap(location.getInt("province_code"), location.getString("province_name")));
                    result.put("district", createSimpleMap(location.getInt("district_code"), location.getString("district_name")));
                    result.put("sector", createSimpleMap(location.getString("sector_code"), location.getString("sector_name")));
                    result.put("cell", createSimpleMap(location.getInt("cell_code"), location.getString("cell_name")));
                    result.put("village", createSimpleMap(location.getInt("village_code"), location.getString("village_name")));

                    results.add(result);
                }
            }
        }

        return results;
    }

    /**
     * Get location hierarchy for a specific village
     *
     * @param villageCode Village code
     * @return Complete location hierarchy or null if not found
     * @throws IOException if data cannot be loaded
     */
    public Map<String, Object> getLocationByVillageCode(int villageCode) throws IOException {
        load();

        for (int i = 0; i < data.length(); i++) {
            JSONObject location = data.getJSONObject(i);

            if (location.getInt("village_code") == villageCode) {
                Map<String, Object> result = new HashMap<>();
                result.put("country", createSimpleMap(location.getString("country_code"), location.getString("country_name")));
                result.put("province", createSimpleMap(location.getInt("province_code"), location.getString("province_name")));
                result.put("district", createSimpleMap(location.getInt("district_code"), location.getString("district_name")));
                result.put("sector", createSimpleMap(location.getString("sector_code"), location.getString("sector_name")));
                result.put("cell", createSimpleMap(location.getInt("cell_code"), location.getString("cell_name")));
                result.put("village", createSimpleMap(location.getInt("village_code"), location.getString("village_name")));

                return result;
            }
        }

        return null;
    }

    /**
     * Get statistics about the data
     *
     * @return Map with statistics
     * @throws IOException if data cannot be loaded
     */
    public Map<String, Integer> getStats() throws IOException {
        load();

        Map<String, Integer> stats = new HashMap<>();
        stats.put("total_locations", data.length());
        stats.put("provinces", getProvinces().size());
        stats.put("districts", getDistricts(null).size());
        stats.put("sectors", getSectors(null).size());
        stats.put("cells", getCells(null).size());
        stats.put("villages", getVillages(null).size());

        return stats;
    }

    /**
     * Helper method to create a simple map with code and name
     */
    private Map<String, Object> createSimpleMap(Object code, String name) {
        Map<String, Object> map = new HashMap<>();
        map.put("code", code);
        map.put("name", name);
        return map;
    }

    /**
     * Example usage
     */
    public static void main(String[] args) {
        try {
            RwandaLocations locations = new RwandaLocations();

            // Get all provinces
            List<Map<String, Object>> provinces = locations.getProvinces();
            System.out.println("Total Provinces: " + provinces.size());
            System.out.println("First Province: " + provinces.get(0));

            // Get statistics
            Map<String, Integer> stats = locations.getStats();
            System.out.println("\nStatistics: " + stats);

            // Search example
            List<Map<String, Object>> results = locations.search("kigali", "all");
            System.out.println("\nSearch results for 'kigali': " + results.size() + " results");

            // Get districts in Kigali province (code 1)
            List<Map<String, Object>> districts = locations.getDistricts(1);
            System.out.println("\nDistricts in Kigali: " + districts.size());

        } catch (IOException e) {
            System.err.println("Error loading data: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
