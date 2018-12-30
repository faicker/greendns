FROM python:2.7-alpine
ENV LISTEN 127.0.0.1:53
RUN pip install --no-cache-dir greendns
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
