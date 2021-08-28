FROM python:3.9-alpine as build

RUN apk add --no-cache --virtual .build-deps gcc libc-dev libxslt-dev

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt


## -----
FROM python:3.9-alpine as app

RUN apk add --no-cache libxslt

COPY --from=build /usr/src/app/wheels /wheels
RUN pip install --no-cache /wheels/*

COPY *.py /app/
ENTRYPOINT ["python3",  "/app/puregym-tracker.py"]
