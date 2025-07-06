from toxiproxy import Toxiproxy

url = "http://toxiproxy:8474"
toxiproxy = Toxiproxy.from_url(url)

search_proxy = toxiproxy.create_proxy(
name = "search_proxy",
listen = "0.0.0.0:6000",
upstream = "search_tool:5000"
)
weather_proxy = toxiproxy.create_proxy(
    name = "weather_proxy",
    listen = "0.0.0.0:6001",
    upstream = "weather_tool:5001"
)
movie_proxy = toxiproxy.create_proxy(
    name = "movie_proxy",
    listen = "0.0.0.0:6002",
    upstream = "movie_tool:5002"
)
calendar_proxy = toxiproxy.create_proxy(
    name = "calendar_proxy",
    listen = "0.0.0.0:6003",
    upstream = "calendar_tool:5003"
)
message_proxy = toxiproxy.create_proxy(
    name = "message_proxy",
    listen = "0.0.0.0:6005",
    upstream = "message_tool:5005"
)
calculator_proxy = toxiproxy.create_proxy(
    name = "calculator_proxy",
    listen = "0.0.0.0:6004",
    upstream = "calculator_tool:5004"
)
translator_proxy=toxiproxy.create_proxy(
    name="translator_proxy",
    listen="0.0.0.0.6006",
    upstream="translator_tool:5006"
)

