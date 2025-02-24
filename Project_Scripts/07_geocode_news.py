import re
import pandas as pd
from tqdm import tqdm
from multiprocessing import Pool
from glob import glob
import sqlite3
import geopandas as gpd
from shapely.geometry import Point

# Function to read and process feather files
def read_feather(file_path):
    """
    Reads a feather file and returns it as a DataFrame with additional preprocessing.
    """
    try:
        df = pd.read_feather(file_path)
        df["len"] = df["text"].str.split().str.len()
        return df
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return pd.DataFrame()  # Return an empty DataFrame in case of error

# Main function for processing feather files and creating geomap
def main():
    # Collect all feather files from the folder with NER data
    files = glob(r".\\04_German_News_ner\\*.feather")

    # Number of processes to use (adjust according to your system's capabilities)
    num_processes = min(60, len(files))  # Ensure it does not exceed available CPUs

    # Create a pool of workers for parallel processing
    with Pool(processes=num_processes) as pool:
        # Use tqdm to display a progress bar
        dataframes = list(tqdm(pool.imap(read_feather, files), total=len(files)))

    # Concatenate all DataFrames into one large DataFrame
    combined_df = pd.concat(dataframes, ignore_index=True)

    # Process and clean location data
    combined_df = combined_df.explode("loc").dropna(subset=["loc"])
    combined_df["loc_normal"] = combined_df["loc"].apply(
        lambda x: re.sub(r"[^a-zA-Zäöüß'\- ]", "", str(x).lower()).strip()
    )
    combined_df = combined_df[combined_df["loc_normal"] != ""]

    # Group by normalized location and filter by occurrence count
    geomap = combined_df.groupby("loc_normal").size().reset_index(name="count")
    geomap = geomap[geomap["count"] > 100]

    # Save initial geomap to Excel
    geomap.to_excel(r'.\\geomap.xlsx', index=False)
    # Manual cleaning and validatation of extracted locations
    # Geocode data the data with a service of your choice e.g. Nominatim
    # Load shapefile for spatial join
    kshape = gpd.read_file(r".\vg5000_ebenen_0101\\VG5000_KRS.shp", crs="EPSG:4326")

    # Create GeoDataFrame from geomap for spatial join
    gdf = gpd.GeoDataFrame(
        geomap,
        crs="EPSG:4326",
        geometry=gpd.points_from_xy(geomap["longitude"], geomap["latitude"])
    )

    # Perform spatial join with shapefile
    g2 = gpd.sjoin(gdf, kshape, op="within")

    # Merge spatial data with geomap
    geomap = pd.merge(
        geomap,
        g2[["loc_normal", "ARS", "NUTS", "GEN"]],
        on="loc_normal",
        how="left"
    ).drop_duplicates()

    # Finalize geomap structure
    geomap = geomap[["loc_normal", "latitude", "longitude", "location_id", "ARS", "NUTS", "GEN"]]

    # Save finalized geomap to Excel
    geomap.to_excel(r'.\geomap.xlsx', index=False)
    

if __name__ == "__main__":
    main()
