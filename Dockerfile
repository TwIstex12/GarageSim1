FROM python:3.11-slim
WORKDIR /app 
COPY . /app
RUN pip install -r requirment.txt
CMD ["python", "bot.py"]
