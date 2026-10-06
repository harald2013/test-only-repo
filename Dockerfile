FROM python:3.13-slim
COPY app.py .
EXPOSE 8000
CMD ["python", "-u", "app.py"]
