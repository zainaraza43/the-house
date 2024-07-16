package ca.razacapital.thehouse

import ca.razacapital.thehouse.extensions.PingExtension
import ca.razacapital.thehouse.utils.DISCORD_TOKEN
import com.kotlindiscord.kord.extensions.ExtensibleBot

suspend fun main() {
    val bot = ExtensibleBot(DISCORD_TOKEN) {
        extensions {
            add(::PingExtension)
        }

    }

    bot.start()
}
