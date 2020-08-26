FROM python:3.7-slim-buster

LABEL maintainer="areed145@gmail.com"

WORKDIR /bus_wx

COPY . /bus_wx

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

CMD ["python", "bus_wx/bus_wx.py"]
