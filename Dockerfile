FROM python:3.10.4-alpine3.15

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /usr/app

ADD requirements.txt .
RUN pip install -r requirements.txt

ADD flask_templates /usr/app/flask_templates
ADD public /usr/app/public
ADD app.py /usr/app/app.py
ADD config.py /usr/app/config.py

ENV TZ=Europe/Berlin

CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5000"]
