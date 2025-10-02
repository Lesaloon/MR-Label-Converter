# syntax=docker/dockerfile:1.6
FROM nginx:stable-alpine

COPY frontend/index.html /usr/share/nginx/html/index.html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
