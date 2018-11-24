FROM python:2.7-alpine
ENV IDNS 223.5.5.5:53
ENV ODNS 127.0.0.1:5454
ENV LISTEN 127.0.0.1:53
ENV LOGLEVEL info
ENV TIMEOUT 1.0
ENV MODE select
ENV RFC1918 true
ENV CACHE true
RUN pip install --no-cache-dir greendns
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
