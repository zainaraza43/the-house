# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the pyproject.toml and poetry.lock files to the container
COPY pyproject.toml poetry.lock /app/

# Install Poetry
RUN pip install poetry

# Install the project dependencies
RUN poetry install --no-dev

# Copy the rest of the application code to the container
COPY . /app

# Expose port (if your application serves on a specific port, e.g., 8000)
EXPOSE 8000

# Specify the command to run the application
CMD ["poetry", "run", "python", "the_house/main.py"]