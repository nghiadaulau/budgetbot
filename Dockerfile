# Sử dụng official AWS Lambda base image cho Python 3.12
FROM public.ecr.aws/lambda/python:3.12

# Copy file requirements vào thư mục task root
COPY requirements.txt requirements-optional.txt ${LAMBDA_TASK_ROOT}/

# Cài đặt toàn bộ dependencies bao gồm cả postgres adapter (psycopg2) và mangum
RUN pip install --no-cache-dir -r requirements.txt -r requirements-optional.txt

# Copy source code ứng dụng vào thư mục task root
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY frontend/ ${LAMBDA_TASK_ROOT}/frontend/

# Set Handler của Lambda trỏ về handler của Mangum trong src/app.py
CMD ["src.app.handler"]
