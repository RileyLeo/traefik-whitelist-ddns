FROM python:alpine3.15

# make a directory for the app
RUN mkdir -p /app
# Set the working directory
WORKDIR /app

# pip install requirements from requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script to the container
COPY app/main.py ./app

# Set the required variables by the script
# ENV WHITELIST_CUSTOM_DOMAIN=
# ENV WHITELIST_MIDDLEWARE_NAME=ip-whitelist
# ENV WHITELIST_TRAEFIK_NAMESPACE=traefik-system

# Run the script
CMD ["python", "main.py"]
