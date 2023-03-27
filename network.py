# run with:
# streamit run network.py

import streamlit as st
import pandas as pd
import duckdb


@st.cache_data
def import_trains():
    return pd.read_csv('https://fr.ftp.opendatasoft.com/infrabel/PunctualityHistory/Data_raw_punctuality_202302.csv')
    # download locally to improve perf:
    # `wget https://fr.ftp.opendatasoft.com/infrabel/PunctualityHistory/Data_raw_punctuality_202302.csv``
    # return pd.read_csv('Data_raw_punctuality_202302.csv')


@st.cache_data
def import_ptcars():
    df = pd.read_json('https://opendata.infrabel.be/api/explore/v2.1/catalog/datasets/operationele-punten-van-het-newterk/exports/json?lang=fr&timezone=Europe%2FBerlin')
    df['lat'] = df['geo_shape'].apply(lambda x: x['geometry']['coordinates'][1])
    df['lon'] = df['geo_shape'].apply(lambda x: x['geometry']['coordinates'][0])
    del df['geo_point_2d']
    del df['geo_shape']
    return df

@st.cache_data
def prepare_trains(df):
    
    # Repair DataFrame
    df.loc[pd.isnull(df['PLANNED_TIME_ARR']), 'PLANNED_TIME_ARR'] = df.loc[pd.isnull(df['PLANNED_TIME_ARR']),'PLANNED_TIME_DEP']
    df.loc[pd.isnull(df['PLANNED_TIME_DEP']), 'PLANNED_TIME_DEP'] = df.loc[pd.isnull(df['PLANNED_TIME_DEP']),'PLANNED_TIME_ARR']
    df.loc[pd.isnull(df['REAL_TIME_ARR']), 'REAL_TIME_ARR'] = df.loc[pd.isnull(df['REAL_TIME_ARR']),'REAL_TIME_DEP']
    df.loc[pd.isnull(df['REAL_TIME_DEP']), 'REAL_TIME_DEP'] = df.loc[pd.isnull(df['REAL_TIME_DEP']),'REAL_TIME_ARR']
    df.loc[pd.isnull(df['PLANNED_DATE_ARR']), 'PLANNED_DATE_ARR'] = df.loc[pd.isnull(df['PLANNED_DATE_ARR']),'PLANNED_DATE_DEP']
    df.loc[pd.isnull(df['PLANNED_DATE_DEP']), 'PLANNED_DATE_DEP'] = df.loc[pd.isnull(df['PLANNED_DATE_DEP']),'PLANNED_DATE_ARR']
    df.loc[pd.isnull(df['REAL_DATE_ARR']), 'REAL_DATE_ARR'] = df.loc[pd.isnull(df['REAL_DATE_ARR']),'REAL_DATE_DEP']
    df.loc[pd.isnull(df['REAL_DATE_DEP']), 'REAL_DATE_DEP'] = df.loc[pd.isnull(df['REAL_DATE_DEP']),'REAL_DATE_ARR']
    df.loc[pd.isnull(df['LINE_NO_DEP']), 'LINE_NO_DEP'] = 'noline'
    df['i'] = df.index

    # Create edges in SQL with DuckDB
    sql = """
        WITH sq AS (
            SELECT
                strptime(DATDEP, '%d%b%Y') AS DATDEP,
                TRAIN_NO,
                RELATION,
                TRAIN_SERV,
                PTCAR_NO,
                LINE_NO_DEP,
                CAST(strptime(REAL_DATE_ARR,    '%d%b%Y') AS DATE) + CAST(strptime(REAL_TIME_ARR,    '%-H:%M:%S') AS TIME) AS REAL_DT_ARR,
                CAST(strptime(REAL_DATE_DEP,    '%d%b%Y') AS DATE) + CAST(strptime(REAL_TIME_DEP,    '%-H:%M:%S') AS TIME) AS REAL_DT_DEP,
                CAST(strptime(PLANNED_DATE_ARR, '%d%b%Y') AS DATE) + CAST(strptime(PLANNED_TIME_ARR, '%-H:%M:%S') AS TIME) AS PLANNED_DT_ARR,
                CAST(strptime(PLANNED_DATE_DEP, '%d%b%Y') AS DATE) + CAST(strptime(PLANNED_TIME_DEP, '%-H:%M:%S') AS TIME) AS PLANNED_DT_DEP,
                DELAY_ARR,
                DELAY_DEP,
                PTCAR_LG_NM_NL,
                LINE_NO_ARR,
                i,
            FROM
                df
        ), shifted AS (
            SELECT
                *,
                LEAD(PTCAR_LG_NM_NL) OVER w AS NEXT_PTCAR_LG_NM_NL,
                LEAD(LINE_NO_ARR) OVER w AS NEXT_LINE_NO_ARR,
                LEAD(PTCAR_NO) OVER w AS NEXT_PTCAR_NO,
                LEAD(LINE_NO_DEP) OVER w AS NEXT_LINE_NO_DEP,
                LEAD(REAL_DT_ARR) OVER w AS NEXT_REAL_DT_ARR,
                LEAD(REAL_DT_DEP) OVER w AS NEXT_REAL_DT_DEP,
                LEAD(PLANNED_DT_ARR) OVER w AS NEXT_PLANNED_DT_ARR,
                LEAD(PLANNED_DT_DEP) OVER w AS NEXT_PLANNED_DT_DEP,
            FROM
                sq
            WINDOW w AS (PARTITION BY TRAIN_NO, DATDEP ORDER BY i)
        )
        SELECT
            DATDEP,
            TRAIN_NO,
            RELATION,
            EXTRACT('epoch' FROM (NEXT_REAL_DT_DEP - REAL_DT_DEP)) AS REAL_TIME,
            EXTRACT('epoch' FROM (NEXT_PLANNED_DT_DEP - PLANNED_DT_DEP)) AS PLANNED_TIME,
            EXTRACT('epoch' FROM (REAL_DT_DEP - PLANNED_DT_DEP)) AS DELAY_DEP,
            PTCAR_LG_NM_NL || '_' || LINE_NO_DEP AS NODE_1,
            PTCAR_LG_NM_NL AS PTCAR_1,
            LINE_NO_DEP AS LINE_NO_1,
            PTCAR_NO AS PTCAR_ID_1,
            NEXT_PTCAR_LG_NM_NL || '_' || NEXT_LINE_NO_DEP AS NODE_2,
            NEXT_PTCAR_LG_NM_NL AS PTCAR_2,
            NEXT_LINE_NO_DEP AS LINE_NO_2,
            NEXT_PTCAR_NO AS PTCAR_ID_2,
            EXTRACT('hour' FROM REAL_DT_DEP) AS HOUR,
        FROM
            shifted
        WHERE
            NEXT_PTCAR_NO IS NOT NULL
        ORDER BY
            DATDEP, TRAIN_NO, REAL_DT_DEP
    """
    return duckdb.sql(sql).df()


@st.cache_data
def get_ptcars(df):
    sql = """
        SELECT DISTINCT
            PTCAR_1
        FROM
            df
        ORDER BY
            1
    """
    return duckdb.sql(sql).df()


def get_stats_by_station(df, ptcar='CHARLEROI-CENTRAL'):
    return df.loc[
            df['PTCAR_1'] == ptcar,:
        ].groupby([
            'LINE_NO_1',
            'LINE_NO_2',
            'PTCAR_2'
        ])['REAL_TIME'].aggregate(['count', 'min', 'median', 'mean', 'max'])


def get_linked_ptcars(df_trains, df_ptcars_attributes, ptcar='CHARLEROI-CENTRAL'):
    sql = """
        SELECT DISTINCT
            ptcarid,
            longnamedutch,
            longnamefrench,
            taftapcode,
            symbolicname,
            lat,
            lon
        FROM
            df_trains
        JOIN
            df_ptcars_attributes
            ON df_ptcars_attributes.longnamedutch = df_trains.PTCAR_2
        WHERE
            df_trains.PTCAR_1 = ?
        ORDER BY
            1
    """
    with duckdb.connect() as con:
        df_result = con.execute(sql, [ptcar]).df()
    return df_result

df_raw = import_trains()
df_trains = prepare_trains(df_raw)
df_ptcars = get_ptcars(df_trains)
df_ptcars_attributes = import_ptcars()


st.write("""
    # Station stats

    Stats by station from Infrabel Open Data
""")

st.write("""
    ## PTCARs

    Select PTCAR
""")
ptcar = st.selectbox('PTCAR', df_ptcars)

st.write(f"""
    ## Stats for {ptcar}
""")

st.write(get_stats_by_station(df_trains, ptcar))

st.write("""
    ## Linked PTCARs
""")

linked_ptcars = get_linked_ptcars(df_trains, df_ptcars_attributes, ptcar)

st.write(linked_ptcars)
st.map(data=linked_ptcars)
