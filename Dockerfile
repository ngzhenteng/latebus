FROM --platform=linux/amd64 python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app
# Install any dependencies specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ARG TELE_BOT_API_KEY
ARG LTA_ACC_KEY
ARG LTA_ODATA_URL
ARG GMAP_URL_BASE

# Define environment variable
ENV TELE_BOT_API_KEY="$TELE_BOT_API_KEY"
ENV LTA_ACC_KEY="$LTA_ACC_KEY"
ENV LTA_ODATA_URL="$LTA_ODATA_URL"
ENV GMAP_URL_BASE="$GMAP_URL_BASE"

# Run app.py when the container launches
CMD ["python", "main.py"]
