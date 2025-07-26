
FROM golang:1.24-alpine


RUN apk add --no-cache gcc musl-dev


WORKDIR /app


COPY go.mod .
RUN go mod download


COPY . .

RUN go build -o proxy_manager .

HEALTHCHECK --interval=30s --retries=3 --timeout=5s \
CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

CMD ["./proxy_manager"]
