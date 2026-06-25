FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY knowledge/ ./knowledge/
COPY mech_bot_main.py .
ENV PYTHONOPTIMIZE=1 MALLOC_TRIM_THRESHOLD_=100000
EXPOSE 8080
CMD ["python", "mech_bot_main.py"]
