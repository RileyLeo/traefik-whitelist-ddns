FROM python:alpine3.15

# make a directory for the app
RUN mkdir -p /app
# Set the working directory
WORKDIR /app

# pip install requirements from requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the script to the container
COPY app/ ./

# Run the script
CMD ["python", "main.py"]
