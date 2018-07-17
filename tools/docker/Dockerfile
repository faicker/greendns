FROM python:2.7-alpine
ENV IDNS 223.5.5.5:53
ENV ODNS 127.0.0.1:5454
ENV LISTEN 127.0.0.1:53
ENV LOGLEVEL info
RUN pip install --no-cache-dir pychinadns
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
