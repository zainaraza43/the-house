# The House

A betting Discord bot project. (more coming soon)

## Setup and Development

### Prerequisites

- Docker
- Docker Compose (optional, for multi-container setups)

### Setting up the Project

1. **Copy the environment file:**
    ```sh
    cp .env.example .env
    ```
2. **Update the environment variables:** Open the `.env` file and update the environment variables as needed.

### Running the Project with Docker

1. **Build the Docker image:**
    ```sh
   docker build -t the-house .
    ```
2. **Run the Docker container:**
    ```sh
   docker run --env-file .env -p 8000:8000 the-house
    ```
   Replace `8000:8000` with the appropriate port if your application runs on a different port.