package ca.razacapital.thehouse

import dev.minn.jda.ktx.coroutines.await
import dev.minn.jda.ktx.events.onCommand
import dev.minn.jda.ktx.jdabuilder.light
import io.github.cdimascio.dotenv.dotenv
import kotlin.time.measureTime


private val dotenv = dotenv()

fun main() {
    val discordToken = dotenv["DISCORD_CLIENT_SECRET"]
    val jda = light(discordToken)
    jda.onCommand("ping") { event ->
        val time = measureTime {
            event.reply("Pong!").await() // suspending
        }.inWholeMilliseconds

        event.hook.editOriginal("Pong: $time ms").queue()
    }
}
