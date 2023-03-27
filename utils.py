from pyproj import Transformer
import pandas as pd

def get_ptcars_l72():
    # df = pd.read_json('https://opendata.infrabel.be/api/explore/v2.1/catalog/datasets/operationele-punten-van-het-newterk/exports/json?lang=fr&timezone=Europe%2FBerlin')
    df = pd.read_json('operationele-punten-van-het-newterk.json', encoding='utf8')
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:31370", always_xy=True)
    
    df['lat'] = df['geo_shape'].apply(lambda x: x['geometry']['coordinates'][1])
    df['lng'] = df['geo_shape'].apply(lambda x: x['geometry']['coordinates'][0])
    del df['geo_point_2d']
    del df['geo_shape']
    
    coords_L72 = transformer.transform(df['lng'], df['lat'])
    
    df['x72'] = coords_L72[0]
    df['y72'] = coords_L72[1]
    
    return df