uvicorn app.main:app --reload

docker build: docker build -t nya-portal:latest
docker run: docker run --env-file .env -p 8000:8000 --name nya-portal --restart unless-stopped nya-portal:latest