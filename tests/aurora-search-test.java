import com.aurora.gplayapi.Item;
import com.aurora.gplayapi.ListResponse;
import com.aurora.gplayapi.data.models.AuthData;
import com.aurora.gplayapi.data.models.StreamCluster;
import com.aurora.gplayapi.exceptions.GooglePlayException;
import com.google.gson.JsonParser;
import com.aurora.gplayapi.helpers.SearchHelper;
import com.aurora.gplayapi.data.providers.DeviceInfoProvider;
import java.util.List;
import java.util.Locale;
import java.util.Properties;

class AuroraSearchTest {
    public static void main(String[] args) throws Exception {
        var properties = new Properties();
        properties.load(AuroraSearchTest.class.getResourceAsStream("/gplayapi_poco_f1.properties"));
        properties.setProperty("Features", "android.hardware.vulkan.level=1,android.hardware.vulkan.version=4198400");
        var config = new DeviceInfoProvider(properties, "en_US").getDeviceConfigurationProto();
        if (!config.getSystemAvailableFeatureList().equals(List.of("android.hardware.vulkan.level", "android.hardware.vulkan.version"))
            || config.getDeviceFeature(0).getValue() != 1 || config.getDeviceFeature(1).getValue() != 4198400) {
            throw new AssertionError("Vulkan feature versions lost");
        }
        var auth = new AuthData("fixture", "", "", true, "", "", "", "", "", "", "", "", "", "", Locale.US, null, null);
        var exact = Item.newBuilder().setId("exact").addSubItem(
            Item.newBuilder().setId("com.termux").setTitle("Termux").setType(1));
        var related = Item.newBuilder().setId("related").addSubItem(
            Item.newBuilder().setId("org.example.related").setTitle("Related").setType(1));
        var response = ListResponse.newBuilder().setItem(Item.newBuilder().addSubItem(exact).addSubItem(related)).build();
        var bundle = new SearchHelper(auth).getStreamBundle(42, response);
        var packages = bundle.getStreamClusters().values().stream()
            .flatMap(cluster -> cluster.getClusterAppList().stream()).map(app -> app.getPackageName()).toList();
        if (!packages.equals(List.of("com.termux", "org.example.related"))) {
            throw new AssertionError("Search groups lost or reordered: " + packages);
        }
        var cursors = MainKt.class.getDeclaredMethod("pageCursors", String.class, List.class);
        cursors.setAccessible(true);
        var cluster = new StreamCluster(1, "", "", "cluster-next", "", List.of());
        var clusterOnly = JsonParser.parseString(cursors.invoke(null, "", List.of(cluster)).toString());
        if (!clusterOnly.equals(JsonParser.parseString("""
            [{"kind":"cluster","url":"cluster-next"}]
            """))) {
            throw new AssertionError("Cluster continuation dropped: " + clusterOnly);
        }
        var combined = JsonParser.parseString(cursors.invoke(null, "bundle-next", List.of(cluster)).toString());
        if (!combined.equals(JsonParser.parseString("""
            [{"kind":"bundle","url":"bundle-next"},{"kind":"cluster","url":"cluster-next"}]
            """))) {
            throw new AssertionError("Bundle/cluster continuations lost: " + combined);
        }
        if (!cursors.invoke(null, "", List.of(StreamCluster.Companion.getEMPTY())).toString().equals("[]")) {
            throw new AssertionError("Exhausted cluster emitted a continuation");
        }
        var errors = MainKt.class.getDeclaredMethod("errorResponse", Exception.class);
        errors.setAccessible(true);
        var expired = JsonParser.parseString(errors.invoke(null,
            new GooglePlayException.AuthException(401, "secret-token")).toString()).getAsJsonObject();
        if (!expired.get("error").getAsString().equals("authentication")
            || expired.get("status").getAsInt() != 401 || expired.toString().contains("secret-token")) {
            throw new AssertionError("Expired session cannot recover safely: " + expired);
        }
        var limited = JsonParser.parseString(errors.invoke(null,
            new GooglePlayException.Server(429, "secret-token")).toString()).getAsJsonObject();
        if (!limited.get("error").getAsString().equals("rate_limit")) {
            throw new AssertionError("Rate limiting classification changed: " + limited);
        }
        System.out.println("Aurora helper regression tests passed");
    }
}
