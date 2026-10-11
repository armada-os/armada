plugins {
    kotlin("jvm") version "2.3.21"
    kotlin("plugin.serialization") version "2.3.21"
    id("com.google.protobuf") version "0.10.0"
    application
}

repositories { mavenCentral() }
kotlin { jvmToolchain(25) }
kotlin.sourceSets.main { kotlin.srcDir("lib/src/main/java") }
sourceSets.main {
    java.srcDir("lib/src/main/java")
    proto.srcDir("lib/src/main/proto")
    resources.srcDir("lib/src/main/res/raw")
}

dependencies {
    implementation("com.google.code.gson:gson:2.14.0")
    implementation("com.google.protobuf:protobuf-javalite:4.34.1")
    implementation("com.squareup.okhttp3:okhttp:5.3.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.11.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.11.0")
}

protobuf {
    protoc { artifact = "com.google.protobuf:protoc:4.34.1" }
    generateProtoTasks {
        all().forEach { task -> task.builtins { named("java") { option("lite") } } }
    }
}

application {
    mainClass = "MainKt"
    applicationDefaultJvmArgs = listOf("-Xms16m", "-Xmx128m")
}
