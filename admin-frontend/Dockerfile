FROM node:20-alpine

WORKDIR /app

# Salin package manifest untuk layer caching
COPY package*.json ./
RUN npm install

# Salin sisa kode
COPY . .

EXPOSE 5173

CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"]
