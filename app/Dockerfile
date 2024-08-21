FROM python:3.10.9

# RUN mkdir /app
WORKDIR /app

COPY requirements.txt .

RUN pip3 install -r /app/requirements.txt --no-cache-dir

COPY . .

#ENV TOKEN secret
#ENV HOST db
#ENV PORT 5432
#ENV USER postgres
#ENV PASSWORD TRAVEL
#ENV NAME TRAVEL

CMD ["python", "main.py"]
