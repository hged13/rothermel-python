
import json
from flask import Flask, request, jsonify, url_for, render_template
import requests
import numpy as np
import logging
from datetime import datetime, timedelta
import psycopg2
import rasterio
import os
import pandas as pd
import fiona
from rasterio.mask import mask
from psycopg2 import sql
from shapely.geometry import box, mapping, shape



app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static'

@app.route('/')
def index():
      # Read the station data from the CSV file
    stations_df = pd.read_csv('./stations2.csv')

    # Convert the DataFrame to a list of dictionaries
    stations = stations_df.to_dict(orient='records')
    stations = json.dumps(stations)

    # Pass the stations data to the template
    return render_template('index.html', stations=stations)



# database connection
#Connects to my postgre database that contains all raster point information (spatially indexed)
# This allows for fast queries
def connect_to_db():
    return psycopg2.connect(
        dbname='geoserver_db',
        user='geoserver_user',
        password='password',
        host='localhost',
        port='5432'
    )

# Because not every clicked point on the map will correspond to an actual raster entry
# We must find the nearest point to enable our data query

def get_nearest_point_data(input_x, input_y):
    conn = connect_to_db()
    nearest_x, nearest_y = None, None
    output_file = "nearest_point.txt"


    # Find the nearest point
    with conn.cursor() as cur:
        cur.execute("""
        SELECT x, y
        FROM mosaic_schema.location
        ORDER BY the_geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT 1;
        """, (input_x, input_y))

        result = cur.fetchone()
        if result:
            nearest_x, nearest_y = result[0], result[1]
            with open(output_file, "w") as file:
                file.write(f"Nearest point coordinates: x = {nearest_x}, y = {nearest_y}\n")

            return nearest_x, nearest_y

# Connects to the database and gets ALL data for precip, outer, mean and, median
# At the clicked point. (or the closest stored point to it)
# This could be refined to only specify a certain timerange.
# This is currently the only function being called by the index.html file.
# OTHER individual functions are defined below incase only single variables are wanted to be queried.
@app.route('/get_all_data')
def get_all_data():
    input_x = request.args.get('lng')
    input_y = request.args.get('lat')

    x, y = get_nearest_point_data(input_x, input_y)

    conn = connect_to_db()

    with conn.cursor() as cur:
        cur.execute(sql.SQL("""
            SELECT timestamp, value
            FROM {}.{}
            WHERE x = %s AND y = %s
            ORDER BY timestamp;
            """).format(sql.Identifier('mosaic_schema'), sql.Identifier('precipitation_raster_timeseries')), (x, y))
        results = cur.fetchall()
        times = [row[0] for row in results]
        precip_values = [row[1] for row in results]

    with conn.cursor() as cur:
        cur.execute(sql.SQL("""
          SELECT value
          FROM {}.{}
          WHERE x = %s AND y = %s
          ORDER BY timestamp;
        """).format(sql.Identifier('mosaic_schema'), sql.Identifier('mean_raster_timeseries2')), (x, y))
        results = cur.fetchall()
        mean_values = [row[0] for row in results]

    with conn.cursor() as cur:
        cur.execute(sql.SQL("""
          SELECT value
          FROM {}.{}
          WHERE x = %s AND y = %s
          ORDER BY timestamp;
        """).format(sql.Identifier('mosaic_schema'), sql.Identifier('outer_raster_timeseries4')), (x, y))
        results = cur.fetchall()
        outer_values = [row[0] for row in results]

    with conn.cursor() as cur:
        cur.execute(sql.SQL("""
          SELECT value
          FROM {}.{}
          WHERE x = %s AND y = %s
          ORDER BY timestamp;
        """).format(sql.Identifier('mosaic_schema'), sql.Identifier('median_raster_timeseries')), (x, y))
        results = cur.fetchall()
        median_values = [row[0] for row in results]

    print("WE MADE IT ")



    return jsonify({
        'precipitation': {'times': times, 'values': precip_values},
        'outer': {'times': times, 'values': outer_values},
        'mean': {'times': times, 'values': mean_values},
        'median': {'times': times, 'values': median_values}
    })


@app.route('/get_all_data_test')
def get_all_data_test():
    print("BEEN CALLED")
    input_x = request.args.get('lng')
    input_y = request.args.get('lat')

    x, y = get_nearest_point_data(input_x, input_y)

    conn = connect_to_db()

    query = sql.SQL("""
        WITH precip AS (
            SELECT timestamp, value
            FROM {}.{}
            WHERE x = %s AND y = %s
            ORDER BY timestamp
        ),
        mean_data AS (
            SELECT timestamp, value
            FROM {}.{}
            WHERE x = %s AND y = %s
            ORDER BY timestamp
        ),
        outer_data AS (
            SELECT timestamp, value
            FROM {}.{}
            WHERE x = %s AND y = %s
            ORDER BY timestamp
        ),
        median_data AS (
            SELECT timestamp, value
            FROM {}.{}
            WHERE x = %s AND y = %s
            ORDER BY timestamp
        )
        SELECT precip.timestamp, precip.value AS precip_value, mean_data.value AS mean_value,
               outer_data.value AS outer_value, median_data.value AS median_value
        FROM precip
        JOIN mean_data ON precip.timestamp = mean_data.timestamp
        JOIN outer_data ON precip.timestamp = outer_data.timestamp
        JOIN median_data ON precip.timestamp = median_data.timestamp;
    """).format(
        sql.Identifier('mosaic_schema'), sql.Identifier('precipitation_raster_timeseries'),
        sql.Identifier('mosaic_schema'), sql.Identifier('mean_raster_timeseries2'),
        sql.Identifier('mosaic_schema'), sql.Identifier('outer_raster_timeseries4'),
        sql.Identifier('mosaic_schema'), sql.Identifier('median_raster_timeseries')
    )

    with conn.cursor() as cur:
        cur.execute(query, (x, y, x, y, x, y, x, y))
        results = cur.fetchall()

    print("IT WORKED?")

    times = [row[0] for row in results]
    precip_values = [row[1] for row in results]
    mean_values = [row[2] for row in results]
    outer_values = [row[3] for row in results]
    median_values = [row[4] for row in results]

    return jsonify({
        'precipitation': {'times': times, 'values': precip_values},
        'outer': {'times': times, 'values': outer_values},
        'mean': {'times': times, 'values': mean_values},
        'median': {'times': times, 'values': median_values}
    })
# Connects to the database and gets ALL data for outer shell
# At the clicked point. (or the closest stored point to it)
# This could be refined to only specify a certain timerange.
@app.route('/get_coverage_outer')
def get_coverage_outer():
    input_x = request.args.get('lng')
    input_y = request.args.get('lat')
    print("Input")
    print(input_x, input_y)

    x, y = get_nearest_point_data(input_x, input_y)
    print("NEW")
    print(x,y)

    conn = connect_to_db()

    with conn.cursor() as cur:
        cur.execute(sql.SQL("""
          SELECT timestamp, value
          FROM {}.{}
          WHERE x = %s AND y = %s
          ORDER BY timestamp;
        """).format(sql.Identifier('mosaic_schema'), sql.Identifier('outer_raster_timeseries4')), (x, y))
        results = cur.fetchall()
        times = [row[0] for row in results]
        values = [row[1] for row in results]
        print(len(times))
        print(len(values))

    return jsonify({'times': times, 'values': values})

@app.route('/get_median_data')
def get_coverage_median():
    input_x = request.args.get('lng')
    input_y = request.args.get('lat')
    print("Input")
    print(input_x, input_y)

    x, y = get_nearest_point_data(input_x, input_y)
    print("NEW")
    print(x,y)

    conn = connect_to_db()

    with conn.cursor() as cur:
        cur.execute(sql.SQL("""
          SELECT timestamp, value
          FROM {}.{}
          WHERE x = %s AND y = %s
          ORDER BY timestamp;
        """).format(sql.Identifier('mosaic_schema'), sql.Identifier('median_raster_timeseries')), (x, y))
        results = cur.fetchall()
        times = [row[0] for row in results]
        values = [row[1] for row in results]
        print(len(times))
        print(len(values))

    return jsonify({'times': times, 'values': values})

@app.route('/get_mean_data')
def get_coverage_mean():
    input_x = request.args.get('lng')
    input_y = request.args.get('lat')
    print("Input")
    print(input_x, input_y)

    x, y = get_nearest_point_data(input_x, input_y)
    print("mean waws called ")
    print(x,y)

    conn = connect_to_db()

    with conn.cursor() as cur:
        cur.execute(sql.SQL("""
          SELECT timestamp, value
          FROM {}.{}
          WHERE x = %s AND y = %s
          ORDER BY timestamp;
        """).format(sql.Identifier('mosaic_schema'), sql.Identifier('mean_raster_timeseries2')), (x, y))
        results = cur.fetchall()
        times = [row[0] for row in results]
        values = [row[1] for row in results]
        print(len(times))
        print(len(values))

    return jsonify({'times': times, 'values': values})



# Connects to the database and gets ALL data for precipitation
# At the clicked point. (or the closest stored point to it)
# This could be refined to only specify a certain timerange.
@app.route('/get_precip_data')
def get_precipitation_data():
  in_x = request.args.get('lng')
  in_y = request.args.get('lat')

  x, y = get_nearest_point_data(in_x, in_y)

  conn =psycopg2.connect(
        dbname='geoserver_db',
        user='geoserver_user',
        password='password',
        host='localhost',
        port='5432'
  )

  with conn.cursor() as cur:
    cur.execute(sql.SQL("""
          SELECT timestamp, value
          FROM {}.{}
          WHERE x = %s AND y = %s
          ORDER BY timestamp;
        """).format(sql.Identifier('mosaic_schema'), sql.Identifier('precipitation_raster_timeseries')), (x, y))
    results = cur.fetchall()
    times = [row[0] for row in results]
    print(times)

    values = [row[1] for row in results]
    print(len(values))


    return jsonify({'times': times, 'values': values})





@app.route('/process_raster', methods=['POST'])
def process_raster():

    coverage_id_1= request.args.get('coverage1')
    coverage_id_2 = request.args.get('coverage2')
    print(coverage_id_1)
    print(coverage_id_2)


# Define the WPS request URL and headers
    coverage_id_1= "Nelson__Mean2_granule_Mean2.1"
    url = "http://localhost:8086/geoserver/ows"
    headers = {'Content-Type': 'text/xml'}

# WPS request payload with CDATA sections
    data_template = '''<?xml version="1.0" encoding="UTF-8"?>
<wps:Execute version="1.0.0" service="WPS" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:wps="http://www.opengis.net/wps/1.0.0" xmlns:ows="http://www.opengis.net/ows/1.1" xmlns:xlink="http://www.w3.org/1999/xlink">
  <ows:Identifier>ras:Jiffle</ows:Identifier>
  <wps:DataInputs>
    <wps:Input>
      <ows:Identifier>coverage</ows:Identifier>
      <wps:Reference mimeType="image/tiff" xlink:href="http://localhost:8086/geoserver/ows" method="POST">
        <wps:Body>
          <![CDATA[
          <wcs:GetCoverage service="WCS" version="2.0.1" xmlns:wcs="http://www.opengis.net/wcs/2.0">
            <wcs:CoverageId>{coverage_id_1}</wcs:CoverageId>
            <wcs:Format>image/tiff</wcs:Format>
          </wcs:GetCoverage>
          ]]>
        </wps:Body>
      </wps:Reference>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>coverage</ows:Identifier>
      <wps:Reference mimeType="image/tiff" xlink:href="http://localhost:8086/geoserver/ows" method="POST">
        <wps:Body>
          <![CDATA[
          <wcs:GetCoverage service="WCS" version="2.0.1" xmlns:wcs="http://www.opengis.net/wcs/2.0">
            <wcs:CoverageId>{coverage_id_2}</wcs:CoverageId>
            <wcs:Format>image/tiff</wcs:Format>
          </wcs:GetCoverage>
          ]]>
        </wps:Body>
      </wps:Reference>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>script</ows:Identifier>
      <wps:Data>
        <wps:LiteralData> if (src1[0] == -255 || src2[0] == -255 ) {{
    dest = -255;
  }} else {{ band1 = src1[0]; band2 = src2[0]; dest = band2-band1;}} </wps:LiteralData>
      </wps:Data>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>sourceName</ows:Identifier>
      <wps:Data>
        <wps:LiteralData>src1</wps:LiteralData>
      </wps:Data>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>sourceName</ows:Identifier>
      <wps:Data>
        <wps:LiteralData>src2</wps:LiteralData>
      </wps:Data>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>outputType</ows:Identifier>
      <wps:Data>
        <wps:LiteralData>DOUBLE</wps:LiteralData>
      </wps:Data>
    </wps:Input>
    <wps:Input>
      <ows:Identifier>bandCount</ows:Identifier>
      <wps:Data>
        <wps:LiteralData>1</wps:LiteralData>
      </wps:Data>
    </wps:Input>
    </wps:DataInputs>
    <wps:ResponseForm>
      <wps:RawDataOutput mimeType="image/tiff">
        <ows:Identifier>result</ows:Identifier>
      </wps:RawDataOutput>
    </wps:ResponseForm>
</wps:Execute>'''


    data = data_template.format(coverage_id_1=coverage_id_1, coverage_id_2=coverage_id_2)
    response = requests.post(url, headers=headers, data=data)
    if response.status_code != 200:
        print("WPS request failed with status code:", response.status_code)
        return jsonify({'error': 'WPS request failed'}), 500

    print("WPS request succeeded")


    # Save the response content as an image file
    result_filepath = "resultnew2genius.tiff"
    with open(result_filepath, "wb") as f:
        f.write(response.content)

    # Clip the raster using rasterio
    shapefile_path = "./Northern Rockies..shp"
    output_clipped_filepath = os.path.join(app.config['UPLOAD_FOLDER'], "clipped_result.tiff")



   # Read the shapefile and extract its geometry
    with fiona.open(shapefile_path, "r") as shapefile:
      shapes = [shape(feature["geometry"]) for feature in shapefile]

        # Open the result raster and clip it
    with rasterio.open(result_filepath) as src:
        out_image, out_transform = mask(src, shapes, crop=True, nodata=-255)
        out_meta = src.meta.copy()
        print("Raster clipped successfully")

        # Update metadata for the clipped image
        out_meta.update({
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
            "nodata": -255
        })

        # Save the clipped image
        with rasterio.open(output_clipped_filepath, "w", **out_meta) as dest:
            dest.write(out_image)
        print("Clipped image saved as", output_clipped_filepath)

        file_url = url_for('static', filename='clipped_result.tiff', _external=True)
        print("Returning file URL:", file_url)
        return jsonify({'url': file_url})




if __name__ == '__main__':
    app.run(debug=True)
