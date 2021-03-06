"""MUSA 509 demo app"""
from flask import Flask, Response, render_template, escape, request, url_for
import json
import logging
import requests
from sqlalchemy import create_engine, String, Integer
from sqlalchemy.sql import text, bindparam
from google.cloud import bigquery
import geopandas as gpd
from shapely.geometry import shape

app = Flask(__name__, template_folder="templates")

bqclient = bigquery.Client.from_service_account_json("MUSA-509-3337814ad805.json")

# load credentials from a file
with open("pg-credentials.json", "r") as f_in:
    pg_creds = json.load(f_in)

# mapbox
with open("mapbox_token.json", "r") as mb_token:
    MAPBOX_TOKEN = json.load(mb_token)["token"]

# load credentials from JSON file
HOST = pg_creds["HOST"]
USERNAME = pg_creds["USERNAME"]
PASSWORD = pg_creds["PASSWORD"]
DATABASE = pg_creds["DATABASE"]
PORT = pg_creds["PORT"]
engine = create_engine(f"postgresql://{USERNAME}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}")

# index page
@app.route("/")
def index():
    index_html = f"""
    <h2>Hello Endpoints</h2>
    <ul>
      <li><a href="{url_for('hello_basic', name='MUSA 509')}">{url_for('hello_basic', name='MUSA 509')}</a></li>
      <li><a href="{url_for('hello_basic_html', name='MUSA 509')}">{url_for('hello_basic_html', name='MUSA 509')}</a></li>
      <li><a href="{url_for('hello_template', name='MUSA 509')}">{url_for('hello_template', name='MUSA 509')}</a></li>
      <li><a href="{url_for('hello_jinja_basic', name='MUSA 509')}">{url_for('hello_jinja_basic', name='MUSA 509')}</a></li>
      <li><a href="{url_for('hello_jinja_styled', name='MUSA 509')}">{url_for('hello_jinja_styled', name='MUSA 509')}</a></li>
    </ul>
    <h2>Jinja-templated Covid Example</h2>
    <ul>
      <li><a href="{url_for('covid_tests', address='Meyerson Hall, University of Pennsylvania')}">{url_for('covid_tests', address='Meyerson Hall, University of Pennsylvania')}</a></li>
    </ul>
    """
    return index_html


# basic endpoint example
@app.route("/hello_basic/<string:name>/")
def hello_basic(name):
    """Returns text string without HTML tags"""
    return f"Hello, {name}!"


# basic hello html example
@app.route("/hello_basic_html/<string:name>/")
def hello_basic_html(name):
    """Returns basic HTML"""
    html_out = f"<h1>Hello, {name}!</h1>"
    return html_out


# basic template example
@app.route("/hello_template/<string:name>/")
def hello_template(name):
    """Returns a page with a full HTML document"""
    html_out = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Welcome Page</title>
    </head>
    <body>
      <h1>Hello, {name}!</h1>
    </body>
    </html>
    """
    return html_out


@app.route("/hello_jinja_basic/<string:name>/")
def hello_jinja_basic(name):
    """Returns a page from a Jinja2 template"""
    html_out = render_template("hello_template.html", name=name)
    return html_out


# variable rules
@app.route("/hello_jinja_styled/<string:name>/")
def hello_jinja_styled(name):
    """Return a Jinja2-templated welcome page"""
    html_out = render_template("hello_styled.html", name=name)
    return html_out


@app.route("/sample/<string:name>/")
def sample(name):
    """Sample from lecture"""
    counts = [
        {"name": "bike", "count": 20},
        {"name": "scooter", "count": 30},
        {"name": "moped", "count": 12},
    ]
    return render_template("sample.html", name=name, results=counts)


# query string example
@app.route("/geocoder")
def geocode_place():
    place_name = request.args.get("place_name")
    if place_name is None:
        return "No place entered! Use `?place_name=...` query string"
    geocoding_call = (
        f"https://api.mapbox.com/geocoding/v5/mapbox.places/{place_name}.json"
    )
    resp = requests.get(
        geocoding_call, params={"access_token": MAPBOX_TOKEN, "address": place_name}
    )
    return resp.json()


# combine routes to avoid duplication
@app.route("/newhello")
@app.route("/newhello/<string:name>")
def newhello(name=None):
    if name is not None:
        return f"Hello, {name}!"
    return "Hello, World!"


# hello as query string
@app.route("/helloquery", methods=["GET"])
def hello_world():
    name = request.args.get("name")
    if name is not None:
        return f"Hello, {escape(name)}!"
    return "Hello, World!"


# HTNL example
@app.route("/disp_image")
def disp_image():
    urlpath = request.args.get("urlpath")
    if urlpath is None:
        resp = requests.get(
            "https://api.giphy.com/v1/gifs/random?api_key=TPIpfX5L9BHTF29IR5buIVlglzpbGx5j"
        ).json()["data"]["images"]["original"]["url"]
        return f"""
            <h1>No image submitted, try again. Here's a random gif.</h1>
            <img src='{resp}/giphy.gif' />
            <p>Source: <a href='{resp}'>{resp}</a></p>
            """
    return f"""
        <h1>Here's your image</h1>
        <img src='{urlpath}' />
        <p>Source: <a href='{urlpath}'>{urlpath}</a></p>
    """


@app.route("/covid_tests/")
def covid_tests():
    address = request.args.get("address")
    if address is None:
        return f"""
        <p>No address specified, try:</p>
        <div>
        <a href="{url_for('covid_tests', address='Meyerson Hall, University of Pennsylvania')}">{url_for('covid_tests', address='Meyerson Hall, University of Pennsylvania')}</a>
        </div>
        """
    geocoding_call = (
        "https://api.mapbox.com/geocoding/v5/mapbox.places/"
        f"{address}.json?access_token={MAPBOX_TOKEN}"
    )
    resp = requests.get(geocoding_call)
    lng, lat = resp.json()["features"][0]["center"]

    query = text(
        """
    SELECT
        num_tests_positive,
        num_tests_negative,
        ST_X(ST_Centroid(geom)) as longitude,
        ST_Y(ST_Centroid(geom)) as latitude,
        zip_code
    FROM philadelphia_covid_tests
    WHERE ST_Intersects(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
    """
    )
    resp = engine.execute(query, lng=lng, lat=lat).fetchone()
    if resp is None:
        all_zips = engine.execute(
            """
        SELECT string_agg('<a href="/covid_tests/' || zip_code || '/">' || zip_code || '</a>', ', ') as zips
        FROM philadelphia_covid_tests
        """
        ).fetchone()["zips"]
        return f"Zip code `{resp['zip_code']}` is out of Philadelphia. Try one of {all_zips}"

    nearest_hospital = get_nearest_amenity(resp["longitude"], resp["latitude"])

    map_directions, geojson_str = get_static_map(
        start_lng=lng,
        start_lat=lat,
        end_lng=nearest_hospital["longitude"],
        end_lat=nearest_hospital["latitude"],
    )
    logging.warning("Map directions %s", str(map_directions))

    html_map = render_template(
        "geojson_map.html",
        mapbox_token=MAPBOX_TOKEN,
        geojson_str=geojson_str,
        center_lng=(resp["longitude"] + nearest_hospital["longitude"]) / 2,
        center_lat=(resp["latitude"] + nearest_hospital["latitude"]) / 2,
    )
    old_html_response = f"""
    <div style='float: left;'>
        <h1>Covid Tests in Zip Code {resp['zip_code']}</h1>
        <h3>Address entered: {address}</h3>
        <p>
          In your zip code ({resp['zip_code']}) there are:
          <ul>
            <li><b style='color: green;'>{resp['num_tests_negative']} negative tests</b></li>
            <li><b style='color: red;'>{resp['num_tests_positive']} positive tests</b></li>
          </ul>
        </p>
        <p>
          Your nearest hospital is {nearest_hospital['amenity_name']}.<br />Call ahead at {nearest_hospital['phone_number']}.
        </p>
        <!-- <img src='{map_directions}' /> -->
    </div>
        {html_map}
        """

    html_response = render_template(
        "covid_report.html",
        covid_data=resp,
        nearest_hospital=nearest_hospital,
        address=address,
        html_map=html_map,
    )

    response = Response(response=html_response, status=200, mimetype="text/html")
    return response


def get_static_map(start_lng, start_lat, end_lng, end_lat):
    """"""
    geojson_str = get_map_directions(start_lng, start_lat, end_lng, end_lat)
    return (
        f"https://api.mapbox.com/styles/v1/mapbox/streets-v11/static/"
        f"geojson({geojson_str})/auto/640x640?access_token={MAPBOX_TOKEN}"
    ), geojson_str


def get_map_directions(start_lng, start_lat, end_lng, end_lat):
    directions_resp = requests.get(
        f"https://api.mapbox.com/directions/v5/mapbox/cycling/{start_lng},{start_lat};{end_lng},{end_lat}",
        params={
            "access_token": MAPBOX_TOKEN,
            "geometries": "geojson",
            "steps": "false",
            "alternatives": "true",
        },
    )
    routes = gpd.GeoDataFrame(
        geometry=[
            shape(directions_resp.json()["routes"][idx]["geometry"])
            for idx in range(len(directions_resp.json()["routes"]))
        ]
    )
    return routes.iloc[:1].to_json()


def get_nearest_amenity(lng, lat, amenity_type="hospital"):
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("poi_category", "STRING", amenity_type),
            bigquery.ScalarQueryParameter("lng", "FLOAT", lng),
            bigquery.ScalarQueryParameter("lat", "FLOAT", lat),
        ]
    )
    query = f"""
        SELECT (select value from unnest(all_tags) WHERE key = 'name') as amenity_name,
               (select value from unnest(all_tags) WHERE key = 'amenity') as amenity_type,
               (select value from unnest(all_tags) WHERE key = 'addr:street') as address,
               (select value from unnest(all_tags) WHERE key = 'phone') as phone_number,
               CAST(round(ST_Distance(ST_GeogPoint(@lng, @lat), ST_Centroid(geometry))) AS int64) as distance_away_meters,
               ST_X(ST_Centroid(geometry)) as longitude,
               ST_Y(ST_Centroid(geometry)) as latitude
          FROM `bigquery-public-data.geo_openstreetmap.planet_features`
         WHERE ('amenity', @poi_category) IN (SELECT (key, value) FROM UNNEST(all_tags))
         ORDER BY distance_away_meters ASC
         LIMIT 1
    """
    response = [
        dict(row) for row in bqclient.query(query, job_config=job_config).result()
    ]
    return response[0]


# 404 page example
@app.errorhandler(404)
def page_not_found(e):
    return render_template("null_island.html", mapbox_token=MAPBOX_TOKEN), 404


if __name__ == "__main__":
    app.jinja_env.auto_reload = True
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.run(debug=True)
