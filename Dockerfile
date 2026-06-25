FROM python:3.12-slim

# Set direktori kerja di dalam container.
WORKDIR /app

# Install dependency sebelum copy kode untuk memanfaatkan layer cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode aplikasi dan data.
COPY agent/ ./agent/
COPY api/ ./api/
COPY app/ ./app/
COPY services/ ./services/
COPY observability/ ./observability/
COPY data/ ./data/
COPY config.py .
COPY pyproject.toml .
COPY start.sh .

# Install project sebagai editable package agar semua import resolve dari root.
RUN pip install -e .

# Beri permission eksekusi ke start.sh.
RUN chmod +x start.sh

# Port yang diekspos ke publik adalah Streamlit.
EXPOSE 8080

# Jalankan start.sh saat container start.
CMD ["./start.sh"]