import requests
import json
url = "https://api.themoviedb.org/3/tv/popular?language=en-US&page=5"

headers = {
    "accept": "application/json",
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI3YjZlNDhhYjNkYzYyNWI2YWFkZjEzODg5YmFiMzAyOSIsIm5iZiI6MTc1MTEyMjI3Mi42NDYwMDAxLCJzdWIiOiI2ODYwMDE2MGE0ZWFhZTc1MGJkZWJkNzEiLCJzY29wZXMiOlsiYXBpX3JlYWQiXSwidmVyc2lvbiI6MX0.NoxCWGhPLkZfj8dnrkshkGGVa_Ls9fle7aZ2X4_uG08"
}
response = requests.get(url, headers=headers)


# Parse JSON response body
data = response.json()

# Extract the list from the "results" key
response_list = data.get("results")  # use .get with default to avoid None

# Safely build your result list
result = [
    {
        "origin_country": e.get("origin_country"),
        "original_name": e.get("original_name"),
        "overview": e.get("overview"),
        "first_air_date": e.get("first_air_date"),
        "name": e.get("name"),
        "popularity": e.get("popularity")
    }
    for e in response_list
]
with open("movies.json","r",encoding ="utf-8") as f:
  existing_data = json.load(f)
if isinstance(existing_data,list) and isinstance(result,list):
  existing_data.extend(result)
with open("movies.json","w",encoding ="utf-8") as f:
  json.dump(existing_data,f,indent =2,ensure_ascii = False)
