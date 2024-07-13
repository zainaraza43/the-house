plugins {
    kotlin("jvm") version "2.0.0"

    // KTLint
    id("org.jlleitschuh.gradle.ktlint") version "12.1.1"

    // Detekt
    id("io.gitlab.arturbosch.detekt") version "1.23.6"
}

group = "ca.razacapital"
version = "1.0-SNAPSHOT"

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
}

tasks.test {
    useJUnitPlatform()
}
kotlin {
    jvmToolchain(17)
}

tasks.register<Copy>("copyPreCommitHook") {
    description = "Copy pre-commit git hook from the scripts to the .git/hooks folder."
    group = "git hooks"
    outputs.upToDateWhen { false }
    from("$rootDir/scripts/pre-commit")
    into("$rootDir/.git/hooks/")
}