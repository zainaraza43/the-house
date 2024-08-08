# The House

Ever wanted to bet on your friend's competitive video game matches? The House is a Discord bot that allows users to bet on the outcomes of games within their Discord guild. Users can place bets using virtual currency and compete against each other to climb the leaderboard.

## Invite Link

Coming soon!

## Important Policies

1. **No Betting Against Your Own Games:** Users are strictly prohibited from betting on outcomes of games in which they are directly involved. This policy ensures fair play and integrity within the betting environment.
2. **Worthless Currency:** The currency used within The House is purely virtual and holds no real-world value. It is intended solely for entertainment purposes, and there are no plans to assign any monetary value to it now or in the future. Users should not treat it as a financial asset.

## Supported Games

- **League of Legends:** Working
- ~~Valorant:~~ WIP
- ~~CS2:~~ WIP

## Setup and Development

### Prerequisites

- Docker
- Docker Compose

### Setting up the Project

1. **Copy the environment file:**
    ```sh
    cp .env.example .env
    ```
2. **Update the environment variables:** Open the `.env` file and update the environment variables as needed.

### Running the Project with Docker

- **Run the Project with Docker Compose:**
    ```sh
    docker-compose up --build
    ```

## Usage

Once the project is up and running, you can interact with the bot using various commands. Here are some key commands:

- **/set-betting-channel:** Set the channel where betting will take place.
- **/set-currency:** Set the currency for the guild.
- **/set-league-of-legends-account:** Add a League of Legends account.
- **/wallet:** Check the amount of currency in your wallet.
- **/leaderboard:** Check the leaderboard for the guild.
- **/bet:** Bet on the outcome of the current game.

Enjoy the fun of virtual betting with The House, while respecting the policies and understanding the limitations of the virtual currency.
