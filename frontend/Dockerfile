FROM node:20-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=build /app .
EXPOSE 3021
CMD ["npx", "vite", "preview", "--host", "0.0.0.0", "--port", "3021"]
