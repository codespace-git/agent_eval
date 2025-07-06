from toxiproxy import Toxiproxy

toxiproxy = Toxiproxy("http://toxiproxy:8474")

toxiproxy.create(name="search_proxy", listen="0.0.0.0:6000", upstream="search_tool:5000")
toxiproxy.create(name="weather_proxy", listen="0.0.0.0:6001", upstream="weather_tool:5001")
toxiproxy.create(name="movie_proxy", listen="0.0.0.0:6002", upstream="movie_tool:5002")
toxiproxy.create(name="calendar_proxy", listen="0.0.0.0:6003", upstream="calendar_tool:5003")
toxiproxy.create(name="calculator_proxy", listen="0.0.0.0:6004", upstream="calculator_tool:5004")
toxiproxy.create(name="message_proxy", listen="0.0.0.0:6005", upstream="message_tool:5005")
toxiproxy.create(name="translator_proxy", listen="0.0.0.0:6006", upstream="translator_tool:5006")


