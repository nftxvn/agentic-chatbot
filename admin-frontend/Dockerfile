FROM node:22-alpine

WORKDIR /app

# Install utility
RUN apk add --no-cache dos2unix

# Salin package manifest untuk layer caching
COPY package*.json ./
RUN npm install

# Salin sisa kode
COPY . .

# Pasang script entrypoint
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN dos2unix /usr/local/bin/docker-entrypoint.sh && chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 5173

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
