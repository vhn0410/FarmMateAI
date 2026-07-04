# Stage 1: Build Frontend
FROM node:20-alpine AS build

WORKDIR /app

# Cài đặt dependencies (tận dụng cache)
COPY package.json package-lock.json ./
RUN npm install

# Copy source code và build
COPY . .
RUN npm run build

# Stage 2: Serve với Nginx
FROM nginx:alpine

# Xóa cấu hình mặc định của nginx
RUN rm /etc/nginx/conf.d/default.conf

# Copy cấu hình tùy chỉnh (hỗ trợ React Router fallback)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy file tĩnh từ quá trình build trước đó
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
