FROM python:3

# Set the working directory
WORKDIR /app

# Copy Pipfile and Pipfile.lock and install dependencies
COPY Pipfile* ./
RUN pip install --no-cache-dir pipenv && \
    pipenv install --system --deploy --ignore-pipfile

# Copy Pipfile and Pipfile.lock and install dependencies
COPY . .

# Start the bot
CMD ["python3", "bot/main.py"]