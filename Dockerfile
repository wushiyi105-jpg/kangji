FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN pip install -e .

EXPOSE 8772

CMD ["python", "-m", "kangji", "serve", "--host", "0.0.0.0"]
