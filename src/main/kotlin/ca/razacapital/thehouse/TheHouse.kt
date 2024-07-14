package ca.razacapital.thehouse

import dev.kord.core.Kord
import io.github.cdimascio.dotenv.dotenv


private val dotenv = dotenv()

suspend fun main() {
    val discordToken = dotenv["DISCORD_CLIENT_SECRET"]
    val kord = Kord(discordToken)
    kord.login()
}
