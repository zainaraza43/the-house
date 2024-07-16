package ca.razacapital.thehouse.utils

import com.kotlindiscord.kord.extensions.utils.env

val DISCORD_TOKEN = env("DISCORD_CLIENT_SECRET")

val DB_PORT = env("DB_PORT")
val DB_NAME = env("DB_NAME")
val DB_USER = env("DB_USER")
val DB_PASSWORD = env("DB_PASSWORD")