FROM python:3.11

# Set the working directory
WORKDIR /app

# Copy the application files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the application port
EXPOSE 80

# Run the application with Gunicorn and Uvicorn
CMD ["python", "app.py"]
#CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", "app:app", "--bind", "0.0.0.0:80"]
