plugins {
    kotlin("jvm") version "2.0.0"
}

group = "ca.razacapital"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {

    implementation("net.dv8tion:JDA:5.0.0")
    implementation ("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    implementation("club.minnced:jda-ktx:0.11.0-beta.19")
    implementation("io.github.cdimascio:dotenv-kotlin:6.4.1")

    testImplementation(kotlin("test"))
}

tasks.build {
    dependsOn("copyPreCommitHook")
}

tasks.test {
    useJUnitPlatform()
}

kotlin {
    jvmToolchain(17)
}
