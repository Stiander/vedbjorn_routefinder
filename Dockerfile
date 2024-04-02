FROM python:3.10-slim-buster
ENV PYTHONUNBUFFERED 1
RUN mkdir -p /home/routefinder/
COPY ./requirements.txt /home/routefinder/
RUN pip install -r /home/routefinder/requirements.txt
COPY ./src/ /home/routefinder/
WORKDIR /home/routefinder
EXPOSE 5678
CMD python3 main.py
