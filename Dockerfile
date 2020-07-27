FROM python:3.7-slim-buster

LABEL maintainer="areed145@gmail.com"

WORKDIR /bus_wx

COPY . /bus_wx

# We copy just the requirements.txt first to leverage Docker cache
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# EXPOSE 80

CMD ["python", "src/kk6gpv_bus_wx/bus_wx.py"]
