FROM python:3-alpine
LABEL maintainer="Yui Yukihira (yuiyukihiria@pm.me)"
EXPOSE 80
COPY setup /setup
RUN sh /setup/setup.sh
COPY src /src
ENTRYPOINT ["python3"]
CMD ["/src/main.py", "&"]
ARG snow_host
ENV SNOW_HOST=$snow_host
ARG auth_host
ENV AUTH_HOST=$auth_host
ARG db_host
ENV DB_HOST=$db_host
ARG db_user
ENV DB_USER=$db_user
ARG db_pass
ENV DB_PASS=$db_pass
