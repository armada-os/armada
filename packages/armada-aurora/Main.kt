// SPDX-License-Identifier: GPL-3.0-or-later
import com.aurora.gplayapi.data.models.App
import com.aurora.gplayapi.data.models.AuthData
import com.aurora.gplayapi.data.models.PlayFile
import com.aurora.gplayapi.data.models.StreamCluster
import com.aurora.gplayapi.helpers.AppDetailsHelper
import com.aurora.gplayapi.helpers.AuthHelper
import com.aurora.gplayapi.helpers.PurchaseHelper
import com.aurora.gplayapi.helpers.SearchHelper
import com.aurora.gplayapi.helpers.web.WebTopChartsHelper
import com.aurora.gplayapi.exceptions.GooglePlayException
import com.aurora.gplayapi.Constants
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import java.util.Locale
import java.util.Properties
import kotlinx.serialization.json.*

private class Failure(val code: String, override val message: String) : Exception(message)
private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true }
private fun JsonObject.text(key: String) = this[key]?.jsonPrimitive?.content ?: ""
private val packageName = Regex("[A-Za-z][A-Za-z0-9_]*(\\.[A-Za-z0-9_]+)+")

/** Advertise a bounded Android 11 profile for discovery, without claiming Google services. */
private fun profile() = Properties().apply {
    load(object {}.javaClass.getResourceAsStream("/gplayapi_poco_f1.properties"))
    setProperty("Platforms", "arm64-v8a")
    setProperty("Screen.Density", "320")
    setProperty("Screen.Width", "1080")
    setProperty("Screen.Height", "1920")
    setProperty("Locales", "en_US,en_AU,en")
    setProperty("GL.Version", "196609")
    setProperty("SharedLibraries", "android.test.base,android.test.mock,android.test.runner,org.apache.http.legacy")
    setProperty(
        "Features",
        listOf(
            "android.hardware.audio.low_latency",
            "android.hardware.audio.output",
            "android.hardware.ethernet",
            "android.hardware.faketouch",
            "android.hardware.gamepad",
            "android.hardware.microphone",
            "android.hardware.opengles.aep",
            "android.hardware.ram.normal",
            "android.hardware.screen.landscape",
            "android.hardware.screen.portrait",
            "android.hardware.touchscreen",
            "android.hardware.touchscreen.multitouch",
            "android.hardware.touchscreen.multitouch.distinct",
            "android.hardware.touchscreen.multitouch.jazzhand",
            "android.hardware.vulkan.compute",
            "android.hardware.vulkan.level=1",
            "android.hardware.vulkan.version=4198400",
            "android.hardware.wifi",
            "android.software.input_methods",
            "android.software.webview",
            "android.software.activities_on_secondary_displays",
        ).joinToString(",")
    )
}

/** Return public app metadata; authentication and download credentials stay in the helper. */
private fun summary(app: App) = buildJsonObject {
    put("package", app.packageName)
    put("restriction", app.restriction.name)
    put("name", app.displayName)
    put("description", app.shortDescription)
    put("icon", app.iconArtwork.url)
    put("developer", app.developerName)
    put("free", app.isFree)
    put("version", app.versionName)
    put("versionCode", app.versionCode)
    put("size", app.size)
}

/** Retain both bundle and cluster continuations, including on subsequent cluster pages. */
private fun pageCursors(bundleUrl: String, clusters: List<StreamCluster>) = buildJsonArray {
    if (bundleUrl.isNotBlank()) {
        add(buildJsonObject {
            put("kind", "bundle")
            put("url", bundleUrl)
        })
    }
    clusters.filter { it.hasNext() }.forEach { cluster ->
        add(buildJsonObject {
            put("kind", "cluster")
            put("url", cluster.clusterNextPageUrl)
        })
    }
}

private class Backend(private val dispenser: URI) {
    private val properties = profile()
    private var session: AuthData? = null
    private var authFailure: Failure? = null

    /** Reuse the anonymous session and cache failures until Store restarts the helper. */
    private fun authenticate(): AuthData {
        session?.let { return it }
        authFailure?.let { throw it }
        try {
            val body = json.encodeToString(properties.entries.associate {
                it.key.toString() to it.value.toString()
            })
            val request = HttpRequest.newBuilder(dispenser)
                .timeout(Duration.ofSeconds(45))
                .header("Content-Type", "application/json")
                .header("User-Agent", "com.aurora.store-4.8.4-76")
                .POST(HttpRequest.BodyPublishers.ofString(body))
                .build()
            val response = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(20))
                .build()
                .send(request, HttpResponse.BodyHandlers.ofString())
            if (response.statusCode() != 200) {
                throw Failure("authentication", "Anonymous authentication HTTP ${response.statusCode()}")
            }
            val account = json.parseToJsonElement(response.body()).jsonObject
            val email = account.text("email")
            val token = account.text("authToken")
            if (email.isBlank() || token.isBlank()) {
                throw Failure("authentication", "Invalid anonymous session response")
            }
            return AuthHelper.build(
                email, token, AuthHelper.Token.AUTH, true, properties, Locale.forLanguageTag("en-US")
            ).also { session = it }
        } catch (error: Exception) {
            val failure = error as? Failure ?: Failure("authentication", "Anonymous authentication failed")
            authFailure = failure
            throw failure
        }
    }

    /** Read the static profile without contacting the dispenser or Google Play. */
    private fun info() = buildJsonObject {
        put("library", "3.6.4")
        put("androidApi", properties.getProperty("Build.VERSION.SDK_INT").toInt())
        put("abis", properties.getProperty("Platforms"))
        put("density", properties.getProperty("Screen.Density").toInt())
        put("anonymous", true)
    }

    /** Filter public chart entries through the anonymous session's actual availability. */
    private fun browse(category: String) = run {
        val chart = WebTopChartsHelper()
            .with(Locale.forLanguageTag("en-US"))
            .getCluster(category, "apps_topselling_free")
        val available = AppDetailsHelper(authenticate())
            .getAppByPackageName(chart.clusterAppList.map { it.packageName })
            .associateBy { it.packageName }
        chart.copy(
            clusterAppList = chart.clusterAppList
                .mapNotNull { available[it.packageName] }
                .filter { it.restriction == Constants.Restriction.NOT_RESTRICTED }
        )
    }

    /** Return one search/chart page, preserving upstream order and continuation URLs. */
    private fun search(query: String, category: String, url: String, kind: String, browse: Boolean): JsonObject {
        val bundle = if (!browse && kind == "bundle") {
            SearchHelper(authenticate()).searchResults(query, url)
        } else {
            null
        }
        val clusters = when {
            bundle != null -> bundle.streamClusters.values.toList()
            browse && url.isEmpty() -> listOf(browse(category))
            else -> listOf(SearchHelper(authenticate()).nextStreamCluster(query, url))
        }
        return buildJsonObject {
            put("apps", JsonArray(clusters.flatMap { it.clusterAppList }
                .distinctBy { it.packageName }
                .map(::summary)))
            put("pages", pageCursors(bundle?.streamNextPageUrl.orEmpty(), clusters))
        }
    }

    /** Resolve free, unrestricted apps to one base APK and optional split APKs. */
    private fun resolve(pkg: String): JsonObject {
        val auth = authenticate()
        val app = AppDetailsHelper(auth).getAppByPackageName(pkg)
        if (app.restriction != Constants.Restriction.NOT_RESTRICTED) {
            throw Failure("unsupported", "App unavailable for this device or anonymous session")
        }
        if (!app.isFree) {
            throw Failure("unsupported", "Only free apps are supported")
        }
        val files = PurchaseHelper(auth).purchase(app.packageName, app.versionCode, app.offerType)
        if (files.count { it.type == PlayFile.Type.BASE } != 1 || files.any {
                it.type !in setOf(PlayFile.Type.BASE, PlayFile.Type.SPLIT)
            }) {
            throw Failure("unsupported", "Only base and split APK downloads are supported")
        }
        return buildJsonObject {
            put("app", summary(app))
            put("files", json.encodeToJsonElement(files))
        }
    }

    /** Validate the request before dispatch so malformed input never starts authentication. */
    fun handle(input: JsonObject): JsonElement {
        val operation = input.text("op")
        if (operation == "info") return info()
        if (operation !in setOf("search", "browse", "details", "resolve")) {
            throw Failure("request", "Unknown operation")
        }

        val query = input.text("query").trim()
        val pkg = input.text("package")
        val category = input.text("category")
        if (operation == "browse" && category !in setOf(
                "APPLICATION", "GAME", "TOOLS", "VIDEO_PLAYERS", "COMMUNICATION"
            )) {
            throw Failure("request", "Invalid category")
        }
        if (operation == "search" && (query.isEmpty() || query.length > 200)) {
            throw Failure("request", "Enter a search query of 1–200 characters")
        }
        if (operation !in setOf("search", "browse") && !packageName.matches(pkg)) {
            throw Failure("request", "Invalid package name")
        }

        val page = input["page"]?.jsonObject
        val url = page?.text("url") ?: ""
        if (url.isNotEmpty() && (url.startsWith("/") || ":" in url || url.length > 8192)) {
            throw Failure("request", "Invalid search page")
        }
        val kind = page?.text("kind") ?: "bundle"
        if (kind !in setOf("bundle", "cluster")) {
            throw Failure("request", "Invalid search page")
        }

        return when (operation) {
            "search", "browse" -> search(query, category, url, kind, operation == "browse")
            "details" -> summary(AppDetailsHelper(authenticate()).getAppByPackageName(pkg))
            else -> resolve(pkg)
        }
    }
}

/** Map upstream failures to safe messages without returning raw exceptions or response bodies. */
private fun errorResponse(error: Exception): JsonObject {
    val code = when (error) {
        is GooglePlayException.AuthException -> error.code
        is GooglePlayException.AppNotPurchased -> error.code
        is GooglePlayException.NotFound -> error.code
        is GooglePlayException.AppRemoved -> error.code
        is GooglePlayException.AppNotSupported -> error.code
        is GooglePlayException.EmptyDownloads -> error.code
        is GooglePlayException.Unknown -> error.code
        is GooglePlayException.Server -> error.code
        else -> null
    }
    val status = code?.takeIf { it in 100..599 }
    val failure = error as? Failure ?: when {
        error is GooglePlayException.AuthException -> Failure(
            "authentication", "Google Play authentication failed; retry in a minute"
        )
        error is GooglePlayException.AppNotSupported -> Failure(
            "unsupported", "Google Play does not offer this app for Lepton's device profile"
        )
        error is GooglePlayException.AppRemoved -> Failure(
            "unsupported", "This app is no longer available from Google Play"
        )
        error is GooglePlayException.AppNotPurchased && code != null && code < 100 -> Failure(
            "unsupported", "This app is unavailable to the anonymous session"
        )
        error is GooglePlayException.EmptyDownloads -> Failure(
            "unsupported", "No APK downloads are available"
        )
        code != null && code < 100 -> Failure("backend", "Google Play refused APK delivery (code $code)")
        else -> null
    }
    val errorCode = failure?.code ?: when {
        status == 429 -> "rate_limit"
        error is IllegalArgumentException -> "request"
        else -> "backend"
    }
    val message = failure?.message ?: when (status) {
        429 -> "Google Play is rate limited; retry in a minute"
        403, 404 -> "App unavailable for this device or anonymous session (HTTP $status)"
        null -> "Request failed"
        else -> "Google Play request failed (HTTP $status)"
    }
    return buildJsonObject {
        put("error", errorCode)
        put("message", message)
        if (status != null) put("status", status)
    }
}

/** Serve one JSON response per input line; stdout is reserved for the Store protocol. */
fun main() {
    val dispenser = URI(System.getenv("ARMADA_AURORA_DISPENSER") ?: "https://auroraoss.com/api/auth")
    require(dispenser.scheme == "https" || (dispenser.scheme == "http" && dispenser.host == "127.0.0.1"))
    val backend = Backend(dispenser)
    generateSequence(::readlnOrNull).forEach { line ->
        val result = try {
            backend.handle(json.parseToJsonElement(line).jsonObject)
        } catch (error: Exception) {
            errorResponse(error)
        }
        println(result)
    }
}
