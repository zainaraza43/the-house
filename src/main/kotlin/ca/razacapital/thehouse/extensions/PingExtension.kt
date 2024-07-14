package ca.razacapital.thehouse.extensions

import com.kotlindiscord.kord.extensions.extensions.Extension
import com.kotlindiscord.kord.extensions.extensions.publicSlashCommand

class PingExtension : Extension() {
    override val name = "ping"

    override  suspend fun setup() {
        publicSlashCommand {
            name = "ping"
            description = "pings bot"

            action {
                respond {
                    content = "pong ${user.mention}!"
                }
            }
        }
    }
}