FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN python3 seed.py

EXPOSE 8000
CMD ["python3", "app.py"]
