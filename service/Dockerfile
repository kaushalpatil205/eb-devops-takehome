# Stage 1: Build & Verify
FROM python:3.12.7-slim AS builder
WORKDIR /build
COPY app.py .
RUN python -m py_compile app.py

# Stage 2: Runtime
FROM python:3.12.7-slim
WORKDIR /app

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy the verified application
COPY --from=builder /build/app.py .

# Switch to non-root user
USER 10001:10001

EXPOSE 8080
ENV PORT=8080

CMD ["python", "app.py"]
