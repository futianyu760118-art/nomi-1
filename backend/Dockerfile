FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pmo ./pmo
COPY app.py .
COPY entrypoint.sh /entrypoint.sh
RUN useradd --uid 10001 --create-home pmo && mkdir -p /app/data && chown -R pmo:pmo /app && chmod +x /entrypoint.sh
USER pmo
ENV HOST=0.0.0.0
EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "app.py"]
