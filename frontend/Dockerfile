FROM nginx:alpine

COPY dist/frontend/browser /usr/share/nginx/html

# Rename index.csr.html to index.html
RUN mv /usr/share/nginx/html/index.csr.html /usr/share/nginx/html/index.html

COPY nginx.conf /etc/nginx/nginx.conf

RUN rm -rf /etc/nginx/conf.d

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]