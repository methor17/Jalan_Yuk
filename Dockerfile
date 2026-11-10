FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN mkdir -p /app/data
ENV HOST=0.0.0.0 PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
VOLUME ["/app/data"]
CMD ["python", "app.py"]
