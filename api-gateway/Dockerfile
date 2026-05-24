FROM nginx:alpine
COPY default.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 443

CMD ["nginx", "-g", "daemon off;"]
