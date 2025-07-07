
FROM golang:1.24-alpine


RUN apk add gcc musl-dev


WORKDIR /app


COPY go.mod .
RUN go mod download

COPY . .


RUN go build -o proxy_manager .

CMD ["./proxy_manager"]